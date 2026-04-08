from . import runtime
from .bridge import write_bridge_state
from .profiles import profile_for_window


READY_ANCHORS = (
    "pergunte alguma coisa",
    "chatgpt pode cometer erros",
    "compartilhar",
    "novo chat",
    "enviar a mensagem",
)

ERROR_ANCHORS = (
    "erro",
    "try again",
    "tente novamente",
    "something went wrong",
    "nao foi possivel",
)


def has_ready_anchor(snapshot):
    texts = " ".join(msg.get("text", "").lower() for msg in snapshot.get("messages", []))
    _, profile = profile_for_window(runtime.focused_window_name())
    anchors = profile.get("ready_anchors", READY_ANCHORS)
    return any(anchor in texts for anchor in anchors) or any(anchor in texts for anchor in READY_ANCHORS) or len(snapshot.get("messages", [])) >= 3


def has_visual_error(snapshot):
    texts = " ".join(msg.get("text", "").lower() for msg in snapshot.get("messages", []))
    return any(anchor in texts for anchor in ERROR_ANCHORS)


def execute_with_verification(action_label, action_fn, observe_fn, ready_fn=None, max_attempts=3, retry_wait=2.0):
    last_snapshot = observe_fn()
    before_hash = last_snapshot.get("frame_hash", "")
    last_error = ""

    for attempt in range(1, max_attempts + 1):
        action_fn()
        runtime.human_delay(0.35, 0.9)
        snapshot = observe_fn()
        changed = snapshot.get("frame_hash", "") != before_hash or bool(snapshot.get("new_messages"))
        ready = ready_fn(snapshot) if ready_fn else changed
        errored = has_visual_error(snapshot)

        if ready and not errored:
            write_bridge_state("completed", action_label, detail=f"Verified on attempt {attempt}")
            return {
                "ok": True,
                "attempts": attempt,
                "snapshot": snapshot,
                "changed": changed,
            }

        if errored:
            last_error = "Erro visual detectado na tela"
        else:
            last_error = "Nada mudou visualmente depois da acao"

        if attempt < max_attempts:
            runtime.time.sleep(retry_wait)

    capture = runtime.save_error_capture("resilience")
    write_bridge_state("failed", action_label, error=f"{last_error}. Captura: {capture}")
    return {
        "ok": False,
        "attempts": max_attempts,
        "snapshot": snapshot,
        "error": last_error,
        "capture": capture,
    }
