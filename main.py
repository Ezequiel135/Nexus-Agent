from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import argparse
import getpass
import json
import platform
import shutil
import subprocess
from pathlib import Path

from core.actions import AcoesAgente
from core.config import (
    NexusPaths,
    NexusMcpServer,
    activate_account,
    activate_agent,
    add_account,
    add_agent,
    add_mcp_server,
    add_remote_integration,
    config_exists,
    find_account,
    load_config,
    logout_account,
    make_remote_integration,
    normalize_ui_mode,
    remove_mcp_server,
    remove_remote_integration,
    save_config,
    slugify_name,
    unique_id,
    verify_password,
)
from core.llm import LiteLLMBridge
from core.mcp import list_mcp_resources, list_mcp_servers, list_mcp_tools, read_mcp_resource
from core.notebooks import append_cell, create_notebook, execute_notebook, list_notebooks, read_notebook
from core.logging_utils import log_event
from core.safeguards import blocked_examples, blocked_reasons
from core.state import ActivityMonitor
from core.parallel import ParallelAgentRunner
from core.version import APP_VERSION

DEFAULT_WHATSAPP_GRAPH_VERSION = "v23.0"


def import_ui_components(required: bool = False):
    try:
        from ui.app import NexusApp, SetupApp
    except ImportError as exc:
        if required:
            missing = str(exc)
            print("Dependencias da interface nao instaladas. Rode: pip install -r requirements.txt")
            print(f"Detalhe: {missing}")
            raise SystemExit(1)
        return None, None
    return NexusApp, SetupApp


def password_gate(prompt_label: str = "Nexus Password: ") -> str:
    if os.environ.get("NEXUS_PASSWORD"):
        return os.environ["NEXUS_PASSWORD"]
    return getpass.getpass(prompt_label)


