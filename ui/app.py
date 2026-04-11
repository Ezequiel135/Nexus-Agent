from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import getpass
import json
import threading
import time
from dataclasses import dataclass
from typing import Any

from rich.markdown import Markdown
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Footer, Input, RichLog, Static

from core.actions import AcoesAgente, CancelledExecution
from core.config import (
    KNOWN_PROVIDERS,
    NexusConfig,
    NexusPaths,
    build_initial_config,
    create_password_hash,
    make_account,
    make_agent,
    normalize_provider,
    normalize_runtime_mode,
    normalize_execution_profile,
    provider_requires_api_key,
    save_config,
)
from core.execution import apply_execution_profile, profile_description, profile_label, should_preview_plan
from core.llm import LiteLLMBridge
from core.logging_utils import log_event
from core.memory import clear_memory, memory_summary, remember
from core.state import ActivityMonitor, LIGHT_COLORS, LIGHT_SYMBOLS
from core.safeguards import blocked_examples, blocked_reasons
from core.transcript import background_interaction, bullet, format_activity_log, transcript_event, worked_banner
from core.update_check import DEFAULT_UPDATE_COMMAND, UpdateInfo, check_for_update, installed_repo_url
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
    runtime_mode: str
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
        mode = "MISSION_MODE=ON" if getattr(snap, "autonomous_mode", False) else "AUTO=OFF"
        account_name = self.config.active_account.name if self.config and self.config.active_account else "-"
        agent_name = self.config.active_agent.name if self.config and self.config.active_agent else "-"
        runtime_mode = getattr(self.config, "runtime_mode", "-") if self.config else "-"
        current_step = getattr(snap, "current_step", 0)
        total_steps = getattr(snap, "total_steps", 0)
        progress = f" | passo={current_step}/{total_steps}" if total_steps else ""
        detail_text = getattr(snap, "detail", "")
        detail = f" | {detail_text}" if detail_text else ""
        cancel = " | Esc cancela" if getattr(snap, "cancellable", False) else ""
        self.update(
            f"[black on bright_cyan] Modelo: {getattr(snap, 'current_model', '-')} | Latencia: {getattr(snap, 'api_latency_ms', 0)} ms | "
            f"{_cpu_and_ram()} | runtime={runtime_mode} | conta={account_name} | agente={agent_name} | "
            f"{mode}{progress}{detail}{cancel} | Ezequiel 135 [/]"
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
                    yield Static("Runtime", classes="setup-label")
                    yield Static("Valores aceitos: hybrid, offline ou online.", classes="setup-hint")
                    yield Input(value="hybrid", placeholder="hybrid / offline / online", id="runtime_mode", classes="field")
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
        self.query_one("#runtime_mode", Input).value = "hybrid"
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
            "runtime_mode",
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
        runtime_mode = normalize_runtime_mode(self.query_one("#runtime_mode", Input).value.strip().lower() or "hybrid")
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
            f"Runtime: {runtime_mode} | Provider: {provider_label} | Modelo: {model_name}"
        )

    def _submit_setup(self) -> None:
        ui_mode = self.query_one("#ui_mode", Input).value.strip().lower() or "visual"
        runtime_mode = normalize_runtime_mode(self.query_one("#runtime_mode", Input).value.strip().lower() or "hybrid")
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
        if runtime_mode not in {"online", "hybrid", "offline"}:
            self._set_feedback("Campo Runtime aceita apenas: hybrid, offline ou online.", "error")
            self._focus_field("runtime_mode")
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
        if provider_requires_api_key(provider, base_url, runtime_mode=runtime_mode) and not api_key:
            self._set_feedback("Informe a API Key da conta para esse provider/runtime.", "error")
            self._focus_field("api_key")
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
        save_config(build_initial_config(password_hash, salt, ui_mode, account, agent, runtime_mode=runtime_mode))
        self._set_feedback("Configuracao salva com sucesso. Fechando setup...", "success")
        self.exit(SetupPayload(ui_mode, runtime_mode, account_name, provider, model_name, agent_name, password))


