from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys

from core.config import NexusPaths, config_exists, load_config, verify_password
from core.logging_utils import log_event
from core.safeguards import blocked_examples, blocked_reasons
from core.state import ActivityMonitor


def import_ui_components(required: bool = False):
    try:
        from ui.app import NexusApp, SetupApp, build_runtime, password_gate
    except ImportError as exc:
        if required:
            missing = str(exc)
            print("Dependencias da interface nao instaladas. Rode: pip install -r requirements.txt")
            print(f"Detalhe: {missing}")
            raise SystemExit(1)
        return None, None, None, None
    return NexusApp, SetupApp, build_runtime, password_gate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nexus", description="NEXUS AGENT local autonomy protocol")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="Inicia o NEXUS AGENT")
    start.add_argument("--task", help="Executa uma tarefa inicial ao abrir a interface")
    start.add_argument("--plain", action="store_true", help="Usa modo terminal puro, estilo REPL")

    sub.add_parser("blocked", help="Mostra os comandos e areas bloqueadas por seguranca")
    sub.add_parser("doctor", help="Mostra diagnostico do terminal e da plataforma")
    sub.add_parser("setup", help="Forca o modo de configuracao inicial")
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
    return 0


def ensure_config(force_setup: bool = False) -> None:
    if force_setup or not config_exists():
        _, SetupApp, _, _ = import_ui_components(required=True)
        SetupApp().run()


def should_use_plain_mode(force_plain: bool) -> bool:
    if force_plain:
        return True
    if os.environ.get("NEXUS_PLAIN") == "1":
        return True
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return True
    nexus_app, _, _, _ = import_ui_components(required=False)
    return nexus_app is None


def handle_start(task: str | None, plain: bool = False) -> int:
    ensure_config()
    config = load_config()
    monitor = ActivityMonitor()
    monitor.start()

    _, _, build_runtime, password_gate = import_ui_components(required=not should_use_plain_mode(plain))
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
        if should_use_plain_mode(plain):
            from ui.plain_cli import PlainNexusCLI

            PlainNexusCLI(bridge, monitor, initial_task=task).run()
        else:
            NexusApp, _, _, _ = import_ui_components(required=True)
            NexusApp(bridge, monitor, initial_task=task).run()
        return 0
    finally:
        monitor.stop()


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
    venv_python = NexusPaths.base_dir / "env" / "bin" / "python"
    if requirements.exists() and venv_python.exists():
        subprocess.run([str(venv_python), "-m", "pip", "install", "-r", str(requirements)], check=False)
    print("NEXUS AGENT atualizado.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "setup":
        ensure_config(force_setup=True)
        return 0
    if args.command == "blocked":
        return handle_blocked()
    if args.command == "doctor":
        return handle_doctor()
    if args.command == "update":
        return handle_update()
    if args.command == "start":
        return handle_start(args.task, plain=args.plain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