def build_runtime(config, monitor) -> LiteLLMBridge:
    return LiteLLMBridge(config, monitor, AcoesAgente(config))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nexus", description="NEXUS AGENT local autonomy protocol")
    parser.add_argument("--version", action="version", version=f"%(prog)s {APP_VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="Inicia o NEXUS AGENT")
    start.add_argument("--task", help="Executa uma tarefa inicial ao abrir a interface")
    start.add_argument("--plain", action="store_true", help="Usa modo terminal puro, estilo REPL")

    sub.add_parser("blocked", help="Mostra os comandos e areas bloqueadas por seguranca")
    sub.add_parser("doctor", help="Mostra diagnostico do terminal e da plataforma")
    sub.add_parser("onboarding", help="Abre a tela de boas-vindas e onboarding")
    sub.add_parser("setup", help="Forca o modo de configuracao inicial")
    sub.add_parser("accounts", help="Lista as contas configuradas")
    login = sub.add_parser("login", help="Troca para uma conta existente ou adiciona uma nova")
    login.add_argument("--account", help="Nome ou ID de uma conta ja existente")
    sub.add_parser("logout", help="Desloga da conta ativa")
    sub.add_parser("agents", help="Lista os agentes configurados")
    add_agent_cmd = sub.add_parser("add-agent", help="Adiciona um novo agente")
    add_agent_cmd.add_argument("--account", help="Conta dona do agente")
    use_agent = sub.add_parser("use-agent", help="Ativa um agente existente")
    use_agent.add_argument("agent", help="Nome ou ID do agente")
    parallel = sub.add_parser("parallel", help="Executa varios agentes em paralelo")
    parallel_sub = parallel.add_subparsers(dest="parallel_command", required=True)
    parallel_sub.add_parser("list", help="Lista agentes disponiveis para execucao paralela")
    parallel_run = parallel_sub.add_parser("run", help="Roda uma tarefa em varios agentes ao mesmo tempo")
    parallel_run.add_argument("--task", required=True, help="Objetivo a enviar para os agentes")
    parallel_run.add_argument("--agent", action="append", dest="agents", help="Nome ou ID de um agente. Repita para varios.")
    parallel_run.add_argument("--mode", choices=["chat", "plan"], default="plan", help="plan gera apenas planos; chat usa o runtime completo")
    parallel_run.add_argument("--max-rounds", type=int, default=6, help="Maximo de rodadas de tool-calls por agente no modo chat")
    parallel_run.add_argument("--json", action="store_true", help="Imprime o resultado em JSON")
    mcp = sub.add_parser("mcp", help="Gerencia servidores MCP configurados")
    mcp_sub = mcp.add_subparsers(dest="mcp_command", required=True)
    mcp_sub.add_parser("list", help="Lista servidores MCP")
    mcp_add = mcp_sub.add_parser("add", help="Adiciona um servidor MCP via stdio")
    mcp_add.add_argument("--name", required=True, help="Nome do servidor MCP")
    mcp_add.add_argument("--command", required=True, help="Comando para iniciar o servidor MCP")
    mcp_remove = mcp_sub.add_parser("remove", help="Remove um servidor MCP")
    mcp_remove.add_argument("server", help="Nome ou ID do servidor")
    mcp_resources = mcp_sub.add_parser("resources", help="Lista recursos de um servidor MCP")
    mcp_resources.add_argument("server", help="Nome ou ID do servidor")
    mcp_read = mcp_sub.add_parser("read", help="Lê um recurso MCP")
    mcp_read.add_argument("server", help="Nome ou ID do servidor")
    mcp_read.add_argument("uri", help="URI do recurso MCP")
    mcp_tools = mcp_sub.add_parser("tools", help="Lista ferramentas de um servidor MCP")
    mcp_tools.add_argument("server", help="Nome ou ID do servidor")
    notebook = sub.add_parser("notebook", help="Gerencia notebooks Jupyter")
    notebook_sub = notebook.add_subparsers(dest="notebook_command", required=True)
    notebook_list = notebook_sub.add_parser("list", help="Lista notebooks .ipynb")
    notebook_list.add_argument("--root", help="Diretorio raiz opcional para busca")
    notebook_create = notebook_sub.add_parser("create", help="Cria um notebook")
    notebook_create.add_argument("path", help="Caminho do notebook")
    notebook_create.add_argument("--title", default="", help="Titulo inicial em markdown")
    notebook_create.add_argument("--kernel", default="python3", help="Kernel Jupyter")
    notebook_read = notebook_sub.add_parser("read", help="Lê um notebook")
    notebook_read.add_argument("path", help="Caminho do notebook")
    notebook_add = notebook_sub.add_parser("add-cell", help="Adiciona uma celula")
    notebook_add.add_argument("path", help="Caminho do notebook")
    notebook_add.add_argument("--type", choices=["code", "markdown"], default="code", help="Tipo da celula")
    notebook_add.add_argument("--content", required=True, help="Conteudo da celula")
    notebook_run = notebook_sub.add_parser("run", help="Executa um notebook")
    notebook_run.add_argument("path", help="Caminho do notebook")
    notebook_run.add_argument("--kernel", default="", help="Kernel opcional")
    notebook_run.add_argument("--timeout", type=int, default=300, help="Timeout por celula em segundos")
    notebook_run.add_argument("--cwd", default="", help="Diretorio de execucao opcional")
    remote = sub.add_parser("remote", help="Gerencia integracoes remotas por bot")
    remote_sub = remote.add_subparsers(dest="remote_command", required=True)
    remote_sub.add_parser("list", help="Lista integracoes remotas")
    remote_sub.add_parser("arm", help="Arma o modo remoto")
    remote_sub.add_parser("disarm", help="Desarma o modo remoto")
    remote_start = remote_sub.add_parser("start", help="Inicia o listener/polling remoto")
    remote_start.add_argument("integration", help="Nome ou ID da integracao")
    remote_start.add_argument("--host", default="127.0.0.1", help="Host para webhooks")
    remote_start.add_argument("--port", type=int, default=8787, help="Porta para webhooks")
    remote_remove = remote_sub.add_parser("remove", help="Remove uma integracao remota")
    remote_remove.add_argument("integration", help="Nome ou ID da integracao")
    remote_tg = remote_sub.add_parser("add-telegram", help="Adiciona um bot Telegram via polling")
    remote_tg.add_argument("--name", required=True, help="Nome da integracao")
    remote_tg.add_argument("--bot-token", required=True, help="Token do bot Telegram")
    remote_tg.add_argument("--allow", action="append", required=True, help="Chat ID ou user ID autorizado")
    remote_tg.add_argument("--prefix", default="!nexus", help="Prefixo exigido na mensagem")
    remote_tg.add_argument("--poll-timeout", type=int, default=30, help="Timeout de polling em segundos")
    remote_wa = remote_sub.add_parser("add-whatsapp", help="Adiciona um webhook WhatsApp Cloud API")
    remote_wa.add_argument("--name", required=True, help="Nome da integracao")
    remote_wa.add_argument("--access-token", required=True, help="Access token do Meta Graph")
    remote_wa.add_argument("--phone-number-id", required=True, help="Phone Number ID do WhatsApp")
    remote_wa.add_argument("--verify-token", required=True, help="Verify token do webhook")
    remote_wa.add_argument("--allow", action="append", required=True, help="Numero/ID autorizado")
    remote_wa.add_argument("--prefix", default="!nexus", help="Prefixo exigido na mensagem")
    remote_wa.add_argument("--graph-version", default=DEFAULT_WHATSAPP_GRAPH_VERSION, help="Versao do Graph API")
    sub.add_parser("uninstall", help="Remove a instalacao local do NEXUS AGENT")
    sub.add_parser("update", help="Atualiza o NEXUS AGENT via git pull")
    return parser


def handle_blocked() -> int:
    print("NEXUS AGENT: comandos bloqueados por seguranca\n")
    print("Razoes:")
    for reason in blocked_reasons():
        print(f"- {reason}")
    print("\nExemplos bloqueados:")
    for example in blocked_examples():
        print(f"- {example}")
    return 0


def handle_doctor() -> int:
    config = load_config() if config_exists() else None
    print("NEXUS AGENT doctor\n")
    print(f"version={APP_VERSION}")
    print(f"platform={platform.system()} {platform.release()}")
    print(f"python={sys.version.split()[0]}")
    print(f"stdin_tty={sys.stdin.isatty()}")
    print(f"stdout_tty={sys.stdout.isatty()}")
    print(f"shell={os.environ.get('SHELL') or os.environ.get('COMSPEC') or '-'}")
    print(f"config_exists={config_exists()}")
    print(f"repo_file={NexusPaths.repo_path}")
    print(f"activity_file={NexusPaths.activity_path}")
    print(f"memory_file={NexusPaths.memory_path}")
    print(f"notebooks_dir={NexusPaths.notebooks_dir}")
    print(f"local_launcher={Path.home() / '.local/bin/nexus'}")
    print(f"global_launcher=/usr/local/bin/nexus")
    if config is not None:
        active_account = config.active_account.name if config.active_account else "-"
        active_agent = config.active_agent.name if config.active_agent else "-"
        print(f"accounts={len(config.accounts)} active_account={active_account}")
        print(f"agents={len(config.agents)} active_agent={active_agent}")
        print(f"mcp_servers={len(config.mcp_servers)}")
        print(f"remote_integrations={len(config.remote_integrations)} armed={config.remote_armed}")
    return 0


def handle_uninstall() -> int:
    targets = [
        NexusPaths.base_dir,
        Path.home() / ".local/bin/nexus",
    ]
    for target in targets:
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            print(f"Removido: {target}")
        elif target.exists():
            target.unlink(missing_ok=True)
            print(f"Removido: {target}")
    print("Desinstalacao local concluida.")
    print("Se existir /usr/local/bin/nexus antigo, remova manualmente com sudo ou rode o install.sh novo para corrigi-lo.")
    return 0


def handle_accounts() -> int:
    if not config_exists():
        print("Nenhuma configuracao encontrada. Rode nexus setup.")
        return 1
    config = load_config()
    if not config.accounts:
        print("Nenhuma conta configurada.")
        return 1
    print("Contas configuradas:\n")
    for account in config.accounts:
        marker = "*" if config.active_account_id == account.id else " "
        provider = account.provider_label
        base = f" | base={account.base_url}" if account.base_url else ""
        print(f"{marker} {account.name} [{account.id}] | provider={provider} | model={account.model_name}{base}")
    return 0


def handle_login(account_query: str | None = None) -> int:
    if not config_exists():
        ensure_config(force_setup=True)
        return 0

    config = load_config()
    if account_query:
        try:
            account = activate_account(config, account_query)
        except ValueError as exc:
            print(str(exc))
            return 1
        save_config(config)
        print(f"Conta ativa alterada para: {account.name}")
        return 0

    from rich.console import Console
    from ui.setup_cli import prompt_account_config

    console = Console()
    default_name = f"Conta {len(config.accounts) + 1}"
    account = prompt_account_config(console, {item.id for item in config.accounts}, default_name=default_name)
    add_account(config, account, activate=True)
    save_config(config)
    print(f"Nova conta criada e ativada: {account.name}")
    return 0


def handle_logout() -> int:
    if not config_exists():
        print("Nenhuma configuracao encontrada.")
        return 1
    config = load_config()
    logout_account(config)
    save_config(config)
    print("Conta ativa desconectada. Rode nexus login para entrar em outra conta.")
    return 0


def handle_agents() -> int:
    if not config_exists():
        print("Nenhuma configuracao encontrada. Rode nexus setup.")
        return 1
    config = load_config()
    if not config.agents:
        print("Nenhum agente configurado.")
        return 1
    print("Agentes configurados:\n")
    for agent in config.agents:
        marker = "*" if config.active_agent_id == agent.id else " "
        account = find_account(config, agent.account_id)
        account_name = account.name if account is not None else "-"
        extra = f" | prompt={agent.system_prompt}" if agent.system_prompt else ""
        print(f"{marker} {agent.name} [{agent.id}] | conta={account_name}{extra}")
    return 0


def handle_add_agent(account_query: str | None = None) -> int:
    if not config_exists():
        print("Nenhuma configuracao encontrada. Rode nexus setup primeiro.")
        return 1
    config = load_config()
    if not config.accounts:
        print("Nenhuma conta configurada. Rode nexus login para criar uma conta.")
        return 1

    account = find_account(config, account_query) if account_query else (config.active_account or config.accounts[0])
    if account is None:
        print(f"Conta nao encontrada: {account_query}")
        return 1

    from rich.console import Console
    from ui.setup_cli import prompt_agent_config

    console = Console()
    default_name = f"Agente {len(config.agents) + 1}"
    agent = prompt_agent_config(
        console,
        account_id=account.id,
        existing_ids={item.id for item in config.agents},
        default_name=default_name,
    )
    add_agent(config, agent, activate=True)
    save_config(config)
    print(f"Agente criado e ativado: {agent.name} (conta: {account.name})")
    return 0


def handle_use_agent(agent_query: str) -> int:
    if not config_exists():
        print("Nenhuma configuracao encontrada.")
        return 1
    config = load_config()
    try:
        agent = activate_agent(config, agent_query)
    except ValueError as exc:
        print(str(exc))
        return 1
    save_config(config)
    print(f"Agente ativo alterado para: {agent.name}")
    return 0


def handle_parallel(args) -> int:
    if not config_exists():
        print("Nenhuma configuracao encontrada. Rode nexus setup.")
        return 1

    config = load_config()
    runner = ParallelAgentRunner(config)

    if args.parallel_command == "list":
        if not config.agents:
            print("Nenhum agente configurado.")
            return 1
        print("Agentes disponiveis para execucao paralela:\n")
        for agent in config.agents:
            account = find_account(config, agent.account_id)
            account_name = account.name if account is not None else "-"
            marker = "*" if config.active_agent_id == agent.id else " "
            extra = f" | prompt={agent.system_prompt}" if agent.system_prompt else ""
            print(f"{marker} {agent.name} [{agent.id}] | conta={account_name}{extra}")
        return 0

    try:
        payload = runner.run(
            args.task,
            agent_queries=args.agents,
            mode=args.mode,
            max_rounds=args.max_rounds,
        )
    except ValueError as exc:
        print(str(exc))
        return 1

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print(
        f"Execucao paralela: {payload['agent_count']} agente(s) | "
        f"modo={payload['mode']} | versao={APP_VERSION}"
    )
    print(f"Tarefa: {payload['task']}\n")
    for item in payload["results"]:
        status = "OK" if item["ok"] else "ERROR"
        print(
            f"[{status}] {item['agent_name']} | conta={item['account_name']} | "
            f"{item['elapsed_ms']} ms"
        )
        if item.get("tool_logs"):
            print(f"tools={', '.join(item['tool_logs'][:4])}")
        if item["ok"]:
            if item.get("mode") == "plan":
                print(f"plan_steps={item.get('plan_steps', 0)}")
            print(item["output"] or "(sem resposta)")
        else:
            print(item.get("error", "Falha sem detalhe"))
        print("")
    print(payload["summary"])
    return 0


def handle_mcp(args) -> int:
    if not config_exists():
        print("Nenhuma configuracao encontrada. Rode nexus setup primeiro.")
        return 1

    config = load_config()
    if args.mcp_command == "list":
        servers = list_mcp_servers(config)
        if not servers:
            print("Nenhum servidor MCP configurado.")
            return 0
        print("Servidores MCP:\n")
        for server in servers:
            status = "on" if server.get("enabled", True) else "off"
            print(f"- {server['name']} [{server['id']}] | {status} | {server['command']}")
        return 0

    if args.mcp_command == "add":
        existing_ids = {server.id for server in config.mcp_servers}
        server = NexusMcpServer(
            id=unique_id(args.name, slugify_name(args.name, "mcp"), existing_ids),
            name=args.name.strip(),
            command=args.command.strip(),
            enabled=True,
        )
        add_mcp_server(config, server)
        save_config(config)
        print(f"Servidor MCP adicionado: {server.name}")
        return 0

    if args.mcp_command == "remove":
        try:
            server = remove_mcp_server(config, args.server)
        except ValueError as exc:
            print(str(exc))
            return 1
        save_config(config)
        print(f"Servidor MCP removido: {server.name}")
        return 0

    if args.mcp_command == "resources":
        try:
            resources = list_mcp_resources(config, args.server)
        except Exception as exc:
            print(f"Erro MCP: {exc}")
            return 1
        if not resources:
            print("Nenhum recurso MCP encontrado.")
            return 0
        for item in resources:
            print(f"- {item.get('name') or item.get('uri')} | {item.get('uri')}")
        return 0

    if args.mcp_command == "read":
        try:
            payload = read_mcp_resource(config, args.server, args.uri)
        except Exception as exc:
            print(f"Erro MCP: {exc}")
            return 1
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if args.mcp_command == "tools":
        try:
            tools = list_mcp_tools(config, args.server)
        except Exception as exc:
            print(f"Erro MCP: {exc}")
            return 1
        if not tools:
            print("Nenhuma ferramenta MCP encontrada.")
            return 0
        for item in tools:
            print(f"- {item.get('name')} | {item.get('description', '')}")
        return 0

    return 0


def handle_notebook(args) -> int:
    try:
        if args.notebook_command == "list":
            items = list_notebooks(args.root)
            if not items:
                print("Nenhum notebook encontrado.")
                return 0
            print("Notebooks Jupyter:\n")
            for item in items:
                print(f"- {item['relative_path']} | {item['size_bytes']} bytes | atualizado {item['modified_at']}")
            return 0
        if args.notebook_command == "create":
            payload = create_notebook(args.path, title=args.title, kernel_name=args.kernel)
            print(f"Notebook criado: {payload['path']}")
            return 0
        if args.notebook_command == "read":
            payload = read_notebook(args.path)
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0
        if args.notebook_command == "add-cell":
            cell_type = "markdown" if args.type == "markdown" else "code"
            payload = append_cell(args.path, args.content, cell_type=cell_type)
            print(f"Celula {payload['cell_type']} adicionada em {payload['path']}")
            return 0
        if args.notebook_command == "run":
            payload = execute_notebook(
                args.path,
                kernel_name=args.kernel,
                timeout=args.timeout,
                cwd=args.cwd,
            )
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0
    except Exception as exc:
        print(f"Erro notebook: {exc}")
        return 1
    return 0


def handle_remote(args) -> int:
    try:
        from core.remote import list_remote_integrations, run_remote_integration
    except ImportError as exc:
        print("Dependencias remotas nao instaladas. Rode pip install -r requirements.txt")
        print(f"Detalhe: {exc}")
        return 1

    if not config_exists():
        print("Nenhuma configuracao encontrada. Rode nexus setup primeiro.")
        return 1

    config = load_config()
    if args.remote_command == "list":
        print(f"Modo remoto: {'ARMADO' if config.remote_armed else 'DESARMADO'}")
        items = list_remote_integrations(config)
        if not items:
            print("Nenhuma integracao remota configurada.")
            return 0
        print("\nIntegracoes remotas:\n")
        for item in items:
            status = "on" if item["enabled"] else "off"
            allowed = ", ".join(item["allowed_senders"]) or "-"
            print(
                f"- {item['name']} [{item['id']}] | canal={item['channel']} | {status} | "
                f"prefixo={item['command_prefix']} | allow={allowed}"
            )
        return 0

    if args.remote_command == "arm":
        config.remote_armed = True
        save_config(config)
        print("Modo remoto armado.")
        return 0

    if args.remote_command == "disarm":
        config.remote_armed = False
        save_config(config)
        print("Modo remoto desarmado.")
        return 0

    if args.remote_command == "add-telegram":
        integration = make_remote_integration(
            args.name,
            "telegram",
            command_prefix=args.prefix,
            allowed_senders=args.allow,
            settings={
                "bot_token": args.bot_token,
                "poll_timeout": str(args.poll_timeout),
            },
            existing_ids={item.id for item in config.remote_integrations},
        )
        add_remote_integration(config, integration)
        save_config(config)
        print(f"Integracao Telegram adicionada: {integration.name}")
        return 0

    if args.remote_command == "add-whatsapp":
        integration = make_remote_integration(
            args.name,
            "whatsapp",
            command_prefix=args.prefix,
            allowed_senders=args.allow,
            settings={
                "access_token": args.access_token,
                "phone_number_id": args.phone_number_id,
                "verify_token": args.verify_token,
                "graph_version": args.graph_version,
            },
            existing_ids={item.id for item in config.remote_integrations},
        )
        add_remote_integration(config, integration)
        save_config(config)
        print(f"Integracao WhatsApp adicionada: {integration.name}")
        return 0

    if args.remote_command == "remove":
        try:
            integration = remove_remote_integration(config, args.integration)
        except ValueError as exc:
            print(str(exc))
            return 1
        save_config(config)
        print(f"Integracao removida: {integration.name}")
        return 0

    if args.remote_command == "start":
        password = password_gate("Nexus Password (remote): ")
        if not verify_password(password, config.password_hash, config.password_salt):
            print("Senha invalida.")
            return 1
        os.environ["AUTONOMOUS_MODE"] = "1"
        try:
            run_remote_integration(config, args.integration, host=args.host, port=args.port)
        except Exception as exc:
            print(f"Erro remoto: {exc}")
            return 1
        return 0

    return 0


def ensure_config(force_setup: bool = False) -> None:
    if force_setup or not config_exists():
        _, SetupApp = import_ui_components(required=False)
        if SetupApp is not None and sys.stdin.isatty() and sys.stdout.isatty():
            SetupApp().run()
            return
        from ui.setup_cli import run_plain_setup

        run_plain_setup()


def should_use_plain_mode(force_plain: bool, config=None) -> bool:
    if force_plain:
        return True
    env_ui_mode = normalize_ui_mode(os.environ.get("NEXUS_UI_MODE"))
    if env_ui_mode == "plain":
        return True
    if env_ui_mode == "visual":
        requested_mode = "visual"
    else:
        requested_mode = normalize_ui_mode(getattr(config, "ui_mode", "auto"))
    if requested_mode == "plain":
        return True
    if os.environ.get("NEXUS_PLAIN") == "1":
        return True
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return True
    nexus_app, _ = import_ui_components(required=False)
    if requested_mode == "visual":
        return nexus_app is None
    return nexus_app is None


def handle_start(task: str | None, plain: bool = False) -> int:
    ensure_config()
    if not config_exists():
        print("Configuracao inicial nao concluida. Rode nexus setup e finalize o formulario.")
        return 1
    config = load_config()
    if config.active_account is None:
        print("Nenhuma conta ativa. Rode nexus login para entrar em uma conta ou nexus setup para reconfigurar.")
        return 1
    use_plain_mode = should_use_plain_mode(plain, config)
    monitor = ActivityMonitor()
    monitor.start()

    if not use_plain_mode:
        import_ui_components(required=True)
    password = password_gate()
    if not verify_password(password, config.password_hash, config.password_salt):
        monitor.set_state("error", "Senha invalida")
        print("Senha invalida.")
        return 1

    os.environ["AUTONOMOUS_MODE"] = "1"
    monitor.set_autonomous_mode(True)
    bridge = build_runtime(config, monitor)
    log_event("BOOT", "NEXUS AGENT iniciado por Ezequiel 135")
    try:
        if use_plain_mode:
            from ui.plain_cli import PlainNexusCLI

            PlainNexusCLI(bridge, monitor, initial_task=task).run()
        else:
            NexusApp, _ = import_ui_components(required=True)
            NexusApp(bridge, monitor, initial_task=task).run()
        return 0
    finally:
        monitor.stop()


def handle_onboarding(plain: bool = False) -> int:
    welcome_task = (
        "Entre em modo onboarding. Apresente o NEXUS AGENT, explique comandos principais, "
        "como salvar memoria local, como usar agentes em paralelo, como ver comandos bloqueados e como operar no modo terminal."
    )
    return handle_start(welcome_task, plain=plain)


def handle_update() -> int:
    if not NexusPaths.repo_path.exists():
        print("Repositorio do NEXUS AGENT nao configurado em ~/.nexus/repo.txt")
        return 1

    repo_url = NexusPaths.repo_path.read_text(encoding="utf-8").strip()
    project_root = NexusPaths.base_dir / "src"
    if not project_root.exists() or not (project_root / ".git").exists():
        print("Instalacao do NEXUS AGENT nao encontrada em ~/.nexus/src")
        return 1

    print("Atualizando NEXUS AGENT...")
    subprocess.run(["git", "-C", str(project_root), "remote", "set-url", "origin", repo_url], check=False)
    pull = subprocess.run(["git", "-C", str(project_root), "pull", "origin", "main"], capture_output=True, text=True)
    sys.stdout.write(pull.stdout)
    sys.stderr.write(pull.stderr)
    if pull.returncode != 0:
        return pull.returncode

    requirements = project_root / "requirements.txt"
    if platform.system().lower() == "windows":
        venv_python = NexusPaths.base_dir / "env" / "Scripts" / "python.exe"
    else:
        venv_python = NexusPaths.base_dir / "env" / "bin" / "python"
    if requirements.exists() and venv_python.exists():
        subprocess.run([str(venv_python), "-m", "pip", "install", "-r", str(requirements)], check=False)
    print("NEXUS AGENT atualizado.")
    return 0


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if not raw_args:
        raw_args = ["start"]
    args = build_parser().parse_args(raw_args)
    if args.command == "setup":
        ensure_config(force_setup=True)
        return 0
    if args.command == "accounts":
        return handle_accounts()
    if args.command == "login":
        return handle_login(args.account)
    if args.command == "logout":
        return handle_logout()
    if args.command == "agents":
        return handle_agents()
    if args.command == "add-agent":
        return handle_add_agent(args.account)
    if args.command == "use-agent":
        return handle_use_agent(args.agent)
    if args.command == "parallel":
        return handle_parallel(args)
    if args.command == "mcp":
        return handle_mcp(args)
    if args.command == "notebook":
        return handle_notebook(args)
    if args.command == "remote":
        return handle_remote(args)
    if args.command == "blocked":
        return handle_blocked()
    if args.command == "doctor":
        return handle_doctor()
    if args.command == "onboarding":
        return handle_onboarding(plain=True)
    if args.command == "update":
        return handle_update()
    if args.command == "uninstall":
        return handle_uninstall()
    if args.command == "start":
        return handle_start(args.task, plain=args.plain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
