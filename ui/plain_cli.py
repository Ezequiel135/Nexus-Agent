from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import json
import threading

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.actions import CancelledExecution
from core.config import NexusPaths
from core.llm import LiteLLMBridge
from core.logging_utils import log_event
from core.memory import clear_memory, memory_summary, remember
from core.notebooks import list_notebooks
from core.safeguards import blocked_examples, blocked_reasons
from core.state import ActivityMonitor
from core.version import APP_VERSION


def format_session_summary(config) -> str:
    account = config.active_account
    agent = config.active_agent
    provider = account.provider_label if account else "-"
    model_name = account.model_name if account else "-"
    account_name = account.name if account else "-"
    agent_name = agent.name if agent else "-"
    return (
        f"Conta ativa: {account_name}\n"
        f"Agente ativo: {agent_name}\n"
        f"Provider: {provider}\n"
        f"Modelo: {model_name}\n"
        f"Workspace Nexus: {NexusPaths.base_dir}"
    )


def format_onboarding_message(first_run: bool = False) -> str:
    intro = (
        "Primeira sessao concluida. O setup ja foi salvo e o agente esta pronto para operar."
        if first_run
        else "Bem-vindo ao NEXUS AGENT."
    )
    return (
        f"{intro}\n\n"
        "1. Descreva um objetivo real em linguagem natural.\n"
        "2. Use /help para comandos e /tools para ver capacidades.\n"
        "3. Use /blocked para revisar os limites de seguranca.\n"
        "4. Use /memory para consultar o contexto salvo.\n"
        "5. Use nexus parallel run para comparar varios agentes."
    )


