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
from core.config import NexusConfig, NexusPaths, create_password_hash, save_config
from core.llm import LiteLLMBridge
from core.logging_utils import log_event
from core.state import ActivityMonitor, LIGHT_COLORS, LIGHT_SYMBOLS


def _cpu_and_ram() -> str:
    try:
        import psutil

        return f"CPU {psutil.cpu_percent(interval=0):.0f}% | RAM {psutil.virtual_memory().percent:.0f}%"
    except Exception:
        return "CPU/RAM indisponivel"


@dataclass(slots=True)
class SetupPayload:
    provider: str
    api_key: str
    model_name: str
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
            f"[bold green]NEXUS AGENT v1.0 - STATUS: [OPERACIONAL][/bold green]   [{color}]{dot}[/{color}]\n"
            "[dim cyan]Criado por Ezequiel 135[/dim cyan]"
        )


class StatusBar(Static):
    def __init__(self, monitor: ActivityMonitor) -> None:
        super().__init__()
        self.monitor = monitor

    def on_mount(self) -> None:
        self.set_interval(1.0, self.refresh_status)
        self.refresh_status()

    def refresh_status(self) -> None:
        snap = self.monitor.read()
        mode = "AUTONOMOUS_MODE=ON" if snap.autonomous_mode else "AUTONOMOUS_MODE=OFF"
        self.update(
            f"[black on bright_cyan] Modelo: {snap.current_model} | Latencia: {snap.api_latency_ms} ms | "
            f"{_cpu_and_ram()} | {mode} | Ezequiel 135 [/]"
        )


class SetupApp(App[SetupPayload | None]):
    CSS = """
    Screen { background: black; color: white; }
    #setup-wrap { width: 80; height: auto; border: round cyan; padding: 1 2; margin: 2 4; }
    .setup-title { color: bright_green; text-style: bold; }
    .field { margin-bottom: 1; }
    """

    BINDINGS = [("ctrl+c", "quit", "Sair")]

    def compose(self) -> ComposeResult:
        yield Container(
            Static("NEXUS AGENT SETUP OBRIGATORIO", classes="setup-title"),
            Static("Provider"),
            Select(
                [
                    ("OpenAI", "OpenAI"),
                    ("Anthropic", "Anthropic"),
                    ("Google", "Google"),
                    ("Ollama", "Ollama"),
                    ("Groq", "Groq"),
                ],
                value="OpenAI",
                id="provider",
                classes="field",
            ),
            Static("API Key"),
            Input(password=True, id="api_key", classes="field"),
            Static("Model Name"),
            Input(placeholder="gpt-4o-mini / claude-3-5-sonnet / llama3", id="model_name", classes="field"),
            Static("NEXUS Password"),
            Input(password=True, id="password", classes="field"),
            Static("Pressione Enter no campo de senha para concluir."),
            id="setup-wrap",
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "password":
            return
        provider = self.query_one("#provider", Select).value or "OpenAI"
        api_key = self.query_one("#api_key", Input).value.strip()
        model_name = self.query_one("#model_name", Input).value.strip()
        password = self.query_one("#password", Input).value.strip()
        if not api_key or not model_name or not password:
            self.notify("Preencha provider, API key, model e senha.")
            return
        password_hash, salt = create_password_hash(password)
        save_config(
            NexusConfig(
                provider=str(provider),
                api_key=api_key,
                model_name=model_name,
                password_hash=password_hash,
                password_salt=salt,
            )
        )
        self.exit(SetupPayload(str(provider), api_key, model_name, password))


class NexusApp(App[None]):
    CSS = """
    Screen { background: #05070a; color: white; }
    #body { height: 1fr; padding: 0 1; }
    #chat-panel { width: 1fr; border: round #2ee6a6; margin-right: 1; padding: 0 1; background: #071018; }
    #log-panel { width: 38; border: round #24c8ff; padding: 0 1; background: #08111a; }
    #chat-log, #action-log { height: 1fr; }
    #prompt { dock: bottom; margin-top: 1; }
    .panel-title { color: bright_cyan; text-style: bold; }
    """

    BINDINGS = [("ctrl+c", "quit", "Sair")]

    def __init__(self, bridge: LiteLLMBridge, monitor: ActivityMonitor, initial_task: str | None = None) -> None:
        super().__init__()
        self.bridge = bridge
        self.monitor = monitor
        self.initial_task = initial_task
        self.conversation: list[dict[str, str]] = []

    def compose(self) -> ComposeResult:
        yield NexusHeader(self.monitor)
        with Horizontal(id="body"):
            with Vertical(id="chat-panel"):
                yield Static("Conversation", classes="panel-title")
                yield RichLog(id="chat-log", markup=True, wrap=True)
                yield Input(placeholder="Digite um objetivo ou comando para o Nexus...", id="prompt")
            with Vertical(id="log-panel"):
                yield Static("Action & Log Panel", classes="panel-title")
                yield RichLog(id="action-log", markup=True, wrap=True)
        yield StatusBar(self.monitor)
        yield Footer()

    def on_mount(self) -> None:
        self.bridge.actions.set_event_callback(lambda text: self.call_from_thread(self._write_log, text))
        self.conversation = self._load_history()
        ok, message = self.bridge.handshake()
        self._write_chat("[bold green]NEXUS AGENT online[/bold green]" if ok else f"[bold red]{message}[/bold red]")
        self._write_chat(
            "Use esta interface como um terminal-agente. "
            "Descreva o objetivo e o NEXUS AGENT decide quando usar shell, arquivos, mouse, teclado, memoria e leitura de tela."
        )
        self._write_log(message)
        self._write_log("Marca d'agua ativa: Ezequiel 135")
        if self.initial_task:
            self.query_one("#prompt", Input).value = self.initial_task
            self._submit_prompt(self.initial_task)

    def _write_chat(self, text: str) -> None:
        self.query_one("#chat-log", RichLog).write(Markdown(text))

    def _write_log(self, text: str) -> None:
        self.query_one("#action-log", RichLog).write(text)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "prompt":
            return
        prompt = event.value.strip()
        event.input.value = ""
        if prompt:
            self._submit_prompt(prompt)

    def _submit_prompt(self, prompt: str) -> None:
        self._write_chat(f"**Você:** {prompt}")
        threading.Thread(target=self._process_prompt, args=(prompt,), daemon=True).start()

    def _process_prompt(self, prompt: str) -> None:
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
                self.call_from_thread(self._write_log, "Nenhuma ferramenta local foi usada nesta resposta.")
        except Exception as exc:
            self.monitor.set_state("error", str(exc))
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
    actions = AcoesAgente()
    return LiteLLMBridge(config, monitor, actions)
