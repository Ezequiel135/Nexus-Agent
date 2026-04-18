from __future__ import annotations

import json
from typing import Any


def _extract_json_block(answer: str) -> str:
    text = (answer or "").strip()
    if not text.startswith("```"):
        return text
    lines = [line for line in text.splitlines() if not line.startswith("```")]
    return "\n".join(lines).strip()


def _load_payload(answer: str) -> Any:
    text = _extract_json_block(answer)
    if not text.startswith(("{", "[")):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def parse_assistant_actions(answer: str) -> list[dict[str, Any]]:
    payload = _load_payload(answer)
    items = payload if isinstance(payload, list) else [payload] if isinstance(payload, dict) else []
    actions: list[dict[str, Any]] = []

    for item in items:
        if not isinstance(item, dict):
            continue
        tool_name = str(item.get("tool") or item.get("name") or "").strip().lower()
        command = item.get("command") or item.get("comando")
        action = item.get("acao") or item.get("action")
        text = item.get("texto") or item.get("text") or item.get("target")

        if tool_name in {"bash", "shell", "terminal", "executar_comando"} and isinstance(command, str) and command.strip():
            actions.append({"kind": "command", "command": command.strip()})
            continue

        if tool_name == "controle_periferico" and isinstance(action, str):
            normalized = {"kind": "visual", "action": action.strip()}
            if isinstance(text, str) and text.strip():
                normalized["target"] = text.strip()
            if item.get("x") is not None:
                normalized["x"] = item.get("x")
            if item.get("y") is not None:
                normalized["y"] = item.get("y")
            actions.append(normalized)
            continue

        if isinstance(action, str) and action.strip() in {"abrir_app", "atalho_teclado", "digitar", "clicar", "mover_mouse"}:
            normalized = {"kind": "visual", "action": action.strip()}
            if isinstance(text, str) and text.strip():
                normalized["target"] = text.strip()
            if item.get("x") is not None:
                normalized["x"] = item.get("x")
            if item.get("y") is not None:
                normalized["y"] = item.get("y")
            actions.append(normalized)

    return actions
