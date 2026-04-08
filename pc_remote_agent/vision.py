import hashlib
from datetime import datetime, timezone

from . import runtime
from .browser import extract_dom_messages
from .profiles import profile_for_window
from .state import ChatState, load_chat_state, save_chat_state


def _now():
    return datetime.now(timezone.utc).isoformat()


def _text_hash(text):
    return hashlib.sha1(text.strip().encode("utf-8", "ignore")).hexdigest()[:16]


def _frame_hash(img):
    small = img.convert("L").resize((24, 24))
    return hashlib.sha1(bytes(small.getdata())).hexdigest()[:16]


def _normalize_lines(text):
    lines = [line.strip() for line in text.splitlines()]
    return [line for line in lines if line and len(line) >= 2]


def extract_messages_from_text(text, bounds, role_hint="unknown"):
    messages = []
    for idx, line in enumerate(_normalize_lines(text)):
        messages.append(
            {
                "id": _text_hash(line),
                "role": role_hint,
                "text": line,
                "position": [bounds[0], bounds[1] + idx * 20],
            }
        )
    return messages


def merge_messages(state, incoming, source, frame_hash):
    known_ids = {msg["id"] for msg in state.messages}
    for message in incoming:
        if message["id"] not in known_ids:
            state.messages.append(message)
            known_ids.add(message["id"])
    state.last_seen_screen = frame_hash
    state.anchors = [msg["id"] for msg in state.messages[-5:]]
    state.source = source
    state.updated_at = _now()
    save_chat_state(state)
    return state


def mark_replied(message_ids):
    state = load_chat_state()
    seen = set(state.replied_ids)
    for item in message_ids:
        if item not in seen:
            state.replied_ids.append(item)
            seen.add(item)
    state.updated_at = _now()
    save_chat_state(state)
    return state


def detect_chat_region():
    img, width, height = runtime.screen_image()
    _, profile = profile_for_window(runtime.focused_window_name())
    profile_region = profile.get("chat_region")
    if profile_region:
        return runtime.resolve_region(profile_region, width, height), width, height
    candidate = runtime.detect_chat_region_from_image(img)
    if candidate:
        return candidate, width, height
    return runtime.resolve_region(runtime.CHAT_REGION, width, height), width, height


def capture_chat_snapshot(timeout=runtime.DEFAULT_OCR_TIMEOUT):
    state = load_chat_state()
    dom_messages = extract_dom_messages()
    if dom_messages:
        bounds, _, _ = detect_chat_region()
        synthetic_img, _, _, _ = runtime.region_image(bounds)
        frame_hash = _frame_hash(synthetic_img)
        new_messages = [msg for msg in dom_messages if msg["id"] not in {m["id"] for m in state.messages}]
        merge_messages(state, dom_messages, "dom", frame_hash)
        return {"source": "dom", "messages": dom_messages, "new_messages": new_messages, "frame_hash": frame_hash, "bounds": bounds}

    bounds, _, _ = detect_chat_region()
    img, _, _, _ = runtime.region_image(bounds)
    frame_hash = _frame_hash(img)
    text = runtime.best_ocr_text(img, timeout=timeout)
    messages = extract_messages_from_text(text, bounds, role_hint="ocr")
    new_messages = [msg for msg in messages if msg["id"] not in {m["id"] for m in state.messages}]
    merge_messages(state, messages, "ocr", frame_hash)
    return {"source": "ocr", "messages": messages, "new_messages": new_messages, "frame_hash": frame_hash, "bounds": bounds}


def changed_since_last(snapshot):
    state = load_chat_state()
    return snapshot["frame_hash"] != state.last_seen_screen


def capture_frame_sequence(frames=4, delay=0.35):
    state = load_chat_state()
    results = []
    repeated = 0
    previous_hash = state.last_seen_screen
    for index in range(frames):
        snapshot = capture_chat_snapshot(timeout=2)
        new_ids = [msg["id"] for msg in snapshot["messages"] if msg["id"] not in state.anchors]
        if snapshot["frame_hash"] == previous_hash:
            repeated += 1
        else:
            repeated = 0
        results.append(
            {
                "index": index + 1,
                "source": snapshot["source"],
                "frame_hash": snapshot["frame_hash"],
                "repeated": repeated,
                "new_ids": new_ids,
                "messages": snapshot["messages"],
                "bounds": snapshot["bounds"],
            }
        )
        previous_hash = snapshot["frame_hash"]
        runtime.time.sleep(delay)
    return results


def read_scroll_history(direction="down", steps=3, delay=0.7, stop_on_repeat=2):
    history = []
    repeated = 0
    previous_seen = None
    for _ in range(steps):
        if direction == "down":
            runtime.scroll_down(1, delay=0.12)
        else:
            runtime.scroll_up(1, delay=0.12)
        runtime.time.sleep(delay)
        snapshot = capture_chat_snapshot(timeout=2)
        ids = tuple(msg["id"] for msg in snapshot["messages"][-6:])
        history.append(snapshot)
        if ids and ids == previous_seen:
            repeated += 1
        else:
            repeated = 0
        previous_seen = ids
        if repeated >= stop_on_repeat:
            break
    return history


def export_state():
    state = load_chat_state()
    return {
        "messages": state.messages,
        "last_seen_screen": state.last_seen_screen,
        "anchors": state.anchors,
        "replied_ids": state.replied_ids,
        "source": state.source,
        "updated_at": state.updated_at,
    }


def unreplied_messages(limit=8):
    state = load_chat_state()
    replied = set(state.replied_ids)
    return [msg for msg in state.messages if msg["id"] not in replied][-limit:]
