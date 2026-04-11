from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .config import NexusPaths
from .version import APP_VERSION, parse_calver


DEFAULT_REPO_URL = "https://github.com/Ezequiel135/Nexus-Agent.git"
DEFAULT_UPDATE_COMMAND = "nexus update"
UPDATE_CACHE_MAX_AGE = timedelta(hours=6)
VERSION_LINE_RE = re.compile(r'^APP_VERSION\s*=\s*"(?P<version>\d+\.\d+\.\d+)"$', re.MULTILINE)


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    checked: bool
    current_version: str
    latest_version: str = ""
    update_available: bool = False
    message: str = ""


def _to_raw_version_url(repo_url: str) -> str | None:
    normalized = (repo_url or "").strip()
    match = re.match(r"https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?/?$", normalized)
    if match is None:
        return None
    owner = match.group("owner")
    repo = match.group("repo")
    return f"https://raw.githubusercontent.com/{owner}/{repo}/main/core/version.py"


def installed_repo_url() -> str:
    if NexusPaths.repo_path.exists():
        try:
            value = NexusPaths.repo_path.read_text(encoding="utf-8").strip()
        except OSError:
            value = ""
        if value:
            return value
    return DEFAULT_REPO_URL


def _load_cached() -> dict[str, object] | None:
    path = getattr(NexusPaths, "update_check_path", NexusPaths.base_dir / "update_check.json")
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    checked_at = str(payload.get("checked_at", "")).strip()
    if not checked_at:
        return None
    try:
        seen_at = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if datetime.now(timezone.utc) - seen_at > UPDATE_CACHE_MAX_AGE:
        return None
    return payload


def _save_cached(latest_version: str, repo_url: str) -> None:
    path = getattr(NexusPaths, "update_check_path", NexusPaths.base_dir / "update_check.json")
    path.write_text(
        json.dumps(
            {
                "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "latest_version": latest_version,
                "repo_url": repo_url,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _compare_versions(current_version: str, latest_version: str) -> bool:
    try:
        latest = parse_calver(latest_version)
        current = parse_calver(current_version)
        return (latest.year, latest.micro, latest.patch) > (current.year, current.micro, current.patch)
    except ValueError:
        return latest_version != current_version


def _fetch_latest_version(repo_url: str, timeout: float = 2.5) -> str:
    target = _to_raw_version_url(repo_url)
    if target is None:
        return ""
    try:
        import requests
    except ImportError:
        return ""
    try:
        response = requests.get(target, timeout=timeout)
        response.raise_for_status()
    except Exception:
        return ""
    match = VERSION_LINE_RE.search(response.text)
    return match.group("version") if match else ""


def check_for_update(current_version: str = APP_VERSION, repo_url: str = DEFAULT_REPO_URL, timeout: float = 2.5) -> UpdateInfo:
    NexusPaths.ensure()
    cached = _load_cached()
    latest_version = ""
    if cached and str(cached.get("repo_url", "")).strip() == repo_url:
        latest_version = str(cached.get("latest_version", "")).strip()
    if not latest_version:
        latest_version = _fetch_latest_version(repo_url, timeout=timeout)
        if latest_version:
            _save_cached(latest_version, repo_url)
    if not latest_version:
        return UpdateInfo(checked=False, current_version=current_version, message="Falha ao verificar atualizacao.")
    update_available = _compare_versions(current_version, latest_version)
    if update_available:
        return UpdateInfo(
            checked=True,
            current_version=current_version,
            latest_version=latest_version,
            update_available=True,
            message=f"Atualizacao disponivel: {latest_version}",
        )
    return UpdateInfo(
        checked=True,
        current_version=current_version,
        latest_version=latest_version,
        update_available=False,
        message="Versao atualizada.",
    )
