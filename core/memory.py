from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from .config import NexusPaths


@dataclass(slots=True)
class MemoryItem:
    timestamp: str
    source: str
    kind: str
    text: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_memory() -> list[MemoryItem]:
    NexusPaths.ensure()
    if not NexusPaths.memory_path.exists():
        return []
    try:
        payload = json.loads(NexusPaths.memory_path.read_text(encoding="utf-8"))
        return [MemoryItem(**item) for item in payload if isinstance(item, dict) and item.get("text")]
    except Exception:
        return []


def save_memory(items: list[MemoryItem]) -> None:
    NexusPaths.ensure()
    NexusPaths.memory_path.write_text(
        json.dumps([asdict(item) for item in items], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def remember(text: str, source: str = "user", kind: str = "note", limit: int = 200) -> MemoryItem:
    items = load_memory()
    item = MemoryItem(timestamp=_now(), source=source, kind=kind, text=text.strip())
    items.append(item)
    save_memory(items[-limit:])
    return item


def memory_summary(max_items: int = 8) -> str:
    items = load_memory()
    if not items:
        return "Memoria local vazia."
    selected = items[-max_items:]
    lines = [f"- [{item.kind}] {item.text}" for item in selected]
    return "Memoria local recente:\n" + "\n".join(lines)


def search_memory(query: str, limit: int = 8) -> list[MemoryItem]:
    q = query.strip().lower()
    if not q:
        return load_memory()[-limit:]
    results = [item for item in load_memory() if q in item.text.lower()]
    return results[-limit:]


def clear_memory() -> None:
    save_memory([])
