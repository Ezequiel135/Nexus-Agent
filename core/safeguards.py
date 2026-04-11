from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


LIGHT_GREEN = "LUZ VERDE — comando permitido"
LIGHT_YELLOW = "LUZ AMARELA — requer revisao/confirmacao"
LIGHT_RED = "LUZ VERMELHA — comando bloqueado"

SHELL_META_RE = re.compile(r"[;&|`]|(\$\()|[<>]|\n")
PATH_LIKE_RE = re.compile(r"^[./~]|^[A-Za-z]:[\\/]|/")

BLOCKED_RULES = [
    (re.compile(r"\brm\s+-rf\b"), "Remocao recursiva forcada bloqueada"),
    (re.compile(r"\bmkfs(\.\w+)?\b"), "Formatacao de disco bloqueada"),
    (re.compile(r"\bdd\b.*\bof=/dev/"), "Gravacao direta em device bloqueada"),
    (re.compile(r"\b(fdisk|parted|cfdisk|sfdisk)\b"), "Manipulacao de particao bloqueada"),
    (re.compile(r"\b(wipefs|shred)\b"), "Apagamento irreversivel bloqueado"),
    (re.compile(r"\b(shutdown|reboot|poweroff|halt|init 0|init 6)\b"), "Comando de energia bloqueado"),
    (re.compile(r"\bchmod\s+-r\b"), "chmod -R bloqueado"),
    (re.compile(r"\bchown\s+-r\b"), "chown -R bloqueado"),
    (re.compile(r"\bformat\b"), "Formatacao bloqueada"),
]

SAFE_EXECUTABLES = {
    "awk",
    "cat",
    "cp",
    "date",
    "df",
    "du",
    "echo",
    "env",
    "file",
    "find",
    "git",
    "grep",
    "head",
    "hostname",
    "ls",
    "mkdir",
    "mv",
    "pip",
    "pip3",
    "pwd",
    "pytest",
    "python",
    "python3",
    "rg",
    "sed",
    "stat",
    "tail",
    "tar",
    "touch",
    "uname",
    "unzip",
    "uv",
    "wc",
    "which",
    "whoami",
    "zip",
}

CONFIRMATION_EXECUTABLES = {
    "cp",
    "git",
    "mkdir",
    "mv",
    "pip",
    "pip3",
    "python",
    "python3",
    "sed",
    "tar",
    "touch",
    "uv",
}

READ_ONLY_PRIVILEGED_EXECUTABLES = {
    "journalctl",
}

READ_ONLY_PRIVILEGED_SUBCOMMANDS = {
    "apt": {"list", "policy", "search", "show"},
    "dpkg": {"--list", "--status", "-l", "-s"},
    "flatpak": {"info", "list", "search"},
    "snap": {"find", "info", "list"},
    "systemctl": {"cat", "is-active", "is-enabled", "list-unit-files", "list-units", "show", "status"},
    "timedatectl": {"show", "status"},
}

CRITICAL_PATH_PREFIXES = (
    "/",
    "/bin",
    "/boot",
    "/dev",
    "/etc",
    "/lib",
    "/lib64",
    "/proc",
    "/root",
    "/run",
    "/sbin",
    "/sys",
    "/usr",
)


@dataclass(slots=True)
class CommandAssessment:
    allowed: bool
    level: str
    reason: str
    needs_confirmation: bool = False
    executable: str = ""
    argv: list[str] = field(default_factory=list)
    modifies_state: bool = False


def allowed_write_roots() -> tuple[Path, ...]:
    cwd = Path.cwd().resolve()
    return (
        Path.home().resolve(),
        cwd,
        (Path.home() / ".nexus").resolve(),
        Path("/tmp").resolve(),
        Path("/var/tmp").resolve(),
    )


def normalize_user_path(value: str) -> Path:
    raw = (value or "").strip()
    if not raw or "\x00" in raw:
        raise ValueError("Path invalido.")
    return Path(raw).expanduser()


def is_critical_system_path(path: Path) -> bool:
    try:
        resolved = path.resolve(strict=False)
    except OSError:
        resolved = path
    resolved_str = str(resolved)
    return any(resolved_str == prefix or resolved_str.startswith(prefix + os.sep) for prefix in CRITICAL_PATH_PREFIXES)


def is_path_within_allowed_roots(path: Path) -> bool:
    try:
        resolved = path.resolve(strict=False)
    except OSError:
        resolved = path
    return any(str(resolved).startswith(str(root)) for root in allowed_write_roots())


def ensure_safe_write_path(value: str) -> Path:
    path = normalize_user_path(value)
    if is_critical_system_path(path):
        raise ValueError(f"Path sensivel bloqueado: {path}")
    if not is_path_within_allowed_roots(path):
        raise ValueError(f"Path fora das areas permitidas: {path}")
    return path


