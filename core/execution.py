from __future__ import annotations

from typing import TYPE_CHECKING

from .config import normalize_execution_profile

if TYPE_CHECKING:
    from .config import NexusConfig


PROFILE_SETTINGS = {
    "quick": {
        "label": "Dia a dia",
        "description": "Minimo de passos para tarefas simples, mouse, teclado, abrir app e execucoes curtas.",
        "plan_before_execute": False,
        "max_tool_rounds": 2,
        "max_plan_steps": 3,
    },
    "planned": {
        "label": "Profissional",
        "description": "Planejamento mais cuidadoso, preview de plano e fluxo completo com ate 6 rodadas.",
        "plan_before_execute": True,
        "max_tool_rounds": 6,
        "max_plan_steps": 8,
    },
}

VISUAL_SHORTCUT_HINTS = {
    "abrir",
    "apertar",
    "app",
    "aplicativo",
    "browser",
    "buscar",
    "clicar",
    "digitar",
    "janela",
    "mouse",
    "mostrar",
    "pesquisa",
    "programa",
    "teclado",
    "tela",
}

COMPLEX_HINTS = {
    "analisar",
    "auditar",
    "backup",
    "baixar",
    "configurar",
    "criar",
    "deploy",
    "documentar",
    "instalar",
    "investigar",
    "migrar",
    "organizar",
    "processar",
    "refatorar",
}

RISK_HINTS = {
    "apagar",
    "chmod",
    "chown",
    "deletar",
    "excluir",
    "git",
    "permiss",
    "remover",
    "root",
    "sudo",
}

PLAN_HINTS = {
    "como faria",
    "estrategia",
    "etapas",
    "passo a passo",
    "planeja",
    "planejar",
    "plano",
}


def profile_label(value: str | None) -> str:
    profile = normalize_execution_profile(value)
    return PROFILE_SETTINGS[profile]["label"]


def profile_description(value: str | None) -> str:
    profile = normalize_execution_profile(value)
    return PROFILE_SETTINGS[profile]["description"]


def apply_execution_profile(config: "NexusConfig", profile: str) -> str:
    normalized = normalize_execution_profile(profile)
    settings = PROFILE_SETTINGS[normalized]
    config.execution_profile = normalized
    config.plan_before_execute = bool(settings["plan_before_execute"])
    config.max_tool_rounds = int(settings["max_tool_rounds"])
    config.max_plan_steps = int(settings["max_plan_steps"])
    return normalized


def _lower_prompt(prompt: str) -> str:
    return " ".join((prompt or "").strip().lower().split())


def prompt_is_risky(prompt: str) -> bool:
    lowered = _lower_prompt(prompt)
    return any(token in lowered for token in RISK_HINTS)


def prompt_explicitly_requests_plan(prompt: str) -> bool:
    lowered = _lower_prompt(prompt)
    return any(token in lowered for token in PLAN_HINTS)


def prompt_is_visual_shortcut(prompt: str) -> bool:
    lowered = _lower_prompt(prompt)
    if not lowered:
        return False
    if any(token in lowered for token in VISUAL_SHORTCUT_HINTS):
        return True
    words = lowered.split()
    return len(words) <= 8 and any(token in lowered for token in {"abrir", "app", "programa"})


def prompt_is_complex(prompt: str) -> bool:
    lowered = _lower_prompt(prompt)
    words = lowered.split()
    if prompt_is_risky(lowered):
        return True
    if prompt_explicitly_requests_plan(lowered):
        return True
    if any(token in lowered for token in COMPLEX_HINTS):
        return True
    if prompt_is_visual_shortcut(lowered):
        return False
    if len(words) >= 16:
        return True
    connectors = sum(lowered.count(token) for token in (" depois ", " entao ", " em seguida ", " ao mesmo tempo "))
    return connectors >= 2


def should_preview_plan(config: "NexusConfig", prompt: str) -> bool:
    profile = normalize_execution_profile(getattr(config, "execution_profile", "planned"))
    if prompt_explicitly_requests_plan(prompt):
        return True
    if prompt_is_risky(prompt):
        return True
    if profile == "quick":
        return False
    return bool(getattr(config, "plan_before_execute", True) and prompt_is_complex(prompt))
