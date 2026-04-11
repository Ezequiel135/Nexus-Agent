from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from .config import NexusPaths


SECRET_PATTERNS = [
    re.compile(r"\b(ghp_[A-Za-z0-9]{20,})\b"),
    re.compile(r"\b(sk-[A-Za-z0-9_\-]{10,})\b"),
    re.compile(r"\b(xox[baprs]-[A-Za-z0-9\-]{10,})\b"),
    re.compile(r"\b(Bearer\s+[A-Za-z0-9._\-]{10,})\b", re.IGNORECASE),
    re.compile(r"\b([A-Za-z0-9_\-]{32,})\b"),
]


def now_hms() -> str:
    return datetime.now().strftime("%H:%M:%S")


def redact_sensitive_text(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def log_event(action: str, detail: str, status: str = "OK", metadata: dict[str, Any] | None = None) -> str:
    NexusPaths.ensure()
    safe_detail = redact_sensitive_text(detail)
    line = f"[{now_hms()}] [{status}] {action}: {safe_detail}"
    with NexusPaths.log_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    audit_payload = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "status": status,
        "action": action,
        "detail": safe_detail,
        "metadata": metadata or {},
    }
    with NexusPaths.audit_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(audit_payload, ensure_ascii=False) + "\n")
    return line
