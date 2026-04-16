from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Iterable

from .logging_utils import log_event


DEFAULT_TIMEOUT_SECONDS = 15 * 60
MAX_TIMEOUT_SECONDS = 12 * 60 * 60
PRIVILEGED_EXECUTABLES = {
    "apt",
    "apt-get",
    "cp",
    "defaults",
    "dpkg",
    "flatpak",
    "gio",
    "gsettings",
    "journalctl",
    "launchctl",
    "loginctl",
    "mkdir",
    "mount",
    "mv",
    "netsh",
    "networksetup",
    "nmcli",
    "pmset",
    "powershell",
    "pwsh",
    "reg",
    "sc",
    "scutil",
    "snap",
    "softwareupdate",
    "systemctl",
    "tee",
    "timedatectl",
    "touch",
    "ufw",
    "umount",
    "winget",
    "xdg-settings",
}
DEFAULT_SCOPE = {
    "sudo": (
        "apt",
        "apt-get",
        "defaults",
        "dpkg",
        "flatpak",
        "gio",
        "gsettings",
        "journalctl",
        "launchctl",
        "loginctl",
        "netsh",
        "networksetup",
        "nmcli",
        "pmset",
        "powershell",
        "pwsh",
        "reg",
        "sc",
        "scutil",
        "snap",
        "softwareupdate",
        "systemctl",
        "timedatectl",
        "ufw",
        "winget",
        "xdg-settings",
    ),
    "root": (
        "apt",
        "apt-get",
        "cp",
        "defaults",
        "dpkg",
        "flatpak",
        "gio",
        "gsettings",
        "journalctl",
        "launchctl",
        "loginctl",
        "mkdir",
        "mount",
        "mv",
        "netsh",
        "networksetup",
        "nmcli",
        "pmset",
        "powershell",
        "pwsh",
        "reg",
        "sc",
        "scutil",
        "snap",
        "softwareupdate",
        "systemctl",
        "tee",
        "timedatectl",
        "touch",
        "ufw",
        "umount",
        "winget",
        "xdg-settings",
    ),
}
BLOCKED_PRIVILEGED_EXECUTABLES = {
    "bash",
    "dd",
    "fdisk",
    "fish",
    "mkfs",
    "parted",
    "pip",
    "pip3",
    "poweroff",
    "python",
    "python3",
    "reboot",
    "rm",
    "sh",
    "shutdown",
    "su",
    "sudo",
    "wipefs",
    "zsh",
}