def sanitize_url(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("URL vazia.")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL deve usar http ou https.")
    if parsed.username or parsed.password:
        raise ValueError("URL com credenciais embutidas nao e permitida.")
    if not parsed.netloc:
        raise ValueError("URL invalida.")
    return raw


def parse_shell_command(command: str) -> list[str]:
    raw = (command or "").strip()
    if not raw:
        raise ValueError("Comando vazio.")
    if SHELL_META_RE.search(raw):
        raise ValueError("Operadores de shell complexos foram bloqueados por seguranca.")
    try:
        argv = shlex.split(raw, posix=True)
    except ValueError as exc:
        raise ValueError(f"Comando invalido: {exc}") from exc
    if not argv:
        raise ValueError("Comando vazio.")
    return argv


def command_assessment(command: str, extra_safe_executables: set[str] | None = None) -> CommandAssessment:
    raw = (command or "").strip()
    lowered = raw.lower()
    extra_safe_executables = {item.lower() for item in (extra_safe_executables or set())}

    for pattern, reason in BLOCKED_RULES:
        if pattern.search(lowered):
            return CommandAssessment(False, "red", reason)

    try:
        argv = parse_shell_command(raw)
    except ValueError as exc:
        return CommandAssessment(False, "red", str(exc))

    executable = argv[0].lower()
    if executable not in SAFE_EXECUTABLES and executable not in extra_safe_executables:
        return CommandAssessment(False, "red", f"Executavel fora da whitelist: {executable}", executable=executable, argv=argv)

    modifies_state = executable in CONFIRMATION_EXECUTABLES or executable in extra_safe_executables
    if executable in extra_safe_executables:
        if executable in READ_ONLY_PRIVILEGED_EXECUTABLES:
            modifies_state = False
        else:
            first_non_flag = next((token for token in argv[1:] if not token.startswith("-")), "")
            if first_non_flag and first_non_flag in READ_ONLY_PRIVILEGED_SUBCOMMANDS.get(executable, set()):
                modifies_state = False

    if executable == "git":
        modifies_state = any(
            token in {"add", "commit", "push", "pull", "checkout", "switch", "merge", "rebase", "clone", "restore"}
            for token in argv[1:]
        )
        if "push" in argv[1:]:
            return CommandAssessment(False, "red", "git push via agente shell foi bloqueado; use fluxo explicito de publicacao.", executable=executable, argv=argv, modifies_state=True)

    if executable in {"python", "python3"}:
        if any(token in {"-c", "-m"} for token in argv[1:3]):
            modifies_state = True

    for token in argv[1:]:
        if token.startswith("-"):
            continue
        if not PATH_LIKE_RE.search(token):
            continue
        try:
            candidate = normalize_user_path(token)
        except ValueError:
            return CommandAssessment(False, "red", f"Path invalido no comando: {token}", executable=executable, argv=argv)
        if modifies_state:
            if is_critical_system_path(candidate):
                return CommandAssessment(False, "red", f"Path sensivel bloqueado: {candidate}", executable=executable, argv=argv, modifies_state=True)
            if not is_path_within_allowed_roots(candidate):
                return CommandAssessment(False, "red", f"Path fora das areas permitidas: {candidate}", executable=executable, argv=argv, modifies_state=True)

    if modifies_state:
        return CommandAssessment(
            True,
            "yellow",
            "Comando com potencial de modificar arquivos/ambiente.",
            needs_confirmation=True,
            executable=executable,
            argv=argv,
            modifies_state=True,
        )

    return CommandAssessment(True, "green", "Comando permitido.", executable=executable, argv=argv)


def is_destructive_command(command: str) -> bool:
    assessment = command_assessment(command)
    return assessment.level == "red"


def command_is_safe(command: str) -> tuple[bool, str]:
    assessment = command_assessment(command)
    if assessment.level == "green":
        return True, ""
    prefix = "Luz Vermelha" if assessment.level == "red" else "Luz Amarela"
    return False, f"{prefix}: {assessment.reason}"


def assess_command_light(command: str, extra_safe_executables: set[str] | None = None) -> str:
    assessment = command_assessment(command, extra_safe_executables=extra_safe_executables)
    if assessment.level == "green":
        return LIGHT_GREEN
    if assessment.level == "yellow":
        return f"{LIGHT_YELLOW} — {assessment.reason}"
    return f"{LIGHT_RED} — {assessment.reason}"


def blocked_reasons() -> list[str]:
    reasons = [reason for _, reason in BLOCKED_RULES]
    reasons.append("Executaveis fora da whitelist padrao sao bloqueados.")
    reasons.append("Operadores complexos de shell (;, &&, ||, |, >, <, $()) sao bloqueados.")
    reasons.append("Escritas fora de HOME/cwd/.nexus/tmp sao bloqueadas.")
    return reasons


def blocked_examples() -> list[str]:
    return [
        "rm -rf /",
        "rm -rf ~/Downloads",
        "mkfs.ext4 /dev/sda1",
        "dd if=image.iso of=/dev/sda",
        "chmod -R 777 /",
        "shutdown now",
        "bash -lc 'rm -rf /tmp/x'",
        "git push origin main",
    ]
