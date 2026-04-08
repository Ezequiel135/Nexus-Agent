import json
import os
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_DIR = PROJECT_ROOT / "runtime"
BRIDGE_JSON = BRIDGE_DIR / "bridge.json"
STATE_LOG = BRIDGE_DIR / "state.log"
CONSENT_JSON = BRIDGE_DIR / "consent.json"


def ensure_runtime_dir():
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_runtime():
    return import_module(".runtime", __package__)


def detect_capabilities():
    capabilities = {
        "platform": os.name,
        "display": os.environ.get("DISPLAY", ""),
        "mouse": False,
        "keyboard": False,
        "screen_capture": False,
        "windows": False,
        "ocr": False,
        "headless_supported": True,
        "browser_automation": False,
        "visible_windows": 0,
    }
    try:
        runtime = load_runtime()
    except Exception as exc:
        capabilities["runtime_error"] = str(exc)
        return capabilities

    capabilities.update(
        {
            "platform": runtime.platform_name(),
            "mouse": True,
            "keyboard": True,
            "screen_capture": True,
            "windows": True,
            "ocr": True,
            "browser_automation": True,
            "visible_windows": len(runtime.visible_windows()),
        }
    )
    return capabilities


def write_bridge_state(status, command, detail=None, error=None):
    ensure_runtime_dir()
    payload = {
        "timestamp": now_iso(),
        "status": status,
        "command": command,
        "detail": detail or "",
        "error": error or "",
        "capabilities": detect_capabilities(),
    }
    BRIDGE_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    append_state_log(payload)


def append_state_log(entry):
    ensure_runtime_dir()
    with STATE_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=True) + "\n")


def read_session_consent():
    ensure_runtime_dir()
    if not CONSENT_JSON.exists():
        return {"trusted": False, "updated_at": ""}
    try:
        return json.loads(CONSENT_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {"trusted": False, "updated_at": ""}


def write_session_consent(trusted, detail=""):
    ensure_runtime_dir()
    payload = {
        "trusted": bool(trusted),
        "detail": detail,
        "updated_at": now_iso(),
    }
    CONSENT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    append_state_log(
        {
            "timestamp": now_iso(),
            "status": "session",
            "command": "session",
            "detail": detail or ("trusted" if trusted else "revoked"),
            "error": "",
            "capabilities": detect_capabilities(),
        }
    )
    return payload
