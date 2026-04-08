from __future__ import annotations

import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.config import NexusPaths
from core.llm import LiteLLMBridge
from core.logging_utils import log_event
from core.memory import clear_memory, memory_summary, remember
from core.safeguards import blocked_examples, blocked_reasons
from core.state import ActivityMonitor


class PlainNexusCLI:
    def __init__(self, bridge: LiteLLMBridge, monitor: ActivityMonitor, initial_task: str | None = None) -> None:
        self.bridge = bridge
        self.monitor = monitor
        self.initial_task = initial_task
        self.console = Console()
        self.conversation: list[dict[str, str]] = []
        self.bridge.actions.set_event_callback(self._write_log)

    def run(self) -> int:
        self.conversation = self._load_history()
        ok, message = self.bridge.handshake()
        self._render_header()
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
                "[yellow]Modo plain estilo Codex/Claude Code[/yellow]\n"
                "[dim cyan]Criado por Ezequiel 135[/dim cyan]\n"
                "[white]Shell + Files + Vision + Memory + Tool Use[/white]",
                border_style="bright_cyan",
            )
        )
        self.console.print(
            "[dim]Dica: use /help, /tools, /memory, /onboarding, /blocked e /exit[/dim]"
        )

    def _handle_prompt(self, prompt: str) -> None:
        self.console.print(Panel.fit(prompt, title="Voce", border_style="cyan"))
        log_event("PROMPT", prompt)
        remember(prompt, source="user", kind="prompt")
        self.conversation.append({"role": "user", "content": prompt})
        self._save_history()
        try:
            answer, _tool_logs = self.bridge.chat(self.conversation)
            self.conversation.append({"role": "assistant", "content": answer})
            self._save_history()
            self.console.print(Panel.fit(answer or "(sem resposta)", title="NEXUS AGENT", border_style="green"))
        except Exception as exc:
            self.monitor.set_state("error", str(exc))
            self.console.print(Panel.fit(str(exc), title="ERRO", border_style="red"))

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
            table.add_row("/tools", "Mostra as ferramentas locais que a IA sabe usar")
            table.add_row("/memory", "Mostra a memoria local salva")
            table.add_row("/remember texto", "Salva uma memoria local manualmente")
            table.add_row("/forget-all", "Apaga toda a memoria local")
            table.add_row("/blocked", "Mostra comandos bloqueados")
            table.add_row("/clear", "Limpa a tela")
            table.add_row("/exit", "Fecha o terminal")
            self.console.print(table)
            return False
        if command == "/status":
            snap = self.monitor.read()
            self.console.print(
                Panel.fit(
                    f"estado={snap.state}\nmodelo={snap.current_model}\nlatencia={snap.api_latency_ms} ms\nautonomous={snap.autonomous_mode}",
                    title="Status",
                    border_style="yellow",
                )
            )
            return False
        if command in {"/init", "/onboarding"}:
            self.console.print(
                Panel.fit(
                    "Bem-vindo ao NEXUS AGENT.\n\n"
                    "1. Descreva um objetivo natural.\n"
                    "2. O agente decide quando usar shell, arquivos, mouse, teclado e memoria.\n"
                    "3. Use /tools para ver capacidades.\n"
                    "4. Use /memory para ver memoria local.\n"
                    "5. Use /blocked para ver o que nunca sera executado.\n"
                    "6. Use nexus update para atualizar via GitHub.\n"
                    "7. Use nexus uninstall para remover a instalacao local.",
                    title="Onboarding",
                    border_style="bright_cyan",
                )
            )
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
