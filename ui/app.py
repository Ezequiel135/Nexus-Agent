from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import getpass
import json
import threading
from dataclasses import dataclass

from rich.markdown import Markdown
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Footer, Input, RichLog, Static

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
from core.version import APP_VERSION


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
            f"[bold green]NEXUS AGENT {APP_VERSION} — STATUS: [OPERACIONAL][/bold green]   [{color}]{dot}[/{color}]\n"
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
    Screen {
        background: #041019;
        color: #f3fbff;
    }
    #setup-shell {
        width: 1fr;
        height: 1fr;
        overflow-y: auto;
        align-horizontal: center;
    }
    #setup-card {
        width: 1fr;
        max-width: 112;
        height: auto;
        margin: 1 2 2 2;
        padding: 0 0 2 0;
    }
    #setup-hero {
        layout: vertical;
        height: auto;
        border: round #28bff0;
        background: #081621;
        padding: 1 2;
        margin-bottom: 1;
    }
    .setup-brand {
        color: #7ef5c5;
        text-style: bold;
    }
    .setup-title {
        color: #ffffff;
        text-style: bold;
        margin-top: 1;
    }
    .setup-lead {
        color: #a8c7d8;
        margin-top: 1;
    }
    #setup-feedback {
        border: round #244b63;
        background: #0c1c28;
        color: #d9efff;
        padding: 1;
        margin-top: 1;
    }
    #setup-feedback.-error {
        border: round #9f3d47;
        background: #2b1116;
        color: #ffd9dd;
    }
    #setup-feedback.-success {
        border: round #28785c;
        background: #0f241d;
        color: #dffff2;
    }
    #setup-live-status {
        border: round #244b63;
        background: #0c1c28;
        color: #d9efff;
        padding: 1;
        margin-top: 1;
    }
    .setup-section {
        layout: vertical;
        height: auto;
        border: round #235e7e;
        background: #091521;
        padding: 1 2;
        margin-top: 1;
    }
    .setup-section-title {
        color: #67dbff;
        text-style: bold;
        margin-bottom: 1;
    }
    .setup-section-help {
        color: #a8c7d8;
        margin-bottom: 1;
    }
    .setup-label {
        color: #f3fbff;
        text-style: bold;
        margin-top: 1;
    }
    .setup-hint {
        color: #97b4c7;
        margin-bottom: 1;
    }
    .field {
        width: 1fr;
        margin-bottom: 1;
        min-height: 3;
    }
    Input {
        width: 1fr;
        color: #ffffff;
        background: #112231;
        border: round #27536b;
    }
    Input:focus {
        background: #183346;
        border: round #2ee6a6;
    }
    Input > .input--placeholder {
        color: #7f9fb4;
    }
    #custom-provider-wrap {
        layout: vertical;
        height: auto;
        margin-top: 1;
    }
    #setup-actions {
        height: auto;
        margin-top: 1;
    }
    #reset_setup, #submit_setup {
        width: 1fr;
        min-height: 3;
    }
    #reset_setup {
        margin-right: 1;
        background: #102130;
        color: #f3fbff;
        border: round #335b73;
    }
    #submit_setup {
        background: #2ee6a6;
        color: #041410;
        text-style: bold;
        border: none;
    }
    #setup-footer-note {
        color: #97b4c7;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("ctrl+s", "submit_setup", "Salvar"),
        ("ctrl+r", "reset_setup", "Limpar"),
        ("ctrl+c", "quit", "Sair"),
    ]

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="setup-shell"):
            with Vertical(id="setup-card"):
                with Vertical(id="setup-hero"):
                    yield Static(f"NEXUS AGENT {APP_VERSION}", classes="setup-brand")
                    yield Static("Configuracao Inicial", classes="setup-title")
                    yield Static(
                        "Setup simplificado para evitar travamentos: apenas campos de texto, "
                        "rolagem responsiva e validacao direta.",
                        classes="setup-lead",
                    )
                    yield Static(
                        "Digite os valores e use Tab para navegar. Sem menus flutuantes e sem overlay de selecao.",
                        id="setup-feedback",
                    )
                    yield Static("", id="setup-live-status")

                with Vertical(classes="setup-section"):
                    yield Static("Ambiente", classes="setup-section-title")
                    yield Static(
                        "Defina como o Nexus vai abrir e identifique a conta principal desta instalacao.",
                        classes="setup-section-help",
                    )
                    yield Static("Interface inicial", classes="setup-label")
                    yield Static("Valores aceitos: visual ou plain.", classes="setup-hint")
                    yield Input(value="visual", placeholder="visual ou plain", id="ui_mode", classes="field")
                    yield Static("Nome da conta", classes="setup-label")
                    yield Static("Exemplo: Conta principal, Trabalho, Cliente X.", classes="setup-hint")
                    yield Input(value="Conta principal", id="account_name", classes="field")

                with Vertical(classes="setup-section"):
                    yield Static("Provider e Acesso", classes="setup-section-title")
                    yield Static(
                        "Preencha cada caixa com um tipo de dado separado. "
                        "Nao misture API Key, nome do provider e URL no mesmo campo.",
                        classes="setup-section-help",
                    )
                    yield Static("Provider", classes="setup-label")
                    yield Static(
                        "Valores comuns: OpenAI, Anthropic, Google, Ollama, Groq ou Custom.",
                        classes="setup-hint",
                    )
                    yield Input(
                        value="OpenAI",
                        placeholder="OpenAI / Anthropic / Google / Ollama / Groq / Custom",
                        id="provider",
                        classes="field",
                    )
                    with Vertical(id="custom-provider-wrap", classes="setup-section"):
                        yield Static("Provider custom", classes="setup-section-title")
                        yield Static("Obrigatorio apenas quando o provider for Outro / Custom.", classes="setup-section-help")
                        yield Static("Nome/ID do provider custom", classes="setup-label")
                        yield Static("Exemplos: openrouter, azure, provider-interno.", classes="setup-hint")
                        yield Input(
                            placeholder="openrouter / azure / provider interno",
                            id="custom_provider",
                            classes="field",
                        )
                    yield Static("Base URL / Endpoint", classes="setup-label")
                    yield Static(
                        "Opcional para providers padrao e obrigatorio para provider custom.",
                        classes="setup-hint",
                    )
                    yield Input(placeholder="https://api.exemplo.com/v1", id="base_url", classes="field")
                    yield Static("API Key", classes="setup-label")
                    yield Static("Cole somente a chave da conta neste campo.", classes="setup-hint")
                    yield Input(password=True, placeholder="sk-...", id="api_key", classes="field")
                    yield Static("Modelo", classes="setup-label")
                    yield Static("Exemplos: gpt-4o-mini, claude-3-5-sonnet, llama3.", classes="setup-hint")
                    yield Input(
                        placeholder="gpt-4o-mini / claude-3-5-sonnet / llama3",
                        id="model_name",
                        classes="field",
                    )

                with Vertical(classes="setup-section"):
                    yield Static("Perfil do Agente", classes="setup-section-title")
                    yield Static(
                        "O agente pode ter um nome proprio e uma instrucao extra para orientar o comportamento.",
                        classes="setup-section-help",
                    )
                    yield Static("Nome do agente inicial", classes="setup-label")
                    yield Static("Exemplo: Agente principal, Revisor, Automacao.", classes="setup-hint")
                    yield Input(value="Agente principal", id="agent_name", classes="field")
                    yield Static("Instrucao extra do agente", classes="setup-label")
                    yield Static("Opcional. Exemplo: resposta curta, foco em automacao e organizacao.", classes="setup-hint")
                    yield Input(
                        placeholder="Ex: foco em automacao, organizacao e resposta curta",
                        id="agent_prompt",
                        classes="field",
                    )

                with Vertical(classes="setup-section"):
                    yield Static("Seguranca", classes="setup-section-title")
                    yield Static(
                        "Essa senha protege o modo autonomo do Nexus e sera exigida em operacoes sensiveis.",
                        classes="setup-section-help",
                    )
                    yield Static("Senha mestra do Nexus", classes="setup-label")
                    yield Static("Use uma senha que voce consiga lembrar com seguranca.", classes="setup-hint")
                    yield Input(password=True, placeholder="Sua senha mestra", id="password", classes="field")

                with Horizontal(id="setup-actions"):
                    yield Button("Resetar campos", id="reset_setup")
                    yield Button("Salvar configuracao", id="submit_setup")

                yield Static(
                    "Dica: Tab navega entre campos. Enter avanca para o proximo campo. Ctrl+S salva e Ctrl+R limpa.",
                    id="setup-footer-note",
                )
        yield Footer()

    def on_mount(self) -> None:
        self._toggle_custom_provider_fields()
        self._update_setup_summary()
        self.call_after_refresh(self._focus_setup_input)

    def action_submit_setup(self) -> None:
        self._submit_setup()

    def action_reset_setup(self) -> None:
        self.query_one("#ui_mode", Input).value = "visual"
        self.query_one("#account_name", Input).value = "Conta principal"
        self.query_one("#provider", Input).value = "OpenAI"
        self.query_one("#custom_provider", Input).value = ""
        self.query_one("#base_url", Input).value = ""
        self.query_one("#api_key", Input).value = ""
        self.query_one("#model_name", Input).value = ""
        self.query_one("#agent_name", Input).value = "Agente principal"
        self.query_one("#agent_prompt", Input).value = ""
        self.query_one("#password", Input).value = ""
        self._toggle_custom_provider_fields()
        self._update_setup_summary()
        self._set_feedback("Formulario resetado. Digite novamente os valores.", "info")
        self._focus_setup_input()

    def on_input_changed(self, _event: Input.Changed) -> None:
        self._toggle_custom_provider_fields()
        self._update_setup_summary()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit_setup":
            self._submit_setup()
            return
        if event.button.id == "reset_setup":
            self.action_reset_setup()

    def _focus_setup_input(self) -> None:
        self._focus_field("ui_mode")

    def _focus_field(self, field_id: str) -> None:
        self.query_one(f"#{field_id}").focus()

    def _toggle_custom_provider_fields(self) -> None:
        provider = self.query_one("#provider", Input).value or "OpenAI"
        self.query_one("#custom-provider-wrap").display = normalize_provider(provider) == "Custom"

    def _set_feedback(self, message: str, level: str = "info") -> None:
        feedback = self.query_one("#setup-feedback", Static)
        feedback.update(message)
        feedback.remove_class("-error")
        feedback.remove_class("-success")
        if level == "error":
            feedback.add_class("-error")
        elif level == "success":
            feedback.add_class("-success")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "password":
            self._focus_next_setup_field(event.input.id)
            return
        self._submit_setup()

    def _visible_setup_order(self) -> list[str]:
        order = [
            "ui_mode",
            "account_name",
            "provider",
            "custom_provider",
            "base_url",
            "api_key",
            "model_name",
            "agent_name",
            "agent_prompt",
            "password",
            "submit_setup",
        ]
        if normalize_provider(self.query_one("#provider", Input).value or "OpenAI") != "Custom":
            order.remove("custom_provider")
        return order

    def _focus_next_setup_field(self, field_id: str) -> None:
        order = self._visible_setup_order()
        if field_id not in order:
            return
        index = order.index(field_id)
        if index + 1 < len(order):
            self._focus_field(order[index + 1])

    def _update_setup_summary(self) -> None:
        ui_mode = self.query_one("#ui_mode", Input).value.strip().lower() or "visual"
        provider = self.query_one("#provider", Input).value.strip() or "OpenAI"
        custom_provider = self.query_one("#custom_provider", Input).value.strip()
        provider_label = custom_provider if normalize_provider(provider) == "Custom" and custom_provider else provider
        account_name = self.query_one("#account_name", Input).value.strip() or "Conta principal"
        agent_name = self.query_one("#agent_name", Input).value.strip() or "Agente principal"
        model_name = self.query_one("#model_name", Input).value.strip() or "defina um modelo"
        if ui_mode == "visual":
            ui_label = "Visual completa"
        elif ui_mode == "plain":
            ui_label = "Terminal puro"
        else:
            ui_label = ui_mode
        self.query_one("#setup-live-status", Static).update(
            f"UI: {ui_label} | Conta: {account_name} | Agente: {agent_name} | "
            f"Provider: {provider_label} | Modelo: {model_name}"
        )

    def _submit_setup(self) -> None:
        ui_mode = self.query_one("#ui_mode", Input).value.strip().lower() or "visual"
        account_name = self.query_one("#account_name", Input).value.strip() or "Conta principal"
        provider = self.query_one("#provider", Input).value.strip() or "OpenAI"
        custom_provider = self.query_one("#custom_provider", Input).value.strip()
        base_url = self.query_one("#base_url", Input).value.strip()
        api_key = self.query_one("#api_key", Input).value.strip()
        model_name = self.query_one("#model_name", Input).value.strip()
        agent_name = self.query_one("#agent_name", Input).value.strip() or "Agente principal"
        agent_prompt = self.query_one("#agent_prompt", Input).value.strip()
        password = self.query_one("#password", Input).value.strip()

        if ui_mode not in {"visual", "plain"}:
            self._set_feedback("Campo Interface inicial aceita apenas: visual ou plain.", "error")
            self._focus_field("ui_mode")
            return
        if not api_key:
            self._set_feedback("Informe a API Key da conta.", "error")
            self._focus_field("api_key")
            return
        if not model_name:
            self._set_feedback("Informe o modelo principal da conta.", "error")
            self._focus_field("model_name")
            return
        if not password:
            self._set_feedback("Informe a senha mestra do Nexus.", "error")
            self._focus_field("password")
            return
        if normalize_provider(provider) == "Custom" and not custom_provider:
            self._set_feedback("Provider custom exige Nome/ID do provider.", "error")
            self._focus_field("custom_provider")
            return
        if normalize_provider(provider) == "Custom" and not base_url:
            self._set_feedback("Provider custom exige Base URL / Endpoint.", "error")
            self._focus_field("base_url")
            return

        password_hash, salt = create_password_hash(password)
        account = make_account(
            name=account_name,
            provider=provider,
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
        save_config(build_initial_config(password_hash, salt, ui_mode, account, agent))
        self._set_feedback("Configuracao salva com sucesso. Fechando setup...", "success")
        self.exit(SetupPayload(ui_mode, account_name, provider, model_name, agent_name, password))


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
                yield Static("Comandos uteis: onboarding | blocked | accounts | agents | parallel | mcp | notebook | remote", classes="hint-box")
                yield RichLog(id="action-log", markup=True, wrap=True)
        yield StatusBar(self.monitor, self.bridge.config)
        yield Footer()

    def on_mount(self) -> None:
        self.bridge.actions.set_event_callback(lambda text: self.call_from_thread(self._write_log, text))
        self.conversation = self._load_history()
        ok, message = self.bridge.handshake()
        self._write_chat(f"[bold green]NEXUS AGENT {APP_VERSION} ONLINE[/bold green]" if ok else f"[bold red]{message}[/bold red]")
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
        self._write_log("Modo Missao: decomposicao automatica de tarefas. Execucao paralela disponivel via CLI.")
        self.call_after_refresh(self._focus_prompt)
        if self.initial_task:
            self.query_one("#prompt", Input).value = self.initial_task
            self._submit_prompt(self.initial_task)

    def _focus_prompt(self) -> None:
        self.query_one("#prompt", Input).focus()

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
        self._focus_prompt()

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
        finally:
            self.call_from_thread(self._focus_prompt)

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
        finally:
            self.call_from_thread(self._focus_prompt)

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
