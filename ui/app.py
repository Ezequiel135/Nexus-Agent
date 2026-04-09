from __future__ import annotations

import getpass
import json
import os
import threading
from dataclasses import dataclass

from rich.markdown import Markdown
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Input, RichLog, Select, Static

from core.actions import AcoesAgente
from core.config import (
    KNOWN_PROVIDERS,
    NexusConfig,
    NexusPaths,
    build_initial_config,
    create_password_hash,
    make_account,
    make_agent,
    normalize_provider,
    save_config,
)
from core.llm import LiteLLMBridge
from core.logging_utils import log_event
from core.state import ActivityMonitor, LIGHT_COLORS, LIGHT_SYMBOLS
from core.safeguards import assess_command_light


def _cpu_and_ram() -> str:
    try:
        import psutil
        return f"CPU {psutil.cpu_percent(interval=0):.0f}% | RAM {psutil.virtual_memory().percent:.0f}%"
    except Exception:
        return "CPU/RAM indisponivel"


@dataclass(slots=True)
class SetupPayload:
    ui_mode: str
    account_name: str
    provider: str
    model_name: str
    agent_name: str
    password: str


class NexusHeader(Static):
    def __init__(self, monitor: ActivityMonitor) -> None:
        super().__init__()
        self.monitor = monitor

    def on_mount(self) -> None:
        self.set_interval(0.3, self.refresh_header)
        self.refresh_header()

    def refresh_header(self) -> None:
        snap = self.monitor.read()
        color = LIGHT_COLORS[snap.state]
        symbol = LIGHT_SYMBOLS[snap.state]
        dot = symbol if snap.pulse_on or snap.state != "acting" else " "
        self.update(
            "[bold cyan]"
            " _   _ ________  _______ _____ \n"
            "| \\ | |  ____\\ \\/ /_   _/ ____|\n"
            "|  \\| | |__   \\  /  | || (___  \n"
            "| . ` |  __|  /  \\  | | \\___ \\ \n"
            "| |\\  | |____/ /\\ \\_| |_ ____) |\n"
            "|_| \\_|______/_/  \\_\\_____|____/[/bold cyan]\n"
            f"[bold green]NEXUS AGENT v2.2 — STATUS: [OPERACIONAL][/bold green]   [{color}]{dot}[/{color}]\n"
            "[dim cyan]Criado por Ezequiel 135[/dim cyan]"
        )


class StatusBar(Static):
    def __init__(self, monitor: ActivityMonitor, config: NexusConfig | None = None) -> None:
        super().__init__()
        self.monitor = monitor
        self.config = config

    def on_mount(self) -> None:
        self.set_interval(1.0, self.refresh_status)
        self.refresh_status()

    def refresh_status(self) -> None:
        snap = self.monitor.read()
        mode = "MISSION_MODE=ON" if snap.autonomous_mode else "AUTO=OFF"
        account_name = self.config.active_account.name if self.config and self.config.active_account else "-"
        agent_name = self.config.active_agent.name if self.config and self.config.active_agent else "-"
        self.update(
            f"[black on bright_cyan] Modelo: {snap.current_model} | Latencia: {snap.api_latency_ms} ms | "
            f"{_cpu_and_ram()} | conta={account_name} | agente={agent_name} | {mode} | Ezequiel 135 [/]"
        )


