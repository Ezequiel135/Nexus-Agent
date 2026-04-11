from __future__ import annotations

import re


LOG_LINE_RE = re.compile(r"^\[(?P<time>\d{2}:\d{2}:\d{2})\] \[(?P<status>[A-Z]+)\] (?P<action>[A-Z_]+): (?P<detail>.*)$")


def format_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def worked_banner(seconds: float) -> str:
    title = f"Worked for {format_duration(seconds)}"
    side = "─" * 44
    return f"{side} {title} {side}"


def bullet(text: str) -> str:
    return f"• {text.strip()}"


def child(text: str) -> str:
    return f"  └ {text.strip()}"


def background_interaction(text: str) -> str:
    return f"↳ Interacted with background terminal\n{child(text)}"


def _label_for_action(action: str, detail: str, status: str) -> tuple[str, str]:
    if action == "ARQUIVO":
        return "Vou mexer em arquivos locais.", detail
    if action == "PERIFERICO":
        return "Vou controlar mouse, teclado ou tela.", detail
    if action == "MCP":
        return "Vou consultar contexto MCP.", detail
    if action == "NOTEBOOK":
        return "Vou trabalhar com notebook.", detail
    if action == "BLOQUEADO":
        return "Comando bloqueado pelas regras de seguranca.", detail
    if action == "DRY_RUN":
        return "Dry-run ativo para esta acao.", detail
    if action == "TIMEOUT":
        return "A execucao bateu no timeout.", detail
    if action == "CANCELADO":
        return "A execucao foi cancelada.", detail
    if action == "RESULTADO":
        return "Comando finalizado.", detail
    if action == "PRIVILEGE":
        return "Sessao privilegiada atualizada.", detail
    if action == "PRIVILEGE_USE":
        return "Sessao privilegiada usada neste comando.", detail
    label = "Atualizacao de execucao."
    if status == "ERROR":
        label = "Falha durante a execucao."
    elif status == "WARN":
        label = "Execucao com aviso."
    return label, detail


def format_activity_log(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    if text.startswith("EXECUTANDO: "):
        command = text.split("EXECUTANDO: ", 1)[1].strip()
        return bullet(f"Ran `{command}`")
    if text.startswith("PIXEL: "):
        return f"{bullet('Vou verificar um pixel da tela.')}\n{child(text.split('PIXEL: ', 1)[1])}"
    if text.startswith("MEMORIA: "):
        detail = text.split("MEMORIA: ", 1)[1]
        return f"{bullet('Vou consultar ou salvar memoria local.')}\n{child(detail)}"

    match = LOG_LINE_RE.match(text)
    if match is None:
        return bullet(text)

    action = match.group("action")
    detail = match.group("detail")
    status = match.group("status")
    label, nested = _label_for_action(action, detail, status)
    return f"{bullet(label)}\n{child(nested)}"
