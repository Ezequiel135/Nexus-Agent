from __future__ import annotations

import os
import re


LIGHT_GREEN = "🟢 LUZ VERDE — comando classificado como SEGURO"
LIGHT_YELLOW = "🟡 Atencao — comando modifica o sistema (ex: instalar, remover)"
LIGHT_RED = "🔴 BLOQUEADO — risco de dano ou operacao destrutiva"


BLOCKED_RULES = [
    # Destruicao total
    (re.compile(r"\brm\s+-rf\s+/($|\s)"), "Remocao total da raiz"),
    (re.compile(r"\brm\s+-rf\s+--no-preserve-root\b"), "Tentativa de apagar a raiz"),
    (re.compile(r"\bmv\s+.+\s+/dev/null\b"), "Descarte destrutivo de arquivos"),
    (re.compile(r"\bmkfs(\.\w+)?\b"), "Formatacao de disco bloqueada"),
    (re.compile(r"\b(fdisk|parted|cfdisk|sfdisk)\b"), "Manipulacao de particao bloqueada"),
    (re.compile(r"\bdd\s+.+\bof=/dev/"), "Gravacao direta em device bloqueada"),
    (re.compile(r"\b(wipefs|shred)\b"), "Apagamento irreversivel bloqueado"),
    # Alteracoes massivas na raiz
    (re.compile(r"\b(chmod|chown)\s+-r\s+/"), "Alteracao massiva na raiz bloqueada"),
    (re.compile(r"\bchmod\s+777\s+/"), "Permissao perigosa na raiz bloqueada"),
    # Energia / firmware
    (re.compile(r"\b(systemctl\s+(poweroff|reboot|halt))\b"), "Comando de desligamento bloqueado"),
    (re.compile(r"\b(shutdown|reboot|poweroff|halt|init 0|init 6)\b"), "Comando de energia bloqueado"),
    (re.compile(r"\bmount\b.+\s-o\s+remount,rw\s+/"), "Remount sensivel da raiz bloqueado"),
    (re.compile(r"\b(flashrom|efibootmgr)\b"), "Comando de firmware bloqueado"),
]

DANGEROUS_PATTERNS = [
    re.compile(r"^\s*rm\s+.*-rf\b"),
    re.compile(r"^\s*dd\s+.*of=/dev/"),
    re.compile(r"^\s*(shutdown|reboot|poweroff|halt)\b"),
    re.compile(r"^\s*mkfs\b"),
    re.compile(r"^\s*fdisk\b"),
    re.compile(r"^\s*rm\s+.*/\*"),
    re.compile(r"^\s*rm\s+~"),  # apagar home inteiro
]


EXEMPT_DIRS = {
    os.path.expanduser("~"),
    os.path.expanduser("~/.nexus"),
    "/tmp",
    "/var/tmp",
    os.getcwd(),
}

ALLOWED_SUDO_COMMANDS = {
    "apt-get update",
    "apt-get install",
    "systemctl --user",
    "pip3 install",
}


def is_destructive_command(command: str) -> bool:
    cmd = command.strip()
    for pattern in BLOCKED_RULES:
        if pattern[0].search(cmd):
            return True
    return False


def command_is_safe(command: str) -> tuple[bool, str]:
    cmd = " ".join(command.strip().lower().split())

    # Regras explicitas
    for pattern, reason in BLOCKED_RULES:
        if pattern.search(cmd):
            return False, f"Luz Vermelha: {reason}"

    # rm -rf fora de diretorios permitidos
    rm_match = re.match(r"^rm\s+.*-rf\b", cmd)
    if rm_match:
        removed_paths = re.findall(r"rm\s+-rf\s+([^\s]+)", cmd)
        for p in removed_paths:
            expanded = os.path.expanduser(p)
            if expanded != "/" and not any(expanded.startswith(d) for d in EXEMPT_DIRS):
                return False, "Luz Vermelha: remocao em massa fora de diretorios seguros"

    # Verifica se esta em um diretorio seguro
    cwd = os.getcwd()
    if not any(cwd.startswith(d) for d in EXEMPT_DIRS):
        return False, f"Luz Amarela: diretorio atual {cwd} fora de zonas seguras"

    # Comandos que pedem confirmacao visual
    dangerous_keywords = ["rm -r", "dd", "mkfs", "fdisk", "shred", "format"]
    if any(kw in cmd for kw in dangerous_keywords):
        return False, "Luz Amarela: comando potencialmente destrutivo — precisa confirmacao"

    return True, ""


def assess_command_light(command: str) -> str:
    """Retorna o estado da Luz Verde para um comando."""
    allowed, reason = command_is_safe(command)
    if allowed:
        return LIGHT_GREEN
    if "Luz Vermelha" in reason:
        return f"{LIGHT_RED} — {reason}"
    return f"{LIGHT_YELLOW} — {reason}"


def blocked_reasons() -> list[str]:
    return [r for _, r in BLOCKED_RULES]


def blocked_examples() -> list[str]:
    return [
        "rm -rf /",
        "rm -rf --no-preserve-root /",
        "mkfs.ext4 /dev/sda1",
        "fdisk /dev/sda",
        "dd if=image.iso of=/dev/sda",
        "wipefs -a /dev/sda",
        "shred -v /dev/sdb",
        "chmod -R 777 /",
        "shutdown now",
        "mkfs.vfat /dev/sda1",
    ]