class SetupApp(App[SetupPayload | None]):
    CSS = """
    Screen { background: black; color: white; }
    #setup-wrap { width: 108; height: auto; border: round cyan; padding: 1 2; margin: 1 2; }
    .setup-title { color: ansi_bright_green; text-style: bold; }
    .field { margin-bottom: 1; width: 1fr; height: 3; }
    .setup-section { border: round #245c7a; padding: 1; margin-bottom: 1; background: #0b1722; }
    .setup-section-title { color: ansi_bright_cyan; text-style: bold; margin-bottom: 1; }
    .setup-help { color: #a8c7d8; margin-bottom: 1; }
    Input, Select { width: 1fr; color: white; background: #111923; border: round #245c7a; }
    Input:focus, Select:focus { background: #162430; border: round #2ee6a6; }
    .hidden { display: none; }
    """

    BINDINGS = [("ctrl+c", "quit", "Sair")]

    def compose(self) -> ComposeResult:
        provider_options = []
        for provider in KNOWN_PROVIDERS:
            label = "Outro / Custom" if provider == "Custom" else provider
            provider_options.append((label, provider))
        yield Container(
            Static("NEXUS AGENT SETUP OBRIGATORIO", classes="setup-title"),
            Static(
                "Preencha cada caixa com um tipo de dado separado. "
                "Nao misture API Key com URL.",
                classes="setup-help",
            ),
            Static("Tipo de UI"),
            Select(
                [
                    ("Visual completa", "visual"),
                    ("Terminal puro", "plain"),
                ],
                value="visual",
                id="ui_mode",
                classes="field",
            ),
            Static("Nome da conta"),
            Input(value="Conta principal", id="account_name", classes="field"),
            Static("Provider"),
            Select(
                provider_options,
                value="OpenAI",
                id="provider",
                classes="field",
            ),
            Container(
                Static("Provider custom / Outro", classes="setup-section-title"),
                Static(
                    "Se escolheu Outro / Custom, preencha os campos abaixo separadamente.",
                    classes="setup-help",
                ),
                Static("Nome/ID do provider custom"),
                Static(
                    "Coloque aqui somente o nome/ID do provider. Ex: openrouter, azure, provider-interno.",
                    classes="setup-help",
                ),
                Input(placeholder="openai / openrouter / provider interno", id="custom_provider", classes="field"),
                Static("Base URL / Endpoint"),
                Static(
                    "Coloque aqui somente a URL base/endpoint. Ex: https://api.exemplo.com/v1",
                    classes="setup-help",
                ),
                Input(placeholder="https://api.exemplo.com/v1", id="base_url", classes="field"),
                id="custom-provider-wrap",
                classes="setup-section",
            ),
            Container(
                Static("Credenciais da conta", classes="setup-section-title"),
                Static("API Key"),
                Static(
                    "Coloque aqui somente a API Key da conta. Nao coloque URL neste campo.",
                    classes="setup-help",
                ),
                Input(password=True, id="api_key", classes="field"),
                id="api-key-wrap",
                classes="setup-section",
            ),
            Static("Model Name"),
            Input(placeholder="gpt-4o-mini / claude-3-5-sonnet / llama3", id="model_name", classes="field"),
            Static("Nome do agente inicial"),
            Input(value="Agente principal", id="agent_name", classes="field"),
            Static("Instrucao extra do agente (opcional)"),
            Input(placeholder="Ex: foco em automacao, organizacao e resposta curta", id="agent_prompt", classes="field"),
            Static("NEXUS Password"),
            Input(password=True, id="password", classes="field"),
            Static("Pressione Enter no campo de senha para concluir."),
            id="setup-wrap",
        )

    def on_mount(self) -> None:
        self._toggle_custom_provider_fields()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "provider":
            self._toggle_custom_provider_fields()

    def _toggle_custom_provider_fields(self) -> None:
        provider = str(self.query_one("#provider", Select).value or "OpenAI")
        self.query_one("#custom-provider-wrap", Container).display = normalize_provider(provider) == "Custom"

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "password":
            return
        ui_mode = self.query_one("#ui_mode", Select).value or "visual"
        account_name = self.query_one("#account_name", Input).value.strip() or "Conta principal"
        provider = self.query_one("#provider", Select).value or "OpenAI"
        custom_provider = self.query_one("#custom_provider", Input).value.strip()
        base_url = self.query_one("#base_url", Input).value.strip()
        api_key = self.query_one("#api_key", Input).value.strip()
        model_name = self.query_one("#model_name", Input).value.strip()
        agent_name = self.query_one("#agent_name", Input).value.strip() or "Agente principal"
        agent_prompt = self.query_one("#agent_prompt", Input).value.strip()
        password = self.query_one("#password", Input).value.strip()
        if not api_key or not model_name or not password:
            self.notify("Preencha conta, provider, API key, model, agente e senha.")
            return
        if normalize_provider(str(provider)) == "Custom" and not custom_provider:
            self.notify("Provider custom exige Nome/ID do provider.")
            return
        if normalize_provider(str(provider)) == "Custom" and not base_url:
            self.notify("Provider custom exige Base URL / Endpoint.")
            return
        password_hash, salt = create_password_hash(password)
        account = make_account(
            name=account_name,
            provider=str(provider),
            api_key=api_key,
            model_name=model_name,
            base_url=base_url,
            custom_provider=custom_provider,
        )
        agent = make_agent(
            name=agent_name,
            account_id=account.id,
            system_prompt=agent_prompt,
        )
        save_config(build_initial_config(password_hash, salt, str(ui_mode), account, agent))
        self.exit(SetupPayload(str(ui_mode), account_name, str(provider), model_name, agent_name, password))


class MissionPanel(Static):
    """Shows current mission plan and step progress."""
    pass


class GreenLightBar(Static):
    """Visual indicator of safety status."""
    def __init__(self):
        super().__init__()
        self.status = "🟢 LUZ VERDE — ambiente seguro"
        self.can_focus = False

    def set_status(self, status: str, emoji: str = "🟢") -> None:
        self.status = f"{emoji} {status}"
        self.refresh()

    def render(self) -> str:
        return self.status


