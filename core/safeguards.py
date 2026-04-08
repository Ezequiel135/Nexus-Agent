from __future__ import annotations

import re


BLOCKED_RULES = [
    (re.compile(r"\brm\s+-rf\s+/($|\s)"), "Remocao total da raiz"),
    (re.compile(r"\brm\s+-rf\s+--no-preserve-root\b"), "Tentativa de apagar a raiz"),
    (re.compile(r"\bmv\s+.+\s+/dev/null\b"), "Descarte destrutivo de arquivos"),
    (re.compile(r"\bmkfs(\.\w+)?\b"), "Formatacao de disco bloqueada"),
    (re.compile(r"\b(fdisk|parted|cfdisk|sfdisk)\b"), "Manipulacao de particao bloqueada"),
    (re.compile(r"\bdd\s+.+\bof=/dev/"), "Gravacao direta em device bloqueada"),
    (re.compile(r"\b(wipefs|shred)\b"), "Apagamento irreversivel bloqueado"),
    (re.compile(r"\b(chmod|chown)\s+-r\s+/"), "Alteracao massiva na raiz bloqueada"),
    (re.compile(r"\b(systemctl\s+(poweroff|reboot|halt))\b"), "Comando de desligamento bloqueado"),
    (re.compile(r"\b(shutdown|reboot|poweroff|halt|init 0|init 6)\b"), "Comando de energia bloqueado"),
    (re.compile(r"\bmount\b.+\s-o\s+remount,rw\s+/"), "Remount sensivel da raiz bloqueado"),
    (re.compile(r"/(boot|efi|etc|dev|proc|sys)(/|$)"), "Acesso destrutivo a area critica do sistema"),
    (re.compile(r"\b(flashrom|efibootmgr)\b"), "Comando de firmware bloqueado"),
]

BLOCKED_EXAMPLES = [
    "rm -rf /",
    "rm -rf --no-preserve-root /",
    "mkfs.ext4 /dev/sda1",
    "fdisk /dev/sda",
    "parted /dev/nvme0n1",
    "dd if=image.iso of=/dev/sda",
    "wipefs -a /dev/sda",
    "flashrom -p internal -w bios.bin",
    "efibootmgr -b 0001 -B",
    "shutdown now",
    "reboot",
    "poweroff",
]


def command_is_safe(command: str) -> tuple[bool, str]:
    lowered = " ".join(command.strip().lower().split())
    for pattern, reason in BLOCKED_RULES:
        if pattern.search(lowered):
            return False, f"Acao bloqueada para preservar o PC: {reason}"
    return True, ""


def blocked_reasons() -> list[str]:
    return [reason for _, reason in BLOCKED_RULES]


def blocked_examples() -> list[str]:
    return list(BLOCKED_EXAMPLES)