class MissionPanel(Static):
    def set_text(self, text: str) -> None:
        self.update(text)


class GreenLightBar(Static):
    """Visual indicator of safety status."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
    .panel-title { color: #24c8ff; text-style: bold; }
    .hint-box { color: white; background: #0b1722; border: round #245c7a; padding: 0 1; margin-bottom: 1; }
    #mission-panel { height: auto; border: round #ff4fd8; margin-bottom: 1; padding: 1; background: #12081a; }
    #light-bar { text-style: bold; dock: top; height: 1; content-align: center middle; background: #0a2a0a; }
    #startup-overlay {
        layer: overlay;
        width: 1fr;
        height: 1fr;
        align: center middle;
        background: rgba(3, 6, 10, 0.94);
    }
    #startup-card {
        width: 88;
        max-width: 96%;
        height: auto;
        border: round #24c8ff;
        background: #091521;
        padding: 1 2;
    }
    #startup-brand {
        color: #7ef5c5;
        text-style: bold;
    }
    #startup-title {
        color: #ffffff;
        text-style: bold;
        margin-top: 1;
    }
    #startup-lead {
        color: #b1d5e5;
        margin-top: 1;
    }
    #startup-status {
        border: round #245c7a;
        background: #0c1b28;
        color: #dff3ff;
        padding: 1;
        margin-top: 1;
    }
    #startup-actions {
        height: auto;
        margin-top: 1;
    }
    .mode-button {
        width: 1fr;
        min-height: 5;
        margin-right: 1;
    }
    #profile_quick {
        background: #2ee6a6;
        color: #041410;
        border: none;
        text-style: bold;
    }
    #profile_planned {
        background: #122637;
        color: #f3fbff;
        border: round #24c8ff;
        text-style: bold;
    }
    #startup-note {
        color: #94b5c9;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Sair"),
        ("ctrl+m", "mission_mode", "Auto Plan"),
        ("ctrl+l", "show_launcher", "Launcher"),
        ("escape", "cancel_current", "Cancelar"),
    ]

    def __init__(self, bridge: LiteLLMBridge, monitor: ActivityMonitor, initial_task: str | None = None) -> None:
        super().__init__()
        self.bridge = bridge
        self.monitor = monitor
        self.initial_task = initial_task
        self.conversation: list[dict[str, str]] = []
        self.mission_mode = False
        self.pending_plan: dict[str, Any] | None = None
        self.cancel_event = threading.Event()
        self.worker_thread: threading.Thread | None = None
        self.startup_ready = False
        self.launcher_visible = initial_task is None
        self._loading_frame = 0
        self._loading_base = "Carregando modulos, contexto e sessao"
        self.task_started_at: float | None = None
        self.update_info: UpdateInfo | None = None

    def compose(self) -> ComposeResult:
        yield GreenLightBar(id="light-bar")
        yield NexusHeader(self.monitor)
        yield MissionPanel("Sem plano pendente. Use /help para ver atalhos locais.", id="mission-panel")
        with Horizontal(id="body"):
            with Vertical(id="chat-panel"):
                yield Static("Conversation", classes="panel-title")
                yield Static(
                    "Descreva o objetivo ou use /help. O agente mostra plano, progresso, dry-run e aprovacoes como Codex/Claude Code.",
                    classes="hint-box",
                )
                yield RichLog(id="chat-log", markup=True, wrap=True)
                yield Input(placeholder="Digite um objetivo ou comando para o Nexus...", id="prompt")
            with Vertical(id="log-panel"):
                yield Static("Action & Log Panel", classes="panel-title")
                yield Static(
                    "Comandos uteis: /help, /approve, /cancel, /settings, /mode offline, /dry-run off",
                    classes="hint-box",
                )
                yield RichLog(id="action-log", markup=True, wrap=True)
        with Container(id="startup-overlay"):
            with Vertical(id="startup-card"):
                yield Static(f"NEXUS AGENT {APP_VERSION}", id="startup-brand")
                yield Static("Inicializando sessao visual", id="startup-title")
                yield Static(
                    "A interface abre primeiro com uma tela de carregamento e depois oferece o modo Dia a dia ou Profissional.",
                    id="startup-lead",
                )
                yield Static("Carregando...", id="startup-status")
                with Horizontal(id="startup-actions"):
                    yield Button("Dia a dia\nMenos passos", id="profile_quick", classes="mode-button")
                    yield Button("Profissional\nPlanejamento completo", id="profile_planned", classes="mode-button")
                yield Static(
                    "Dia a dia reduz etapas para tarefas simples. Profissional mantem preview de plano e fluxo completo.",
                    id="startup-note",
                )
        yield StatusBar(self.monitor, self.bridge.config)
        yield Footer()

    def on_mount(self) -> None:
        self.bridge.actions.set_event_callback(lambda text: self.call_from_thread(self._write_log, text))
        if hasattr(self.bridge.actions, "set_cancel_event"):
            self.bridge.actions.set_cancel_event(self.cancel_event)
        self.query_one("#chat-log", RichLog).can_focus = False
        self.query_one("#action-log", RichLog).can_focus = False
        self.query_one("#startup-actions", Horizontal).display = False
        self.set_interval(0.25, self._tick_startup)
        self.call_after_refresh(self._focus_startup_target)
        threading.Thread(target=self._bootstrap_session, daemon=True).start()

    def _focus_prompt(self) -> None:
        self.query_one("#prompt", Input).focus()

    def _focus_startup_target(self) -> None:
        if self.launcher_visible and self.startup_ready:
            self.query_one("#profile_quick", Button).focus()
            return
        if self.launcher_visible:
            self.query_one("#startup-overlay", Container).focus()
            return
        self._focus_prompt()

    def _tick_startup(self) -> None:
        if self.startup_ready:
            return
        self._loading_frame = (self._loading_frame + 1) % 4
        dots = "." * (self._loading_frame + 1)
        self.query_one("#startup-status", Static).update(f"{self._loading_base}{dots}")

    def _bootstrap_session(self) -> None:
        self.conversation = self._load_history()
        ok, message = self.bridge.handshake()
        self.call_from_thread(self._finish_bootstrap, ok, message)

    def _finish_bootstrap(self, ok: bool, message: str) -> None:
        self.startup_ready = True
        self._write_chat(f"[bold green]NEXUS AGENT {APP_VERSION} ONLINE[/bold green]" if ok else f"[bold red]{message}[/bold red]")
        self._write_chat(
            "Use esta interface como um agente local com preview de plano, dry-run e cancelamento. "
            "Prompts complexos podem gerar um plano antes da execucao; aprove com `/approve`."
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
        self._write_log("Auto plan, dry-run e cancelamento por Esc habilitados. Execucao paralela disponivel via CLI.")
        self._start_update_check()
        if self.initial_task:
            self.launcher_visible = False
            self.query_one("#startup-overlay", Container).display = False
            self.call_after_refresh(self._focus_prompt)
            self.set_timer(0.05, self._focus_prompt)
            self.query_one("#prompt", Input).value = self.initial_task
            self._submit_prompt(self.initial_task)
            return
        self._show_launcher()

    def _show_launcher(self) -> None:
        profile = normalize_execution_profile(getattr(self.bridge.config, "execution_profile", "planned"))
        self.launcher_visible = True
        self.query_one("#startup-overlay", Container).display = True
        self.query_one("#startup-title", Static).update("Escolha o foco desta sessao")
        self.query_one("#startup-status", Static).update(
            f"Conta: {(self.bridge.config.active_account.name if self.bridge.config.active_account else '-')} | "
            f"Perfil salvo: {profile_label(profile)} | Runtime: {getattr(self.bridge.config, 'runtime_mode', '-')}"
        )
        self.query_one("#startup-actions", Horizontal).display = True
        self.query_one("#startup-note", Static).update(
            f"Atual: {profile_label(profile)}. {profile_description(profile)} "
            "Voce pode reabrir esta tela com Ctrl+L ou /launcher."
        )
        self.call_after_refresh(self._focus_startup_target)

    def _close_launcher(self) -> None:
        self.launcher_visible = False
        self.query_one("#startup-overlay", Container).display = False
        self._set_mission_panel(
            f"Perfil atual: {profile_label(getattr(self.bridge.config, 'execution_profile', 'planned'))} | "
            f"dry_run={self.bridge.config.dry_run} | runtime={self.bridge.config.runtime_mode}"
        )
        self.call_after_refresh(self._focus_prompt)
        self.set_timer(0.05, self._focus_prompt)

    def _write_chat(self, text: str) -> None:
        self.query_one("#chat-log", RichLog).write(Markdown(text))

    def _write_log(self, text: str) -> None:
        rendered = format_activity_log(text)
        if rendered:
            self.query_one("#action-log", RichLog).write(rendered)

    def _start_task_log(self, message: str) -> None:
        self.task_started_at = time.monotonic()
        self._write_log(message)

    def _finish_task_log(self, message: str) -> None:
        started_at = self.task_started_at
        self.task_started_at = None
        if started_at is None:
            return
        self.query_one("#action-log", RichLog).write("")
        self.query_one("#action-log", RichLog).write(worked_banner(time.monotonic() - started_at))
        self.query_one("#action-log", RichLog).write("")
        self._write_log(message)

    def _set_mission_panel(self, text: str) -> None:
        self.query_one("#mission-panel", MissionPanel).set_text(text)

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
        if prompt.startswith("/"):
            self._handle_slash(prompt)
            return
        if self._worker_running():
            self._write_log("[WARN] Ja existe uma execucao em andamento. Pressione Esc para cancelar.")
            return
        if self._should_preview_plan(prompt):
            self.mission_mode = True
            self._start_task_log("Vou montar um plano antes de executar e mostrar os passos conforme avancar.")
            self._start_worker(self._process_plan_preview, prompt)
        else:
            self.mission_mode = False
            self._start_task_log("Vou executar essa tarefa e mostrar os passos conforme avancar.")
            self._start_worker(self._process_simple, prompt)

    def _worker_running(self) -> bool:
        return bool(self.worker_thread and self.worker_thread.is_alive())

    def _start_worker(self, target, *args) -> None:
        self.cancel_event.clear()
        self.worker_thread = threading.Thread(target=target, args=args, daemon=True)
        self.worker_thread.start()

    def _should_preview_plan(self, prompt: str) -> bool:
        return should_preview_plan(self.bridge.config, prompt)

    def action_mission_mode(self) -> None:
        self.bridge.config.plan_before_execute = not self.bridge.config.plan_before_execute
        self._write_log(f"plan_before_execute={self.bridge.config.plan_before_execute}")
        self._set_mission_panel(
            f"Auto plan {'ativado' if self.bridge.config.plan_before_execute else 'desativado'} | "
            f"dry_run={self.bridge.config.dry_run} | runtime={self.bridge.config.runtime_mode}"
        )

    def action_show_launcher(self) -> None:
        if not self.startup_ready or self._worker_running():
            return
        self._show_launcher()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "profile_quick":
            self._apply_profile_and_enter("quick")
            return
        if event.button.id == "profile_planned":
            self._apply_profile_and_enter("planned")

    def _apply_profile_and_enter(self, profile: str) -> None:
        normalized = apply_execution_profile(self.bridge.config, profile)
        save_config(self.bridge.config)
        self._write_log(f"Perfil de execucao: {profile_label(normalized)}")
        self._close_launcher()

    def action_cancel_current(self) -> None:
        self.cancel_event.set()
        self.pending_plan = None
        self.monitor.set_state("idle", detail="Execucao cancelada pelo usuario.")
        self.monitor.set_cancellable(False)
        self._set_mission_panel("Execucao/plano cancelado. Nenhuma acao pendente.")
        self._write_log("[WARN] Cancelamento solicitado pelo usuario.")
        self._finish_task_log("Execucao cancelada.")

    def _handle_slash(self, prompt: str) -> None:
        command = prompt.strip().lower()
        if command == "/help":
            self._write_chat(
                "\n".join(
                    [
                        "**Comandos locais**",
                        "- `/help` ajuda",
                        "- `/settings` runtime/dry-run/auto-plan",
                        "- `/profile quick|planned` alterna Dia a dia e Profissional",
                        "- `/launcher` reabre a tela inicial",
                        "- `/plan on|off` liga/desliga preview automatico",
                        "- `/dry-run on|off` liga/desliga dry-run",
                        "- `/mode online|hybrid|offline` troca runtime atual",
                        "- `/sudo status|on|off|log on|off` controla sudo temporario",
                        "- `/root on|confirm|off|status` controla root temporario",
                        "- `/approve` executa plano pendente",
                        "- `/cancel` cancela plano pendente/execucao",
                        "- `/status`, `/tools`, `/memory`, `/blocked`, `/accounts`, `/agents`, `/mcp`, `/remote`, `/clear`",
                    ]
                )
            )
            return
        if command == "/status":
            snap = self.monitor.read()
            self._write_chat(
                "\n".join(
                    [
                        "**Status**",
                        f"- state={snap.state}",
                        f"- runtime={self.bridge.config.runtime_mode}",
                        f"- profile={profile_label(getattr(self.bridge.config, 'execution_profile', 'planned'))}",
                        f"- dry_run={self.bridge.config.dry_run}",
                        f"- plan_before_execute={self.bridge.config.plan_before_execute}",
                        f"- privilege={self.bridge.actions.privilege_status().summary()}",
                        f"- update={(self.update_info.message if self.update_info else 'checando...')}",
                        f"- model={snap.current_model}",
                        f"- detail={snap.detail or '-'}",
                    ]
                )
            )
            return
        if command == "/settings":
            self._write_chat(
                "\n".join(
                    [
                        "**Settings**",
                        f"- runtime={self.bridge.config.runtime_mode}",
                        f"- execution_profile={getattr(self.bridge.config, 'execution_profile', 'planned')}",
                        f"- dry_run={self.bridge.config.dry_run}",
                        f"- plan_before_execute={self.bridge.config.plan_before_execute}",
                        f"- llm_cache_enabled={self.bridge.config.llm_cache_enabled}",
                        f"- max_tool_rounds={self.bridge.config.max_tool_rounds}",
                        f"- max_output_tokens={self.bridge.config.max_output_tokens}",
                        f"- privilege={self.bridge.actions.privilege_status().summary()}",
                        f"- update_message={(self.update_info.message if self.update_info else 'checando...')}",
                    ]
                )
            )
            return
        if command == "/launcher":
            self.action_show_launcher()
            return
        if command in {"/approve", "/run"}:
            if self.pending_plan is None:
                self._write_log("Nenhum plano pendente para executar.")
                return
            if self._worker_running():
                self._write_log("Ja existe uma execucao em andamento.")
                return
            self._start_worker(self._execute_pending_plan)
            return
        if command == "/cancel":
            self.action_cancel_current()
            return
        if command.startswith("/plan "):
            value = command.split(" ", 1)[1].strip()
            self.bridge.config.plan_before_execute = value in {"on", "1", "true", "auto"}
            self._write_log(f"plan_before_execute={self.bridge.config.plan_before_execute}")
            return
        if command.startswith("/profile "):
            value = command.split(" ", 1)[1].strip()
            self._apply_profile_and_enter(value)
            return
        if command.startswith("/dry-run "):
            value = command.split(" ", 1)[1].strip()
            self.bridge.config.dry_run = value in {"on", "1", "true"}
            self._write_log(f"dry_run={self.bridge.config.dry_run}")
            return
        if command.startswith("/mode "):
            value = command.split(" ", 1)[1].strip()
            if value not in {"online", "hybrid", "offline"}:
                self._write_log("Use /mode online|hybrid|offline")
                return
            self.bridge.config.runtime_mode = value
            self._write_log(f"runtime_mode={value}")
            return
        if command.startswith("/sudo "):
            self._handle_sudo_command(command)
            return
        if command == "/sudo":
            self._handle_sudo_command("/sudo status")
            return
        if command.startswith("/root "):
            self._handle_root_command(command)
            return
        if command == "/root":
            self._handle_root_command("/root status")
            return
        if command == "/tools":
            self._write_chat(f"```text\n{self.bridge.actions.capabilities_summary()}\n```")
            return
        if command == "/memory":
            self._write_chat(f"```text\n{memory_summary()}\n```")
            return
        if command.startswith("/remember "):
            text = prompt[len("/remember ") :].strip()
            if text:
                remember(text, source="user", kind="manual")
                self._write_log("Memoria salva.")
            return
        if command == "/forget-all":
            clear_memory()
            self._write_log("Memoria apagada.")
            return
        if command == "/blocked":
            lines = ["**Bloqueios de seguranca**"]
            lines.extend(f"- {reason}" for reason in blocked_reasons())
            lines.append("")
            lines.extend(f"- `{example}`" for example in blocked_examples())
            self._write_chat("\n".join(lines))
            return
        if command == "/accounts":
            if not self.bridge.config.accounts:
                self._write_log("Nenhuma conta configurada.")
                return
            self._write_chat("\n".join([f"- {account.name} | {account.provider_label} | {account.model_name}" for account in self.bridge.config.accounts]))
            return
        if command == "/agents":
            if not self.bridge.config.agents:
                self._write_log("Nenhum agente configurado.")
                return
            self._write_chat("\n".join([f"- {agent.name} | conta={agent.account_id}" for agent in self.bridge.config.agents]))
            return
        if command == "/mcp":
            if not self.bridge.config.mcp_servers:
                self._write_log("Nenhum servidor MCP configurado.")
                return
            self._write_chat("\n".join([f"- {server.name} | {server.command}" for server in self.bridge.config.mcp_servers]))
            return
        if command == "/remote":
            if not self.bridge.config.remote_integrations:
                self._write_log("Nenhuma integracao remota configurada.")
                return
            self._write_chat(
                "\n".join(
                    [
                        f"- {integration.name} | canal={integration.channel} | prefixo={integration.command_prefix}"
                        for integration in self.bridge.config.remote_integrations
                    ]
                )
            )
            return
        if command == "/clear":
            self.query_one("#chat-log", RichLog).clear()
            self.query_one("#action-log", RichLog).clear()
            self._set_mission_panel("Logs limpos. Nenhum plano pendente.")
            return
        self._write_log(f"Comando desconhecido: {prompt}")

    def _run_with_terminal_release(self, callback):
        try:
            with self.suspend():
                return callback()
        except Exception:
            return callback()

    def _start_update_check(self) -> None:
        threading.Thread(target=self._check_for_update, daemon=True).start()

    def _check_for_update(self) -> None:
        info = check_for_update(APP_VERSION, installed_repo_url())
        self.update_info = info
        if info.update_available:
            self.call_from_thread(
                self._write_log,
                transcript_event(
                    "update_available",
                    latest_version=info.latest_version,
                    command=DEFAULT_UPDATE_COMMAND,
                ),
            )

    def _handle_sudo_command(self, command: str) -> None:
        parts = command.split()
        action = parts[1] if len(parts) > 1 else "status"
        if action == "status":
            self._write_log(self.bridge.actions.privilege_status().summary())
            return
        if action == "off":
            self._write_log(self.bridge.actions.disable_privilege_session(reason="manual"))
            return
        if action == "log":
            if len(parts) < 3 or parts[2] not in {"on", "off"}:
                self._write_log("Use /sudo log on|off")
                return
            enabled = self.bridge.actions.set_privilege_logging(parts[2] == "on")
            self._write_log(f"privilege_log={enabled}")
            return
        if action != "on":
            self._write_log("Use /sudo status|on [timeout] [escopo]|off|log on|off")
            return
        timeout_spec = parts[2] if len(parts) >= 3 else None
        scope = parts[3] if len(parts) >= 4 else None
        self.query_one("#action-log", RichLog).write(background_interaction("sudo prompt aberto para senha manual"))
        self._write_chat("Digite a senha manualmente no prompt nativo do `sudo`. O Nexus nao salva a senha.")
        ok, message = self._run_with_terminal_release(lambda: self.bridge.actions.enable_sudo_session(timeout_spec, scope))
        self._write_log(message)
        if ok:
            self._set_mission_panel(f"Privilegio ativo: {self.bridge.actions.privilege_status().summary()}")

    def _handle_root_command(self, command: str) -> None:
        parts = command.split()
        action = parts[1] if len(parts) > 1 else "status"
        if action == "status":
            self._write_log(self.bridge.actions.privilege_status().summary())
            return
        if action == "off":
            self._write_log(self.bridge.actions.disable_privilege_session(reason="manual"))
            return
        if action == "confirm":
            self.query_one("#action-log", RichLog).write(background_interaction("root prompt aberto para senha manual"))
            self._write_chat("Confirmacao root em andamento. Digite a senha manualmente no prompt nativo do `sudo`.")
            ok, message = self._run_with_terminal_release(self.bridge.actions.confirm_root_session)
            self._write_log(message)
            if ok:
                self._set_mission_panel(f"Privilegio ativo: {self.bridge.actions.privilege_status().summary()}")
            return
        if action != "on":
            self._write_log("Use /root on [timeout] [escopo]|confirm|off|status")
            return
        timeout_spec = parts[2] if len(parts) >= 3 else None
        scope = parts[3] if len(parts) >= 4 else None
        ok, message = self.bridge.actions.request_root_session(timeout_spec, scope)
        self._write_log(message)
        if ok:
            self._set_mission_panel("Root pendente de confirmacao dupla. Use /root confirm.")

    def _process_simple(self, prompt: str) -> None:
        try:
            log_event("PROMPT", prompt)
            self.conversation.append({"role": "user", "content": prompt})
            self._save_history()
            self._set_mission_panel("Execucao direta em andamento...")
            answer, _tool_logs = self.bridge.chat(self.conversation)
            self.conversation.append({"role": "assistant", "content": answer})
            self._save_history()
            self.call_from_thread(self._write_chat, answer)
            self.call_from_thread(self._set_mission_panel, "Execucao direta concluida.")
            self.call_from_thread(self._finish_task_log, "Execucao direta concluida.")
        except CancelledExecution as exc:
            self.call_from_thread(self._write_chat, f"**CANCELADO:** {exc}")
            self.call_from_thread(self._write_log, f"[WARN] {exc}")
            self.call_from_thread(self._set_mission_panel, "Execucao cancelada.")
            self.call_from_thread(self._finish_task_log, "Execucao cancelada.")
        except Exception as exc:
            self.monitor.set_state("error", str(exc))
            self.call_from_thread(self._write_chat, f"**ERRO:** {exc}")
            self.call_from_thread(self._write_log, f"[ERROR] {exc}")
            self.call_from_thread(self._finish_task_log, "Execucao terminou com erro.")
        finally:
            self.monitor.set_cancellable(False)
            self.call_from_thread(self._focus_prompt)

    def _process_plan_preview(self, prompt: str) -> None:
        try:
            log_event("MISSION", prompt)
            self.call_from_thread(self._write_chat, f"[bold cyan]🎯 MODO MISSAO ATIVADO[/bold cyan]")
            self.call_from_thread(self._write_chat, f"[dim]Criando plano para: {prompt}[/dim]")
            preview = self.bridge.preview_plan(prompt)
            self.pending_plan = preview
            steps = preview.get("steps", [])
            plan_lines = ["[bold yellow]📋 PLANO:[/bold yellow]"]
            for s in steps:
                plan_lines.append(f"  {s['step']}. {s['task']}")
                if s.get("tool"):
                    risk = str(s.get("risk_level", "green")).upper()
                    plan_lines.append(f"     [cyan]→ {s['tool']}({s.get('args', {})}) [{risk}][/cyan]")
            plan_lines.append("")
            plan_lines.append("[bold]Use /approve para executar ou Esc//cancel para abortar.[/bold]")
            self.call_from_thread(self._write_chat, "\n".join(plan_lines))
            mission_text = [f"Objetivo: {preview.get('goal', '-')}", f"Passos: {len(steps)}"]
            if preview.get("requires_confirmation"):
                mission_text.append("Aguardando /approve")
            self.call_from_thread(self._set_mission_panel, "\n".join(mission_text))
            if steps:
                for step in steps:
                    if step.get("tool") == "executar_comando":
                        args = step.get("args", {}) if isinstance(step.get("args", {}), dict) else {}
                        assessment = self.bridge.actions.assess_command_preview(
                            str(args.get("comando", "")),
                            elevated=bool(args.get("elevated")),
                        )
                        self.call_from_thread(self._set_light, assessment)
                        if "VERMELHA" in assessment.upper():
                            break
            self.call_from_thread(self._finish_task_log, "Plano pronto. Aguardando /approve.")
        except CancelledExecution as exc:
            self.call_from_thread(self._write_chat, f"**CANCELADO:** {exc}")
            self.call_from_thread(self._set_mission_panel, "Preview cancelado.")
            self.call_from_thread(self._finish_task_log, "Preview cancelado.")
        except Exception as exc:
            self.monitor.set_state("error", str(exc))
            self.call_from_thread(self._set_light, f"ERRO: {exc}")
            self.call_from_thread(self._write_chat, f"**ERRO:** {exc}")
            self.call_from_thread(self._write_log, f"[ERROR] {exc}")
            self.call_from_thread(self._finish_task_log, "Preview terminou com erro.")
        finally:
            self.monitor.set_cancellable(False)
            self.call_from_thread(self._focus_prompt)

    def _execute_pending_plan(self) -> None:
        preview = self.pending_plan
        if preview is None:
            self.call_from_thread(self._write_log, "Nenhum plano pendente.")
            return
        self.pending_plan = None
        try:
            goal = str(preview.get("goal", ""))
            steps = preview.get("steps", [])
            self.call_from_thread(self._start_task_log, "Plano aprovado. Vou executar os passos agora.")
            self.call_from_thread(self._write_chat, f"[bold green]🚀 EXECUTANDO {len(steps)} PASSOS...[/bold green]")
            self.call_from_thread(self._set_mission_panel, f"Executando plano: {goal}")
            result = self.bridge.execute_plan(goal, steps if isinstance(steps, list) else [])
            self.call_from_thread(self._write_chat, f"[bold green]✅ {result.get('summary', '(sem resumo)')}[/bold green]")
            remember(f"Missao: {goal} — {len(result.get('results', []))} passos executados", kind="mission")
            self.call_from_thread(self._set_light, "LUZ VERDE — missao concluida")
            self.call_from_thread(self._write_log, f"[bold green]MISSION COMPLETE: {len(result.get('results', []))} etapas[/bold green]")
            self.call_from_thread(self._set_mission_panel, f"Plano concluido: {goal}")
            self.call_from_thread(self._finish_task_log, "Plano concluido.")
        except CancelledExecution as exc:
            self.call_from_thread(self._write_chat, f"**CANCELADO:** {exc}")
            self.call_from_thread(self._write_log, f"[WARN] {exc}")
            self.call_from_thread(self._set_mission_panel, "Plano cancelado.")
            self.call_from_thread(self._finish_task_log, "Plano cancelado.")
        except Exception as exc:
            self.monitor.set_state("error", str(exc))
            self.call_from_thread(self._write_chat, f"**ERRO:** {exc}")
            self.call_from_thread(self._write_log, f"[ERROR] {exc}")
            self.call_from_thread(self._set_mission_panel, "Falha na execucao do plano.")
            self.call_from_thread(self._finish_task_log, "Plano terminou com erro.")
        finally:
            self.monitor.set_cancellable(False)
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
            json.dumps(self.conversation[-self.bridge.config.max_history_messages :], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def password_gate(prompt_label: str = "Nexus Password: ") -> str:
    if os.environ.get("NEXUS_PASSWORD"):
        return os.environ["NEXUS_PASSWORD"]
    return getpass.getpass(prompt_label)


def build_runtime(config: NexusConfig, monitor: ActivityMonitor) -> LiteLLMBridge:
    actions = AcoesAgente(config)
    return LiteLLMBridge(config, monitor, actions)