class NexusApp(App[None]):
    CSS = """
    Screen { background: #05070a; color: white; }
    #body { height: 1fr; padding: 0 1; }
    #chat-panel { width: 1fr; border: round #2ee6a6; margin-right: 1; padding: 0 1; background: #071018; }
    #log-panel { width: 40; border: round #24c8ff; padding: 0 1; background: #08111a; }
    #chat-log, #action-log { height: 1fr; }
    #prompt { dock: bottom; margin-top: 1; }
    .panel-title { color: bright_cyan; text-style: bold; }
    .hint-box { color: white; background: #0b1722; border: round #245c7a; padding: 0 1; margin-bottom: 1; }
    #mission-panel { height: auto; border: round bright_magenta; margin-bottom: 1; padding: 1; background: #12081a; }
    #light-bar { text-style: bold; dock: top; height: 1; content-align: center middle; background: #0a2a0a; }
    """

    BINDINGS = [("ctrl+c", "quit", "Sair"), ("ctrl+m", "mission_mode", "Modo Missao")]

    def __init__(self, bridge: LiteLLMBridge, monitor: ActivityMonitor, initial_task: str | None = None) -> None:
        super().__init__()
        self.bridge = bridge
        self.monitor = monitor
        self.initial_task = initial_task
        self.conversation: list[dict[str, str]] = []
        self.mission_mode = False

    def compose(self) -> ComposeResult:
        yield GreenLightBar(id="light-bar")
        yield NexusHeader(self.monitor)
        yield MissionPanel("", id="mission-panel")
        with Horizontal(id="body"):
            with Vertical(id="chat-panel"):
                yield Static("Conversation", classes="panel-title")
                yield Static("Descreva o objetivo. O agente usa shell, arquivos, tela, memoria, MCP e notebooks automaticamente.", classes="hint-box")
                yield RichLog(id="chat-log", markup=True, wrap=True)
                yield Input(placeholder="Digite um objetivo ou comando para o Nexus...", id="prompt")
            with Vertical(id="log-panel"):
                yield Static("Action & Log Panel", classes="panel-title")
                yield Static("Comandos uteis: onboarding | blocked | update | accounts | agents | mcp | notebook | remote", classes="hint-box")
                yield RichLog(id="action-log", markup=True, wrap=True)
        yield StatusBar(self.monitor, self.bridge.config)
        yield Footer()

    def on_mount(self) -> None:
        self.bridge.actions.set_event_callback(lambda text: self.call_from_thread(self._write_log, text))
        self.conversation = self._load_history()
        ok, message = self.bridge.handshake()
        self._write_chat("[bold green]NEXUS AGENT v2.2 ONLINE[/bold green]" if ok else f"[bold red]{message}[/bold red]")
        self._write_chat(
            "Use esta interface como um agente autonomo. "
            "Descreva um objetivo (ex: 'organiza minha pasta Downloads') e o NEXUS PLANEJA + EXECUTA."
        )
        self._write_log(message)
        if self.bridge.config.active_account is not None:
            self._write_log(f"Conta ativa: {self.bridge.config.active_account.name}")
        if self.bridge.config.active_agent is not None:
            self._write_log(f"Agente ativo: {self.bridge.config.active_agent.name}")
        if self.bridge.config.mcp_servers:
            self._write_log(f"MCP ativo: {len(self.bridge.config.mcp_servers)} servidor(es) configurado(s)")
        if self.bridge.config.remote_integrations:
            state = "ARMADO" if self.bridge.config.remote_armed else "DESARMADO"
            self._write_log(f"Remote bots: {len(self.bridge.config.remote_integrations)} integracao(oes) | {state}")
        self._write_log(f"Notebook root: {NexusPaths.notebooks_dir}")
        self._write_log("Modo Missao: decomposicao automatica de tarefas. Marca d'agua: Ezequiel 135")
        if self.initial_task:
            self.query_one("#prompt", Input).value = self.initial_task
            self._submit_prompt(self.initial_task)

    def _write_chat(self, text: str) -> None:
        self.query_one("#chat-log", RichLog).write(Markdown(text))

    def _write_log(self, text: str) -> None:
        self.query_one("#action-log", RichLog).write(text)

    def _set_light(self, assessment: str) -> None:
        light = self.query_one("#light-bar", GreenLightBar)
        if "Vermelha" in assessment or "Bloqueado" in assessment:
            light.set_status(assessment, "🔴")
        elif "Amarela" in assessment or "Atencao" in assessment:
            light.set_status(assessment, "🟡")
        else:
            light.set_status(assessment, "🟢")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "prompt":
            return
        prompt = event.value.strip()
        event.input.value = ""
        if prompt:
            self._submit_prompt(prompt)

    def _submit_prompt(self, prompt: str) -> None:
        self._write_chat(f"**Você:** {prompt}")
        # Se o prompt parece uma tarefa complexa, ativa mission mode
        if len(prompt.split()) > 4 or any(w in prompt.lower() for w in ["organizar", "criar", "baixar", "instalar", "configurar", "buscar", "processar"]):
            self.mission_mode = True
            threading.Thread(target=self._process_plan, args=(prompt,), daemon=True).start()
        else:
            self.mission_mode = False
            threading.Thread(target=self._process_simple, args=(prompt,), daemon=True).start()

    def _process_simple(self, prompt: str) -> None:
        try:
            log_event("PROMPT", prompt)
            self.conversation.append({"role": "user", "content": prompt})
            self._save_history()
            answer, tool_logs = self.bridge.chat(self.conversation)
            self.conversation.append({"role": "assistant", "content": answer})
            self._save_history()
            self.call_from_thread(self._write_chat, answer)
            for item in tool_logs:
                self.call_from_thread(self._write_log, item)
            if not tool_logs:
                self.call_from_thread(self._write_log, "Nenhuma ferramenta local usada.")
        except Exception as exc:
            self.monitor.set_state("error", str(exc))
            self.call_from_thread(self._write_chat, f"**ERRO:** {exc}")
            self.call_from_thread(self._write_log, f"[ERROR] {exc}")

    def _process_plan(self, prompt: str) -> None:
        try:
            log_event("MISSION", prompt)
            self.call_from_thread(self._write_chat, f"[bold cyan]🎯 MODO MISSAO ATIVADO[/bold cyan]")
            self.call_from_thread(self._write_chat, f"[dim]Criando plano para: {prompt}[/dim]")

            result = self.bridge.chat_with_plan(prompt)

            goal = result.get("goal", "")
            steps = result.get("results", [])
            summary = result.get("summary", "")

            # Mostra o plano
            plan_lines = ["[bold yellow]📋 PLANO:[/bold yellow]"]
            for s in steps:
                plan_lines.append(f"  {s['step']}. {s['task']}")
                if s.get("tool"):
                    plan_lines.append(f"     [cyan]→ {s['tool']}({s.get('args', {})})[/cyan]")
            self.call_from_thread(self._write_chat, "\n".join(plan_lines))

            # Executa cada passo — cada passo gera log proprio
            self.call_from_thread(self._write_chat, f"[bold green]🚀 EXECUTANDO {len(steps)} PASSOS...[/bold green]")

            all_logs: list[str] = []
            for s in steps:
                log_line = f" PASSO {s['step']}/{len(steps)}: {s['task'][:60]}"
                self.call_from_thread(self._write_log, f"[bold yellow]▶{log_line}[/bold yellow]")

                # Verifica luz verde para comandos shell
                if s.get("tool") == "executar_comando":
                    cmd = s.get("args", {}).get("comando", "")
                    assessment = assess_command_light(cmd)
                    self.call_from_thread(self._set_light, assessment)
                    if "Vermelha" in assessment or "Bloqueado" in assessment:
                        err = f"🚫 {assessment} — comando nao executado"
                        self.call_from_thread(self._write_log, f"[bold red]{err}[/bold red]")
                        s["result"] = err
                        s["status"] = "BLOCKED"
                        continue

                tool_name = s.get("tool")
                args = s.get("args") or {}
                try:
                    r = self.bridge.actions.executar(tool_name, args) if tool_name else f"[livre] {s.get('task','')}"
                    s["result"] = str(r)[:200]
                    s["status"] = "OK"
                    all_logs.append(f"{tool_name or 'acao'}({args})")
                except Exception as e:
                    s["result"] = f"Erro: {e}"
                    s["status"] = "FAIL"
                    all_logs.append(f"ERRO: {e}")

            # Volta luz verde
            self.call_from_thread(self._set_light, "🟢 LUZ VERDE — missao concluida")
            self.call_from_thread(self._write_chat, f"[bold green]✅ {summary}[/bold green]")

            # Salva na memoria
            from core.memory import remember
            remember(f"Missao: {prompt} — {len(steps)} passos executados", kind="mission")

            # Log final
            self.call_from_thread(self._write_log, f"[bold green]MISSION COMPLETE: {len(steps)} etapas[/bold green]")

        except Exception as exc:
            self.monitor.set_state("error", str(exc))
            self.call_from_thread(self._set_light, f"🔴 ERRO: {exc}", "🔴")
            self.call_from_thread(self._write_chat, f"**ERRO:** {exc}")
            self.call_from_thread(self._write_log, f"[ERROR] {exc}")

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


def password_gate(prompt_label: str = "Nexus Password: ") -> str:
    if os.environ.get("NEXUS_PASSWORD"):
        return os.environ["NEXUS_PASSWORD"]
    return getpass.getpass(prompt_label)


def build_runtime(config: NexusConfig, monitor: ActivityMonitor) -> LiteLLMBridge:
    actions = AcoesAgente(config)
    return LiteLLMBridge(config, monitor, actions)
