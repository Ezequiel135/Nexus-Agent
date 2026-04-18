from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from core.assistant_actions import extract_assistant_command, parse_assistant_actions


@dataclass(frozen=True, slots=True)
class ExecutedActionEvent:
    kind: str
    payload: dict[str, Any]
    command: str | None = None
    action: str | None = None
    target: str | None = None


def visual_shortcut_status(action: str, target: str) -> str:
    if action == "atalho_teclado" and target == "win":
        return "Vou abrir o menu de aplicativos direto no host."
    if action == "fechar_app":
        return f"Vou fechar {target} direto no host."
    return f"Vou abrir {target} direto no host."


def collect_assistant_action_events(
    answer: str,
    *,
    run_command: Callable[[str], dict[str, Any]],
    run_visual: Callable[[str, str | None, int | None, int | None], dict[str, Any]],
) -> list[ExecutedActionEvent]:
    actions = parse_assistant_actions(answer)
    if not actions:
        extracted_command = extract_assistant_command(answer)
        if not extracted_command:
            return []
        return [ExecutedActionEvent(kind="command", command=extracted_command, payload=run_command(extracted_command))]

    events: list[ExecutedActionEvent] = []
    for item in actions:
        if item["kind"] == "command":
            command = str(item["command"])
            events.append(ExecutedActionEvent(kind="command", command=command, payload=run_command(command)))
            continue
        if item["kind"] == "visual":
            action = str(item["action"])
            target = item.get("target")
            payload = run_visual(action, target, item.get("x"), item.get("y"))
            events.append(
                ExecutedActionEvent(
                    kind="visual",
                    action=action,
                    target=str(target) if target is not None else None,
                    payload=payload,
                )
            )
    return events


def format_terminal_event(event: ExecutedActionEvent, *, markdown: bool) -> str:
    command = event.command or ""
    payload = event.payload
    if markdown:
        lines = [f"**Terminal:** `{command}`"]
        if payload.get("stdout"):
            lines.append("```text")
            lines.append(str(payload["stdout"]))
            lines.append("```")
        if payload.get("stderr"):
            lines.append("```text")
            lines.append(str(payload["stderr"]))
            lines.append("```")
        if payload.get("erro"):
            lines.append(f"**Erro:** {payload['erro']}")
        if payload.get("returncode") is not None:
            lines.append(f"**Exit:** `{payload['returncode']}`")
        return "\n".join(lines)

    lines = [f"comando: {command}"]
    if payload.get("dry_run"):
        lines.append("modo: dry-run")
    if payload.get("stdout"):
        lines.append("")
        lines.append("[stdout]")
        lines.append(str(payload["stdout"]))
    if payload.get("stderr"):
        lines.append("")
        lines.append("[stderr]")
        lines.append(str(payload["stderr"]))
    if payload.get("erro"):
        lines.append("")
        lines.append(f"erro: {payload['erro']}")
    if payload.get("returncode") is not None:
        lines.append("")
        lines.append(f"exit={payload['returncode']}")
    return "\n".join(lines)


def format_visual_event(event: ExecutedActionEvent, *, markdown: bool) -> str:
    action = event.action or ""
    target = event.target
    payload = event.payload
    if markdown:
        header = f"**Visual:** `{action}`"
        if target:
            header += f" `{target}`"
        lines = [header]
        if payload.get("opened"):
            lines.append(f"**Resultado:** `{payload['opened']}`")
        if payload.get("keys"):
            lines.append(f"**Teclas:** `{payload['keys']}`")
        if payload.get("erro"):
            lines.append(f"**Erro:** {payload['erro']}")
        return "\n".join(lines)

    lines = [f"acao: {action}"]
    if target:
        lines.append(f"target: {target}")
    if payload.get("opened"):
        lines.append(f"resultado: {payload['opened']}")
    if payload.get("keys"):
        lines.append(f"teclas: {payload['keys']}")
    if payload.get("erro"):
        lines.append(f"erro: {payload['erro']}")
    return "\n".join(lines)