def parse_timeout_spec(value: str | None, default_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> int:
    raw = (value or "").strip().lower()
    if not raw:
        return default_seconds
    multiplier = 1
    if raw.endswith("h"):
        multiplier = 3600
        raw = raw[:-1]
    elif raw.endswith("m"):
        multiplier = 60
        raw = raw[:-1]
    elif raw.endswith("s"):
        raw = raw[:-1]
    if not raw.isdigit():
        raise ValueError("Timeout invalido. Use valores como 30s, 15m ou 2h.")
    seconds = int(raw) * multiplier
    if seconds <= 0:
        raise ValueError("Timeout deve ser maior que zero.")
    return min(seconds, MAX_TIMEOUT_SECONDS)


def format_timeout(seconds: int) -> str:
    remaining = max(0, int(seconds))
    if remaining >= 3600 and remaining % 3600 == 0:
        return f"{remaining // 3600}h"
    if remaining >= 60 and remaining % 60 == 0:
        return f"{remaining // 60}m"
    return f"{remaining}s"


def parse_scope_spec(value: str | None, mode: str = "sudo") -> tuple[str, ...]:
    if value is None:
        return tuple(DEFAULT_SCOPE[mode])
    if isinstance(value, str):
        tokens = [item.strip().lower() for item in value.split(",")]
    else:
        tokens = [str(item).strip().lower() for item in value]
    normalized = sorted({item for item in tokens if item})
    if not normalized:
        return tuple(DEFAULT_SCOPE[mode])
    invalid = [item for item in normalized if item not in PRIVILEGED_EXECUTABLES]
    if invalid:
        raise ValueError(f"Escopo invalido: {', '.join(invalid)}")
    return tuple(normalized)


@dataclass(slots=True)
class PendingRootRequest:
    timeout_seconds: int
    scope: tuple[str, ...]
    created_at: float = field(default_factory=time.monotonic)


@dataclass(slots=True)
class PrivilegeStatus:
    mode: str = "off"
    active: bool = False
    timeout_seconds: int = 0
    remaining_seconds: int = 0
    scope: tuple[str, ...] = field(default_factory=tuple)
    logging_enabled: bool = True
    pending_root: bool = False

    def summary(self) -> str:
        if self.pending_root and not self.active:
            return "root pendente de confirmacao"
        if not self.active:
            return "desativado"
        scope = ",".join(self.scope) if self.scope else "-"
        return f"{self.mode} ativo | timeout={format_timeout(self.remaining_seconds)} | escopo={scope}"


class PrivilegeSessionManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._mode = "off"
        self._scope: tuple[str, ...] = ()
        self._timeout_seconds = 0
        self._expires_at = 0.0
        self._logging_enabled = True
        self._pending_root: PendingRootRequest | None = None

    def set_logging_enabled(self, enabled: bool) -> bool:
        with self._lock:
            self._logging_enabled = bool(enabled)
        return self._logging_enabled

    def status(self) -> PrivilegeStatus:
        with self._lock:
            self._expire_locked()
            remaining = max(0, int(self._expires_at - time.monotonic())) if self._mode != "off" else 0
            return PrivilegeStatus(
                mode=self._mode,
                active=self._mode != "off",
                timeout_seconds=self._timeout_seconds,
                remaining_seconds=remaining,
                scope=self._scope,
                logging_enabled=self._logging_enabled,
                pending_root=self._pending_root is not None,
            )

    def request_root(self, timeout_seconds: int, scope: str | Iterable[str] | None = None) -> str:
        normalized_scope = parse_scope_spec(scope, mode="root")
        with self._lock:
            self._pending_root = PendingRootRequest(timeout_seconds=int(timeout_seconds), scope=normalized_scope)
        return (
            "Confirmacao dupla exigida para root. "
            "Use /root confirm para abrir a solicitacao e digitar a senha manualmente."
        )

    def confirm_root(self) -> tuple[bool, str]:
        with self._lock:
            pending = self._pending_root
        if pending is None:
            return False, "Nenhuma ativacao root pendente."
        return self._activate("root", pending.timeout_seconds, pending.scope)

    def enable_sudo(self, timeout_seconds: int, scope: str | Iterable[str] | None = None) -> tuple[bool, str]:
        normalized_scope = parse_scope_spec(scope, mode="sudo")
        return self._activate("sudo", timeout_seconds, normalized_scope)

    def disable(self, *, reason: str = "manual") -> str:
        with self._lock:
            changed = self._mode != "off" or self._pending_root is not None
            self._mode = "off"
            self._scope = ()
            self._timeout_seconds = 0
            self._expires_at = 0.0
            self._pending_root = None
            logging_enabled = self._logging_enabled
        subprocess.run(["sudo", "-k"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if changed and logging_enabled:
            log_event("PRIVILEGE", f"sessao privilegiada encerrada ({reason})")
        return "Sessao privilegiada desativada."

    def prepare_argv(self, argv: list[str], requested_mode: str = "sudo") -> list[str]:
        executable = (argv[0] if argv else "").lower()
        with self._lock:
            self._expire_locked()
            if self._mode == "off":
                raise RuntimeError("Sessao privilegiada nao esta ativa. Use /sudo on ou /root on.")
            if requested_mode == "root" and self._mode != "root":
                raise RuntimeError("Sessao root nao esta ativa. Use /root on e /root confirm.")
            if requested_mode not in {"sudo", "root"}:
                raise RuntimeError(f"Modo privilegiado invalido: {requested_mode}")
            if executable in BLOCKED_PRIVILEGED_EXECUTABLES:
                raise RuntimeError(f"Executavel bloqueado no modo privilegiado: {executable}")
            if executable not in self._scope:
                raise RuntimeError(
                    f"Executavel fora do escopo autorizado: {executable}. Escopo ativo: {', '.join(self._scope) or '-'}"
                )
            logging_enabled = self._logging_enabled
            mode = self._mode
        if logging_enabled:
            log_event("PRIVILEGE_USE", f"{mode} -> {' '.join(argv)}", metadata={"mode": mode, "argv": argv})
        return ["sudo", "-n", *argv]

    def _activate(self, mode: str, timeout_seconds: int, scope: tuple[str, ...]) -> tuple[bool, str]:
        timeout_seconds = int(timeout_seconds)
        try:
            timeout_seconds = parse_timeout_spec(str(timeout_seconds), default_seconds=DEFAULT_TIMEOUT_SECONDS)
        except ValueError as exc:
            return False, str(exc)

        subprocess.run(["sudo", "-k"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        result = subprocess.run(["sudo", "-v"], check=False)
        if result.returncode != 0:
            return False, "Ativacao cancelada ou falhou. Nenhuma credencial foi salva pelo Nexus."

        with self._lock:
            self._mode = mode
            self._scope = scope
            self._timeout_seconds = timeout_seconds
            self._expires_at = time.monotonic() + timeout_seconds
            self._pending_root = None
            logging_enabled = self._logging_enabled
        if logging_enabled:
            log_event(
                "PRIVILEGE",
                f"{mode} ativado timeout={format_timeout(timeout_seconds)} scope={','.join(scope)}",
                metadata={"mode": mode, "timeout_seconds": timeout_seconds, "scope": list(scope)},
            )
        return True, f"{mode} ativo por {format_timeout(timeout_seconds)} com escopo: {', '.join(scope)}"

    def _expire_locked(self) -> None:
        if self._mode == "off" or self._expires_at <= 0:
            return
        if time.monotonic() < self._expires_at:
            return
        mode = self._mode
        self._mode = "off"
        self._scope = ()
        self._timeout_seconds = 0
        self._expires_at = 0.0
        logging_enabled = self._logging_enabled
        subprocess.run(["sudo", "-k"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if logging_enabled:
            log_event("PRIVILEGE", f"sessao {mode} expirou por timeout")
