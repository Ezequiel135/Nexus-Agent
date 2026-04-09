from __future__ import annotations

import argparse
import getpass
import shutil
import os
import platform
import subprocess
import sys
from pathlib import Path

from core.actions import AcoesAgente
from core.config import NexusPaths, config_exists, load_config, normalize_ui_mode, verify_password
from core.llm import LiteLLMBridge
from core.logging_utils import log_event
from core.safeguards import blocked_examples, blocked_reasons
from core.state import ActivityMonitor


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
    return LiteLLMBridge(config, monitor, AcoesAgente())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nexus", description="NEXUS AGENT local autonomy protocol")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="Inicia o NEXUS AGENT")
    start.add_argument("--task", help="Executa uma tarefa inicial ao abrir a interface")
    start.add_argument("--plain", action="store_true", help="Usa modo terminal puro, estilo REPL")

    sub.add_parser("blocked", help="Mostra os comandos e areas bloqueadas por seguranca")
    sub.add_parser("doctor", help="Mostra diagnostico do terminal e da plataforma")
    sub.add_parser("onboarding", help="Abre a tela de boas-vindas e onboarding")
    sub.add_parser("setup", help="Forca o modo de configuracao inicial")
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
    print("NEXUS AGENT doctor\n")
    print(f"platform={platform.system()} {platform.release()}")
    print(f"python={sys.version.split()[0]}")
    print(f"stdin_tty={sys.stdin.isatty()}")
    print(f"stdout_tty={sys.stdout.isatty()}")
    print(f"shell={os.environ.get('SHELL') or os.environ.get('COMSPEC') or '-'}")
    print(f"config_exists={config_exists()}")
    print(f"repo_file={NexusPaths.repo_path}")
    print(f"activity_file={NexusPaths.activity_path}")
    print(f"memory_file={NexusPaths.memory_path}")
    print(f"local_launcher={Path.home() / '.local/bin/nexus'}")
    print(f"global_launcher=/usr/local/bin/nexus")
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
    config = load_config()
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
        "como salvar memoria local, como atualizar, como ver comandos bloqueados e como operar no modo terminal."
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
