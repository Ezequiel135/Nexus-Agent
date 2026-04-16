from __future__ import annotations

import os
import platform
import shutil
import subprocess


COMMON_COMMANDS = (
    "apt",
    "bash",
    "brew",
    "cmd",
    "defaults",
    "dnf",
    "dism",
    "flatpak",
    "gio",
    "gsettings",
    "launchctl",
    "loginctl",
    "netsh",
    "networksetup",
    "nmcli",
    "npm",
    "npx",
    "open",
    "osascript",
    "pacman",
    "pip",
    "pip3",
    "pmset",
    "powershell",
    "pwsh",
    "python",
    "python3",
    "reg",
    "sc",
    "scutil",
    "softwareupdate",
    "snap",
    "systemctl",
    "timedatectl",
    "winget",
    "xdg-open",
    "xdg-settings",
    "zsh",
)

CONTROL_COMMANDS = {
    "linux": ("apt", "dnf", "flatpak", "gio", "gsettings", "loginctl", "nmcli", "snap", "systemctl", "timedatectl", "xdg-open", "xdg-settings"),
    "darwin": ("brew", "defaults", "launchctl", "networksetup", "open", "osascript", "pmset", "scutil", "softwareupdate"),
    "windows": ("cmd", "dism", "netsh", "powershell", "pwsh", "reg", "sc", "winget"),
}

BROWSER_COMMANDS = {
    "brave": ("brave-browser", "brave"),
    "chrome": ("google-chrome-stable", "google-chrome", "chrome"),
    "chromium": ("chromium-browser", "chromium"),
    "edge": ("microsoft-edge", "microsoft-edge-stable", "msedge"),
    "firefox": ("firefox",),
}


def _run_quick(command: list[str]) -> str:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=1.2,
            check=False,
        )
    except Exception:
        return ""
    return (completed.stdout or "").strip()


def detect_platform_slug() -> str:
    return platform.system().lower() or os.name.lower()


def detect_platform_label() -> str:
    system = platform.system() or os.name
    release = platform.release()
    extra = ""
    if detect_platform_slug() == "linux":
        try:
            info = platform.freedesktop_os_release()
        except Exception:
            info = {}
        extra = info.get("PRETTY_NAME", "")
    label = f"{system} {release}".strip()
    if extra and extra not in label:
        label = f"{label} ({extra})"
    return label


def available_commands() -> list[str]:
    return [command for command in COMMON_COMMANDS if shutil.which(command)]


def available_control_commands() -> list[str]:
    platform_slug = detect_platform_slug()
    candidates = CONTROL_COMMANDS.get(platform_slug, ())
    return [command for command in candidates if shutil.which(command)]


def available_browsers() -> list[str]:
    found: list[str] = []
    for alias, commands in BROWSER_COMMANDS.items():
        if any(shutil.which(command) for command in commands):
            found.append(alias)
    return found


def default_browser_alias() -> str:
    env_value = os.environ.get("BROWSER", "").strip().lower()
    if env_value:
        for alias, commands in BROWSER_COMMANDS.items():
            if env_value == alias or any(command in env_value for command in commands):
                return alias

    if detect_platform_slug() == "linux":
        desktop_file = _run_quick(["xdg-settings", "get", "default-web-browser"])
        haystack = desktop_file.lower()
        for alias in BROWSER_COMMANDS:
            if alias in haystack:
                return alias
        desktop_file = _run_quick(["gio", "mime", "x-scheme-handler/https"])
        haystack = desktop_file.lower()
        for alias in BROWSER_COMMANDS:
            if alias in haystack:
                return alias
    return ""


def host_summary() -> str:
    commands = ", ".join(available_commands()[:8]) or "none"
    control_commands = ", ".join(available_control_commands()[:8]) or "none"
    browsers = available_browsers()
    browser_label = ", ".join(browsers) if browsers else "none"
    default_browser = default_browser_alias() or "unknown"
    return (
        f"Host OS: {detect_platform_label()}. "
        f"Available commands: {commands}. "
        f"Control commands: {control_commands}. "
        f"Browsers: {browser_label}. "
        f"Default browser: {default_browser}."
    )


def host_snapshot() -> dict[str, object]:
    return {
        "platform_slug": detect_platform_slug(),
        "platform_label": detect_platform_label(),
        "available_commands": available_commands(),
        "available_control_commands": available_control_commands(),
        "available_browsers": available_browsers(),
        "default_browser": default_browser_alias() or "",
        "summary": host_summary(),
    }
