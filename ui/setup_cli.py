from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import getpass

from rich.console import Console
from rich.panel import Panel

from core.config import (
    KNOWN_PROVIDERS,
    NexusConfig,
    build_initial_config,
    create_password_hash,
    make_account,
    make_agent,
    normalize_provider,
    normalize_ui_mode,
    save_config,
)


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
        config = build_setup_config_from_env()
    else:
        config = prompt_initial_config(console)

    save_config(config)
    console.print("[bold green]Configuracao salva com sucesso.[/bold green]")


def build_setup_config_from_env() -> NexusConfig:
    ui_mode = normalize_ui_mode(os.environ.get("NEXUS_UI_MODE"))
    if ui_mode == "auto":
        ui_mode = "visual"

    password = os.environ.get("NEXUS_PASSWORD", "").strip()
    account_name = os.environ.get("NEXUS_ACCOUNT_NAME", "").strip() or "Conta principal"
    agent_name = os.environ.get("NEXUS_AGENT_NAME", "").strip() or "Agente principal"
    agent_prompt = os.environ.get("NEXUS_AGENT_PROMPT", "").strip()
    provider = normalize_provider(os.environ.get("NEXUS_PROVIDER", "OpenAI"))
    api_key = os.environ.get("NEXUS_API_KEY", "").strip()
    model_name = os.environ.get("NEXUS_MODEL_NAME", "").strip()
    base_url = os.environ.get("NEXUS_BASE_URL", "").strip()
    custom_provider = os.environ.get("NEXUS_CUSTOM_PROVIDER", "").strip()

    validate_account_inputs(provider, api_key, model_name, base_url)
    if not password:
        raise SystemExit(
            "Setup interativo indisponivel sem TTY. "
            "Defina NEXUS_PASSWORD, NEXUS_PROVIDER, NEXUS_API_KEY, NEXUS_MODEL_NAME e opcionalmente "
            "NEXUS_ACCOUNT_NAME, NEXUS_AGENT_NAME, NEXUS_AGENT_PROMPT, NEXUS_BASE_URL e NEXUS_CUSTOM_PROVIDER."
        )

    password_hash, salt = create_password_hash(password)
    account = make_account(
        name=account_name,
        provider=provider,
        api_key=api_key,
        model_name=model_name,
        base_url=base_url,
        custom_provider=custom_provider,
    )
    agent = make_agent(name=agent_name, account_id=account.id, system_prompt=agent_prompt)
    return build_initial_config(password_hash, salt, ui_mode, account, agent)


def prompt_initial_config(console: Console) -> NexusConfig:
    ui_mode = prompt_ui_mode(console)
    account = prompt_account_config(console, existing_ids=set(), default_name="Conta principal")
    agent = prompt_agent_config(
        console,
        account_id=account.id,
        existing_ids=set(),
        default_name="Agente principal",
    )
    password = getpass.getpass("NEXUS Password: ").strip()
    if not password:
        raise SystemExit("Setup cancelado: senha obrigatoria.")
    password_hash, salt = create_password_hash(password)
    return build_initial_config(password_hash, salt, ui_mode, account, agent)


def prompt_ui_mode(console: Console) -> str:
    options = [("visual", "Visual completa"), ("plain", "Terminal puro")]
    console.print("[bold yellow]Escolha o tipo de interface:[/bold yellow]")
    for index, (_mode, label) in enumerate(options, start=1):
        console.print(f"{index}. {label}")
    raw = console.input("[bold cyan]UI [1-2]:[/bold cyan] ").strip()
    if raw.isdigit():
        selected = int(raw)
        if 1 <= selected <= len(options):
            return options[selected - 1][0]
    for mode, label in options:
        if raw.lower() in {mode, label.lower()}:
            return mode
    return "visual"


def prompt_account_config(
    console: Console,
    existing_ids: set[str],
    default_name: str = "Conta",
) -> object:
    providers = list(KNOWN_PROVIDERS)
    console.print("[bold yellow]Escolha o provider:[/bold yellow]")
    for index, name in enumerate(providers, start=1):
        label = "Outro / Custom" if name == "Custom" else name
        console.print(f"{index}. {label}")
    raw = console.input(f"[bold cyan]Provider [1-{len(providers)}]:[/bold cyan] ").strip()
    provider = parse_provider_choice(raw, providers)

    account_name = console.input(f"[bold cyan]Nome da conta[/bold cyan] [{default_name}]: ").strip() or default_name
    custom_provider = ""
    base_url = ""

    if provider == "Custom":
        console.print(
            Panel.fit(
                "[bold cyan]Provider custom / Outro[/bold cyan]\n"
                "Preencha cada dado em uma caixa separada.\n"
                "1. Nome/ID do provider\n"
                "2. Base URL / Endpoint\n"
                "3. API Key da conta\n\n"
                "Nao misture URL com API Key.",
                border_style="bright_cyan",
            )
        )
        console.print("[dim]Campo 1: coloque somente o nome/ID do provider.[/dim]")
        custom_provider = console.input("[bold cyan]Nome/ID do provider custom:[/bold cyan] ").strip()
        console.print("[dim]Campo 2: coloque somente a Base URL / Endpoint.[/dim]")
        base_url = console.input("[bold cyan]Base URL / Endpoint do provider:[/bold cyan] ").strip()
        console.print("[dim]Campo 3: coloque somente a API Key da conta.[/dim]")

    api_key = console.input("[bold cyan]API Key da conta:[/bold cyan] ").strip()
    model_name = console.input("[bold cyan]Model Name:[/bold cyan] ").strip()
    if provider != "Custom":
        base_url = console.input("[bold cyan]Base URL / Endpoint (opcional):[/bold cyan] ").strip()
    if provider == "Custom" and not custom_provider:
        raise SystemExit("Setup cancelado: provider custom exige Nome/ID do provider.")

    validate_account_inputs(provider, api_key, model_name, base_url)
    return make_account(
        name=account_name,
        provider=provider,
        api_key=api_key,
        model_name=model_name,
        base_url=base_url,
        custom_provider=custom_provider,
        existing_ids=existing_ids,
    )


def prompt_agent_config(
    console: Console,
    account_id: str,
    existing_ids: set[str],
    default_name: str = "Agente",
) -> object:
    agent_name = console.input(f"[bold cyan]Nome do agente[/bold cyan] [{default_name}]: ").strip() or default_name
    system_prompt = console.input(
        "[bold cyan]Instrucao extra do agente (opcional):[/bold cyan] "
    ).strip()
    return make_agent(
        name=agent_name,
        account_id=account_id,
        system_prompt=system_prompt,
        existing_ids=existing_ids,
    )


def parse_provider_choice(raw: str, providers: list[str]) -> str:
    if raw.isdigit():
        selected = int(raw)
        if 1 <= selected <= len(providers):
            return providers[selected - 1]
    if raw:
        normalized = normalize_provider(raw)
        if normalized in providers:
            return normalized
    return "OpenAI"


def validate_account_inputs(provider: str, api_key: str, model_name: str, base_url: str) -> None:
    if not api_key or not model_name:
        raise SystemExit("Setup cancelado: API key e model sao obrigatorios.")
    if normalize_provider(provider) == "Custom" and not base_url.strip():
        raise SystemExit("Setup cancelado: provider custom exige Base URL / Endpoint.")


def main() -> int:
    run_plain_setup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
