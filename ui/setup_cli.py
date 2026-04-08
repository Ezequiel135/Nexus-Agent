from __future__ import annotations

import getpass
import os
import sys

from rich.console import Console
from rich.panel import Panel

from core.config import NexusConfig, create_password_hash, save_config


def run_plain_setup() -> None:
    console = Console()
    console.print(
        Panel.fit(
            "[bold green]NEXUS AGENT SETUP[/bold green]\n"
            "[dim cyan]Modo terminal puro | Criado por Ezequiel 135[/dim cyan]",
            border_style="bright_cyan",
        )
    )

    if not sys.stdin.isatty():
        provider = os.environ.get("NEXUS_PROVIDER", "OpenAI").strip() or "OpenAI"
        api_key = os.environ.get("NEXUS_API_KEY", "").strip()
        model_name = os.environ.get("NEXUS_MODEL_NAME", "").strip()
        password = os.environ.get("NEXUS_PASSWORD", "").strip()
        if not api_key or not model_name or not password:
            raise SystemExit(
                "Setup interativo indisponivel sem TTY. "
                "Abra o comando em um terminal real ou defina NEXUS_PROVIDER, NEXUS_API_KEY, NEXUS_MODEL_NAME e NEXUS_PASSWORD."
            )
    else:
        provider = _prompt_provider(console)
        api_key = console.input("[bold cyan]API Key:[/bold cyan] ").strip()
        model_name = console.input("[bold cyan]Model Name:[/bold cyan] ").strip()
        password = getpass.getpass("NEXUS Password: ").strip()

    if not api_key or not model_name or not password:
        raise SystemExit("Setup cancelado: provider, API key, model e senha sao obrigatorios.")

    password_hash, salt = create_password_hash(password)
    save_config(
        NexusConfig(
            provider=provider,
            api_key=api_key,
            model_name=model_name,
            password_hash=password_hash,
            password_salt=salt,
        )
    )
    console.print("[bold green]Configuracao salva com sucesso.[/bold green]")


def _prompt_provider(console: Console) -> str:
    providers = ["OpenAI", "Anthropic", "Google", "Ollama", "Groq"]
    console.print("[bold yellow]Escolha o provider:[/bold yellow]")
    for index, name in enumerate(providers, start=1):
        console.print(f"{index}. {name}")
    raw = console.input("[bold cyan]Provider [1-5]:[/bold cyan] ").strip()
    if raw.isdigit():
        selected = int(raw)
        if 1 <= selected <= len(providers):
            return providers[selected - 1]
    if raw:
        for name in providers:
            if raw.lower() == name.lower():
                return name
    return "OpenAI"
