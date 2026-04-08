from __future__ import annotations

from datetime import datetime

from .config import NexusPaths


def now_hms() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log_event(action: str, detail: str, status: str = "OK") -> str:
    NexusPaths.ensure()
    line = f"[{now_hms()}] [{status}] {action}: {detail}"
    with NexusPaths.log_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return line
