import json
from dataclasses import dataclass, field
from pathlib import Path


STATE_DIR = Path(__file__).resolve().parents[1] / "runtime"
CHAT_STATE_PATH = STATE_DIR / "chat_state.json"


@dataclass
class ChatState:
    messages: list = field(default_factory=list)
    last_seen_screen: str = ""
    anchors: list = field(default_factory=list)
    replied_ids: list = field(default_factory=list)
    source: str = ""
    updated_at: str = ""


def ensure_state_dir():
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def load_chat_state():
    ensure_state_dir()
    if not CHAT_STATE_PATH.exists():
        return ChatState()
    data = json.loads(CHAT_STATE_PATH.read_text(encoding="utf-8"))
    return ChatState(
        messages=data.get("messages", []),
        last_seen_screen=data.get("last_seen_screen", ""),
        anchors=data.get("anchors", []),
        replied_ids=data.get("replied_ids", []),
        source=data.get("source", ""),
        updated_at=data.get("updated_at", ""),
    )


def save_chat_state(state):
    ensure_state_dir()
    payload = {
        "messages": state.messages,
        "last_seen_screen": state.last_seen_screen,
        "anchors": state.anchors,
        "replied_ids": state.replied_ids,
        "source": state.source,
        "updated_at": state.updated_at,
    }
    CHAT_STATE_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
