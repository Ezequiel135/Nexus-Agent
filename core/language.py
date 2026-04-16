from __future__ import annotations

import re

from .config import NexusConfig, normalize_response_language


PT_HINTS = {
    "abrir",
    "agora",
    "ajuda",
    "arruma",
    "atualiza",
    "bom",
    "boa",
    "como",
    "com",
    "está",
    "esta",
    "executa",
    "faz",
    "ingles",
    "inglês",
    "navegador",
    "obrigado",
    "oi",
    "olá",
    "ola",
    "para",
    "planejamento",
    "plano",
    "por",
    "porque",
    "portugues",
    "português",
    "preciso",
    "quero",
    "tarefa",
    "você",
    "voce",
}

EN_HINTS = {
    "and",
    "browser",
    "can",
    "english",
    "execute",
    "fix",
    "hello",
    "help",
    "how",
    "need",
    "open",
    "please",
    "plan",
    "run",
    "set",
    "task",
    "thanks",
    "update",
    "what",
    "why",
}

TOKEN_RE = re.compile(r"[a-zA-ZÀ-ÿ]+")


def detect_message_language(text: str) -> str:
    tokens = [token.lower() for token in TOKEN_RE.findall(text or "")]
    if not tokens:
        return "pt-BR"

    pt_score = sum(token in PT_HINTS for token in tokens)
    en_score = sum(token in EN_HINTS for token in tokens)

    if any(ord(char) > 127 for char in text or ""):
        pt_score += 1

    if en_score > pt_score:
        return "en"
    return "pt-BR"


def preferred_response_language(config: NexusConfig, latest_user_prompt: str | None = None) -> str:
    configured = normalize_response_language(getattr(config, "response_language", "auto"))
    if configured != "auto":
        return configured
    return detect_message_language(latest_user_prompt or "")


def language_instruction(config: NexusConfig, latest_user_prompt: str | None = None) -> str:
    target = preferred_response_language(config, latest_user_prompt)
    if target == "en":
        return (
            "Reply in English. Keep the tone direct and natural. "
            "If the user explicitly switches to Portuguese, follow the latest user language."
        )
    return (
        "Responda em portugues do Brasil. Seja direto e natural. "
        "Se o usuario mudar claramente para ingles, acompanhe o idioma mais recente."
    )
