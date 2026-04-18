from __future__ import annotations

import json
from typing import Any

from .execution import prompt_looks_like_command, prompt_requests_execution
from .safeguards import command_assessment


def _extract_json_block(answer: str) -> str:
    text = (answer or "").strip()
    if not text.startswith("```"):
        return text
    lines = [line for line in text.splitlines() if not line.startswith("```")]
    return "\n".join(lines).strip()


def _candidate_command_lines(answer: str) -> list[str]:
    text = _extract_json_block(answer)
    if not text:
        return []
    lines = [" ".join(line.strip().split()) for line in text.splitlines()]
    return [line for line in lines if line]


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

        if isinstance(action, str) and action.strip() in {"abrir_app", "fechar_app", "atalho_teclado", "digitar", "clicar", "mover_mouse"}:
            normalized = {"kind": "visual", "action": action.strip()}
            if isinstance(text, str) and text.strip():
                normalized["target"] = text.strip()
            if item.get("x") is not None:
                normalized["x"] = item.get("x")
            if item.get("y") is not None:
                normalized["y"] = item.get("y")
            actions.append(normalized)

    return actions


def extract_assistant_command(answer: str) -> str | None:
    lines = _candidate_command_lines(answer)
    if len(lines) != 1:
        return None
    candidate = lines[0]
    if candidate.startswith(("{", "[")):
        return None
    if candidate.lower().startswith(("okay", "ok", "certo", "vou ", "i ", "the user", "looking at")):
        return None
    if ":" in candidate and not prompt_looks_like_command(candidate):
        return None
    if not prompt_looks_like_command(candidate):
        return None
    assessment = command_assessment(candidate)
    if not assessment.allowed:
        return None
    return candidate


def normalize_assistant_answer(
    answer: str,
    prompt: str,
    tool_logs: list[str],
    fallback_executed: bool = False,
) -> tuple[str, bool]:
    if tool_logs:
        return answer or "(sem resposta)", True
    if fallback_executed:
        return "Acao executada a partir do comando estruturado devolvido pela IA.", True
    if parse_assistant_actions(answer):
        return (
            "O modelo devolveu um comando estruturado, mas a execucao automatica nao foi concluida.",
            False,
        )
    extracted_command = extract_assistant_command(answer)
    if extracted_command:
        return f"Comando executado a partir da resposta textual da IA: {extracted_command}", False
    if prompt_requests_execution(prompt):
        return (
            "A IA respondeu em texto, sem executar. O Nexus ocultou a resposta longa e aguardou uma acao real.",
            False,
        )
    return answer or "(sem resposta)", False