class PlainNexusCLI:
    def __init__(
        self,
        bridge: LiteLLMBridge,
        monitor: ActivityMonitor,
        initial_task: str | None = None,
        first_run: bool = False,
    ) -> None:
        self.bridge = bridge
        self.monitor = monitor
        self.initial_task = initial_task
        self.first_run = first_run
        self.console = Console()
        self.conversation: list[dict[str, str]] = []
        self.pending_plan: dict[str, object] | None = None
        self.cancel_event = threading.Event()
        self.bridge.actions.set_event_callback(self._write_log)
        self.bridge.actions.set_cancel_event(self.cancel_event)

    def run(self) -> int:
        self.conversation = self._load_history()
        ok, message = self.bridge.handshake()
        self._render_header()
        self._render_session_summary()
        if self.first_run:
            self._render_onboarding_panel(first_run=True)
        self._write_log(message)
        self.console.print("[bold green]NEXUS AGENT online[/bold green]" if ok else f"[bold red]{message}[/bold red]")
        if self.initial_task:
            self._handle_prompt(self.initial_task)

        while True:
            snap = self.monitor.read()
            self.console.print(
                f"[dim]estado={snap.state} | modelo={snap.current_model} | latencia={snap.api_latency_ms}ms | /help[/dim]"
            )
            try:
                prompt = self.console.input("[bold cyan]nexus> [/bold cyan]").strip()
            except (EOFError, KeyboardInterrupt):
                self.console.print("\n[bold yellow]Saindo do NEXUS AGENT.[/bold yellow]")
                return 0

            if not prompt:
                continue
            if prompt.startswith("/"):
                if self._handle_slash(prompt):
                    return 0
                continue
            self._handle_prompt(prompt)

    def _render_header(self) -> None:
        self.console.print(
            Panel.fit(
                "[bold green]NEXUS AGENT[/bold green]\n"
                f"[yellow]Modo plain estilo Codex/Claude Code | {APP_VERSION}[/yellow]\n"
                "[dim cyan]Criado por Ezequiel 135[/dim cyan]\n"
                "[white]Shell + Files + Vision + Memory + MCP + Notebooks + Remote Bots + Parallel Agents[/white]",
                border_style="bright_cyan",
            )
        )
        self.console.print(
            "[dim]Dica: use /help, /accounts, /agents, /mcp, /notebooks, /remote, /tools e /exit[/dim]"
        )

    def _render_session_summary(self) -> None:
        self.console.print(
            Panel.fit(
                format_session_summary(self.bridge.config),
                title="Sessao Ativa",
                border_style="bright_blue",
            )
        )

    def _render_onboarding_panel(self, *, first_run: bool = False) -> None:
        title = "Primeira Sessao" if first_run else "Onboarding"
        self.console.print(
            Panel.fit(
                format_onboarding_message(first_run=first_run),
                title=title,
                border_style="bright_magenta",
            )
        )

    def _handle_prompt(self, prompt: str) -> None:
        self.console.print(Panel.fit(prompt, title="Voce", border_style="cyan"))
        log_event("PROMPT", prompt)
        remember(prompt, source="user", kind="prompt")
        try:
            if self._should_preview_plan(prompt):
                self.pending_plan = self.bridge.preview_plan(prompt)
                self._render_plan_preview(self.pending_plan)
                return
            self._run_chat(prompt)
        except CancelledExecution as exc:
            self.console.print(Panel.fit(str(exc), title="CANCELADO", border_style="yellow"))
        except Exception as exc:
            self.monitor.set_state("error", str(exc))
            self.console.print(Panel.fit(str(exc), title="ERRO", border_style="red"))

    def _should_preview_plan(self, prompt: str) -> bool:
        lowered = prompt.lower()
        keywords = ["organizar", "criar", "baixar", "instalar", "configurar", "buscar", "processar", "mover", "apagar"]
        return bool(
            self.bridge.config.plan_before_execute
            and (len(prompt.split()) > 4 or any(word in lowered for word in keywords))
        )

    def _render_plan_preview(self, preview: dict[str, object]) -> None:
        steps = preview.get("steps", []) if isinstance(preview, dict) else []
        lines = [f"Objetivo: {preview.get('goal', '-')}", ""]
        for step in steps:
            if not isinstance(step, dict):
                continue
            risk = str(step.get("risk_level", "green")).upper()
            tool_name = step.get("tool") or "livre"
            lines.append(f"{step.get('step')}. {step.get('task')} [{risk}]")
            lines.append(f"   tool={tool_name} args={step.get('args', {})}")
        lines.append("")
        lines.append("Use /approve para executar ou /cancel para descartar.")
        self.console.print(Panel.fit("\n".join(lines), title="Plano", border_style="bright_magenta"))

    def _run_chat(self, prompt: str) -> None:
        self.cancel_event.clear()
        self.conversation.append({"role": "user", "content": prompt})
        self._save_history()
        answer, _tool_logs = self.bridge.chat(self.conversation)
        self.conversation.append({"role": "assistant", "content": answer})
        self._save_history()
        self.console.print(Panel.fit(answer or "(sem resposta)", title="NEXUS AGENT", border_style="green"))

    def _approve_pending_plan(self) -> None:
        if self.pending_plan is None:
            self.console.print("[yellow]Nenhum plano pendente.[/yellow]")
            return
        preview = self.pending_plan
        self.pending_plan = None
        self.cancel_event.clear()
        goal = str(preview.get("goal", ""))
        steps = preview.get("steps", [])
        result = self.bridge.execute_plan(goal, steps if isinstance(steps, list) else [])
        self.console.print(Panel.fit(result.get("summary", "(sem resumo)"), title="Execucao", border_style="green"))

    def _handle_slash(self, prompt: str) -> bool:
        command = prompt.strip().lower()
        if command == "/help":
            table = Table(title="Comandos do Terminal")
            table.add_column("Comando", style="cyan")
            table.add_column("Descricao", style="white")
            table.add_row("/help", "Mostra ajuda")
            table.add_row("/init", "Alias para onboarding")
            table.add_row("/onboarding", "Explica como usar o agente")
            table.add_row("/status", "Mostra status do agente")
            table.add_row("/accounts", "Lista contas configuradas")
            table.add_row("/agents", "Lista agentes configurados")
            table.add_row("/mcp", "Lista servidores MCP configurados")
            table.add_row("/notebooks", "Lista notebooks Jupyter")
            table.add_row("/remote", "Lista integracoes remotas")
            table.add_row("nexus parallel run ...", "Executa varios agentes em paralelo via CLI")
            table.add_row("/tools", "Mostra as ferramentas locais que a IA sabe usar")
            table.add_row("/memory", "Mostra a memoria local salva")
            table.add_row("/remember texto", "Salva uma memoria local manualmente")
            table.add_row("/forget-all", "Apaga toda a memoria local")
            table.add_row("/blocked", "Mostra comandos bloqueados")
            table.add_row("/settings", "Mostra runtime, dry-run e auto-plan")
            table.add_row("/plan on|off", "Liga/desliga preview automatico de plano")
            table.add_row("/dry-run on|off", "Liga/desliga modo dry-run")
            table.add_row("/mode online|hybrid|offline", "Troca o runtime atual")
            table.add_row("/approve", "Executa o plano pendente")
            table.add_row("/cancel", "Cancela plano pendente/execucao atual")
            table.add_row("/clear", "Limpa a tela")
            table.add_row("/exit", "Fecha o terminal")
            self.console.print(table)
            return False
        if command == "/status":
            snap = self.monitor.read()
            self.console.print(
                Panel.fit(
                    f"estado={snap.state}\nmodelo={snap.current_model}\nlatencia={snap.api_latency_ms} ms\n"
                    f"autonomous={snap.autonomous_mode}\n"
                    f"conta={(self.bridge.config.active_account.name if self.bridge.config.active_account else '-')}\n"
                    f"agente={(self.bridge.config.active_agent.name if self.bridge.config.active_agent else '-')}\n"
                    f"mcp={len(self.bridge.config.mcp_servers)}\n"
                    f"notebooks_dir={NexusPaths.notebooks_dir}\n"
                    f"remote={len(self.bridge.config.remote_integrations)} armed={self.bridge.config.remote_armed}",
                    title="Status",
                    border_style="yellow",
                )
            )
            return False
        if command == "/accounts":
            table = Table(title="Contas")
            table.add_column("Ativa", style="cyan", width=5)
            table.add_column("Conta", style="white")
            table.add_column("Provider", style="green")
            table.add_column("Modelo", style="yellow")
            for account in self.bridge.config.accounts:
                table.add_row(
                    "*" if self.bridge.config.active_account_id == account.id else "",
                    account.name,
                    account.provider_label,
                    account.model_name,
                )
            self.console.print(table)
            return False
        if command == "/agents":
            table = Table(title="Agentes")
            table.add_column("Ativo", style="cyan", width=5)
            table.add_column("Agente", style="white")
            table.add_column("Conta", style="green")
            table.add_column("Instrucao", style="yellow")
            for agent in self.bridge.config.agents:
                account = next((item for item in self.bridge.config.accounts if item.id == agent.account_id), None)
                table.add_row(
                    "*" if self.bridge.config.active_agent_id == agent.id else "",
                    agent.name,
                    account.name if account else "-",
                    agent.system_prompt or "-",
                )
            self.console.print(table)
            return False
        if command == "/mcp":
            table = Table(title="Servidores MCP")
            table.add_column("Nome", style="white")
            table.add_column("ID", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Comando", style="yellow")
            for server in self.bridge.config.mcp_servers:
                table.add_row(server.name, server.id, "on" if server.enabled else "off", server.command)
            if not self.bridge.config.mcp_servers:
                self.console.print("[yellow]Nenhum servidor MCP configurado.[/yellow]")
            else:
                self.console.print(table)
            return False
        if command == "/notebooks":
            notebooks = list_notebooks()
            if not notebooks:
                self.console.print("[yellow]Nenhum notebook encontrado.[/yellow]")
                return False
            table = Table(title="Notebooks Jupyter")
            table.add_column("Arquivo", style="white")
            table.add_column("Tamanho", style="cyan")
            table.add_column("Atualizado", style="green")
            for item in notebooks:
                table.add_row(item["relative_path"], str(item["size_bytes"]), item["modified_at"])
            self.console.print(table)
            return False
        if command == "/remote":
            table = Table(title="Integracoes Remotas")
            table.add_column("Nome", style="white")
            table.add_column("Canal", style="cyan")
            table.add_column("Prefixo", style="green")
            table.add_column("Allowlist", style="yellow")
            for integration in self.bridge.config.remote_integrations:
                table.add_row(
                    integration.name,
                    integration.channel,
                    integration.command_prefix,
                    ", ".join(integration.allowed_senders) or "-",
                )
            self.console.print(f"[bold]{'ARMADO' if self.bridge.config.remote_armed else 'DESARMADO'}[/bold]")
            if not self.bridge.config.remote_integrations:
                self.console.print("[yellow]Nenhuma integracao remota configurada.[/yellow]")
            else:
                self.console.print(table)
            return False
        if command in {"/init", "/onboarding"}:
            self._render_onboarding_panel()
            return False
        if command == "/blocked":
            self.console.print("[bold red]Comandos bloqueados por seguranca[/bold red]")
            for reason in blocked_reasons():
                self.console.print(f"- {reason}")
            self.console.print("")
            for example in blocked_examples():
                self.console.print(f"- {example}")
            return False
        if command == "/memory":
            self.console.print(Panel.fit(memory_summary(), title="Memoria Local", border_style="magenta"))
            return False
        if command == "/settings":
            self.console.print(
                Panel.fit(
                    f"runtime={self.bridge.config.runtime_mode}\n"
                    f"dry_run={self.bridge.config.dry_run}\n"
                    f"plan_before_execute={self.bridge.config.plan_before_execute}\n"
                    f"cache={self.bridge.config.llm_cache_enabled}\n"
                    f"max_tool_rounds={self.bridge.config.max_tool_rounds}",
                    title="Settings",
                    border_style="bright_blue",
                )
            )
            return False
        if command in {"/approve", "/run"}:
            self._approve_pending_plan()
            return False
        if command == "/cancel":
            self.cancel_event.set()
            self.pending_plan = None
            self.console.print("[yellow]Plano/execucao marcado como cancelado.[/yellow]")
            return False
        if command.startswith("/plan "):
            value = command.split(" ", 1)[1].strip()
            self.bridge.config.plan_before_execute = value in {"on", "1", "true", "auto"}
            self.console.print(f"[green]plan_before_execute={self.bridge.config.plan_before_execute}[/green]")
            return False
        if command.startswith("/dry-run "):
            value = command.split(" ", 1)[1].strip()
            self.bridge.config.dry_run = value in {"on", "1", "true"}
            self.console.print(f"[green]dry_run={self.bridge.config.dry_run}[/green]")
            return False
        if command.startswith("/mode "):
            value = command.split(" ", 1)[1].strip()
            if value not in {"online", "hybrid", "offline"}:
                self.console.print("[yellow]Use /mode online|hybrid|offline[/yellow]")
                return False
            self.bridge.config.runtime_mode = value
            self.console.print(f"[green]runtime_mode={value}[/green]")
            return False
        if command.startswith("/remember "):
            text = prompt[len("/remember ") :].strip()
            if text:
                remember(text, source="user", kind="manual")
                self.console.print("[green]Memoria salva.[/green]")
            else:
                self.console.print("[yellow]Nada para salvar.[/yellow]")
            return False
        if command == "/forget-all":
            clear_memory()
            self.console.print("[yellow]Memoria local apagada.[/yellow]")
            return False
        if command == "/tools":
            self.console.print(
                Panel.fit(
                    self.bridge.actions.capabilities_summary(),
                    title="Ferramentas do Agente",
                    border_style="green",
                )
            )
            return False
        if command == "/clear":
            self.console.clear()
            self._render_header()
            return False
        if command == "/exit":
            return True
        self.console.print(f"[yellow]Comando desconhecido:[/yellow] {prompt}")
        return False

    def _write_log(self, text: str) -> None:
        self.console.print(f"[dim][LOG][/dim] {text}")

    def _load_history(self) -> list[dict[str, str]]:
        NexusPaths.ensure()
        if not NexusPaths.history_path.exists():
            return []
        try:
            payload = json.loads(NexusPaths.history_path.read_text(encoding="utf-8"))
            return [item for item in payload if isinstance(item, dict) and item.get("role") and item.get("content")]
        except Exception:
            return []

    def _save_history(self) -> None:
        NexusPaths.ensure()
        NexusPaths.history_path.write_text(
            json.dumps(self.conversation[-24:], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
