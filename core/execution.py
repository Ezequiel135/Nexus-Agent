from __future__ import annotations

import re
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
    "abre",
    "abrir",
    "abra",
    "abri",
    "application",
    "apertar",
    "app",
    "aplicativo",
    "browser",
    "buscar",
    "click",
    "clicar",
    "digitar",
    "fecha",
    "fechar",
    "janela",
    "keyboard",
    "mouse",
    "open",
    "close",
    "pesquisa",
    "programa",
    "screen",
    "search",
    "show",
    "tela",
    "teclado",
    "type",
    "window",
    "browser",
    "mostrar",
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
    "migrate",
    "migrar",
    "organize",
    "organizar",
    "process",
    "processar",
    "refatorar",
    "refactor",
    "update",
    "atualizar",
    "fix",
    "corrigir",
}

RISK_HINTS = {
    "apagar",
    "chmod",
    "chown",
    "deletar",
    "delete",
    "excluir",
    "permissao",
    "permiss",
    "permission",
    "remover",
    "remove",
    "root",
    "sudo",
}

PLAN_HINTS = {
    "como faria",
    "estrategia",
    "etapas",
    "how would you",
    "passo a passo",
    "plan",
    "como faria",
    "estrategia",
    "etapas",
    "passo a passo",
    "planeja",
    "planejar",
    "plano",
    "steps",
    "strategy",
}

EXECUTION_HINTS = VISUAL_SHORTCUT_HINTS | COMPLEX_HINTS | {
    "ajustar",
    "arrumar",
    "atualiza",
    "atualizar",
    "change",
    "consertar",
    "create",
    "criar",
    "executa",
    "executar",
    "fix",
    "install",
    "move",
    "mover",
    "organize",
    "run",
    "set",
    "trocar",
    "update",
}

COMMAND_STYLE_PREFIXES = {
    "apt",
    "bun",
    "brew",
    "cargo",
    "chmod",
    "chown",
    "cp",
    "docker",
    "gh",
    "git",
    "go",
    "kubectl",
    "ls",
    "make",
    "mkdir",
    "mv",
    "node",
    "npm",
    "npx",
    "pnpm",
    "pip",
    "pip3",
    "python",
    "python3",
    "rm",
    "sed",
    "sudo",
    "systemctl",
    "touch",
    "uv",
    "winget",
    "yarn",
}

CASUAL_EXACT_HINTS = {
    "blz",
    "boa noite",
    "boa tarde",
    "bom dia",
    "e ai",
    "e aí",
    "hello",
    "hey",
    "hi",
    "oi",
    "oi nexus",
    "ola",
    "olá",
    "thanks",
    "thank you",
    "tudo bem",
    "valeu",
}

CASUAL_TOKENS = {
    "ai",
    "aí",
    "blz",
    "boa",
    "bom",
    "dia",
    "e",
    "hello",
    "hey",
    "hi",
    "nexus",
    "night",
    "noite",
    "oi",
    "ola",
    "olá",
    "tarde",
    "thanks",
    "thank",
    "thankyou",
    "tudo",
    "valeu",
    "well",
}

QUESTION_LEADS = {"como", "what", "why", "when", "where", "who", "qual", "quais", "por", "porque"}
GIT_RISK_PATTERN = re.compile(r"\bgit\s+(add|checkout|clean|clone|commit|merge|pull|push|rebase|reset|restore|switch)\b")
PUNCT_RE = re.compile(r"[^\w\s./:+-]+", re.UNICODE)
DIRECT_BROWSER_PATTERNS = (
    re.compile(r"\b(abre|abrir|abra|abri|open|start|launch)\b(?:\s+\w+){0,4}?\s*\b(google\s+chrome|chrome)\b", re.IGNORECASE),
    re.compile(r"\b(abre|abrir|abra|abri|open|start|launch)\b(?:\s+\w+){0,4}?\s*\b(chromium)\b", re.IGNORECASE),
    re.compile(r"\b(abre|abrir|abra|abri|open|start|launch)\b(?:\s+\w+){0,4}?\s*\b(firefox)\b", re.IGNORECASE),
    re.compile(r"\b(abre|abrir|abra|abri|open|start|launch)\b(?:\s+\w+){0,4}?\s*\b(edge|microsoft\s+edge)\b", re.IGNORECASE),
)
DIRECT_CLOSE_BROWSER_PATTERNS = (
    re.compile(r"\b(fecha|fechar|feche|close|quit|exit)\b(?:\s+\w+){0,6}?\s*\b(google\s+chrome|chrome)\b", re.IGNORECASE),
    re.compile(r"\b(fecha|fechar|feche|close|quit|exit)\b(?:\s+\w+){0,6}?\s*\b(chromium)\b", re.IGNORECASE),
    re.compile(r"\b(fecha|fechar|feche|close|quit|exit)\b(?:\s+\w+){0,6}?\s*\b(firefox)\b", re.IGNORECASE),
    re.compile(r"\b(fecha|fechar|feche|close|quit|exit)\b(?:\s+\w+){0,6}?\s*\b(edge|microsoft\s+edge)\b", re.IGNORECASE),
)
DIRECT_APP_PATTERNS = (
    re.compile(r"^\s*(?:abre|abrir|abra|abri|open|start|launch)\s+(.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:fecha|fechar|feche|close|quit|exit)\s+(.+?)\s*$", re.IGNORECASE),
)
BROWSER_TARGET_ALIASES = {
    "google chrome": "chrome",
    "chrome": "chrome",
    "chromium": "chromium",
    "firefox": "firefox",
    "edge": "edge",
    "microsoft edge": "edge",
}
GENERIC_APP_REQUEST_PATTERNS = (
    re.compile(r"\b(?:abre|abrir|abra|abri|open|start|launch)\b(?:\s+\w+){0,4}?\b(?:algum|alguma|qualquer)\s+(?:app|aplicativo|programa)\b", re.IGNORECASE),
    re.compile(r"\b(?:abre|abrir|abra|abri|open|start|launch)\b(?:\s+\w+){0,4}?\b(?:app|aplicativo|programa)\s+(?:do|no)\s+meu\s+pc\b", re.IGNORECASE),
)
APP_FILLER_PREFIXES = ("o", "a", "os", "as", "um", "uma", "meu", "minha")
APP_FILLER_SUFFIXES = (
    " do meu pc",
    " no meu pc",
    " aqui",
    " pra mim",
    " para mim",
    " que esta aberto",
    " que está aberto",
    " que ta aberto",
    " que tá aberto",
    " aberto",
    " aberta",
)
GENERIC_APP_TAILS = {
    "app",
    "aplicativo",
    "programa",
    "janela",
    "launcher",
    "menu",
    "menu de aplicativos",
    "algum app",
    "algum aplicativo",
    "algum programa",
    "qualquer app",
    "qualquer aplicativo",
    "qualquer programa",
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


def _normalized_prompt(prompt: str) -> str:
    lowered = _lower_prompt(prompt)
    return " ".join(PUNCT_RE.sub(" ", lowered).split())


def prompt_is_smalltalk(prompt: str) -> bool:
    normalized = _normalized_prompt(prompt)
    if not normalized:
        return False
    if normalized in CASUAL_EXACT_HINTS:
        return True
    words = normalized.split()
    return bool(words) and len(words) <= 4 and all(word in CASUAL_TOKENS for word in words)


def prompt_looks_like_command(prompt: str) -> bool:
    normalized = _normalized_prompt(prompt)
    if not normalized:
        return False
    words = normalized.split()
    if not words or words[0] in QUESTION_LEADS:
        return False
    if words[0] not in COMMAND_STYLE_PREFIXES:
        return False
    return len(words) <= 12 and "?" not in (prompt or "")


def prompt_requests_execution(prompt: str) -> bool:
    normalized = _normalized_prompt(prompt)
    if not normalized or prompt_is_smalltalk(normalized):
        return False
    if prompt_looks_like_command(normalized):
        return True
    if prompt_is_visual_shortcut(normalized):
        return True
    if any(token in normalized for token in EXECUTION_HINTS):
        return True
    return any(marker in normalized for marker in ("~/", "./", "/", ".py", ".sh", ".json"))


def prompt_is_risky(prompt: str) -> bool:
    normalized = _normalized_prompt(prompt)
    if not normalized or prompt_is_smalltalk(normalized):
        return False
    if GIT_RISK_PATTERN.search(normalized):
        return True
    if not prompt_requests_execution(normalized):
        return False
    return any(token in normalized for token in RISK_HINTS)


def prompt_explicitly_requests_plan(prompt: str) -> bool:
    normalized = _normalized_prompt(prompt)
    return any(token in normalized for token in PLAN_HINTS)


def prompt_is_visual_shortcut(prompt: str) -> bool:
    normalized = _normalized_prompt(prompt)
    if not normalized:
        return False
    if any(token in normalized for token in VISUAL_SHORTCUT_HINTS):
        return True
    words = normalized.split()
    return len(words) <= 8 and any(token in normalized for token in {"abrir", "app", "open", "programa"})


def prompt_is_complex(prompt: str) -> bool:
    normalized = _normalized_prompt(prompt)
    words = normalized.split()
    if prompt_is_risky(normalized):
        return True
    if prompt_explicitly_requests_plan(normalized):
        return True
    if any(token in normalized for token in COMPLEX_HINTS):
        return True
    if prompt_is_visual_shortcut(normalized):
        return False
    if not prompt_requests_execution(normalized):
        return False
    if len(words) >= 16:
        return True
    connectors = sum(
        normalized.count(token)
        for token in (
            " depois ",
            " entao ",
            " em seguida ",
            " ao mesmo tempo ",
            " then ",
            " after that ",
            " next ",
        )
    )
    return connectors >= 2


def should_preview_plan(config: "NexusConfig", prompt: str) -> bool:
    profile = normalize_execution_profile(getattr(config, "execution_profile", "planned"))
    if prompt_is_smalltalk(prompt):
        return False
    if prompt_explicitly_requests_plan(prompt):
        return True
    if prompt_is_risky(prompt):
        return True
    if not prompt_requests_execution(prompt):
        return False
    if profile == "quick":
        return False
    return bool(getattr(config, "plan_before_execute", True) and prompt_is_complex(prompt))


def extract_direct_browser_target(prompt: str) -> str | None:
    raw = (prompt or "").strip()
    if not raw:
        return None
    for pattern in DIRECT_BROWSER_PATTERNS:
        match = pattern.search(raw)
        if match:
            return BROWSER_TARGET_ALIASES.get(match.group(2).strip().lower())
    return None


def extract_direct_close_browser_target(prompt: str) -> str | None:
    raw = (prompt or "").strip()
    if not raw:
        return None
    for pattern in DIRECT_CLOSE_BROWSER_PATTERNS:
        match = pattern.search(raw)
        if match:
            return BROWSER_TARGET_ALIASES.get(match.group(2).strip().lower())
    return None


def extract_direct_app_target(prompt: str) -> str | None:
    raw = (prompt or "").strip()
    if not raw:
        return None
    if any(pattern.search(raw) for pattern in GENERIC_APP_REQUEST_PATTERNS):
        return "__launcher__"
    if "?" in raw:
        return None
    for pattern in DIRECT_APP_PATTERNS:
        match = pattern.match(raw)
        if not match:
            continue
        target = " ".join(match.group(1).strip().lower().split())
        first_word, _, remainder = target.partition(" ")
        if first_word in APP_FILLER_PREFIXES and remainder:
            target = remainder.strip()
        for suffix in APP_FILLER_SUFFIXES:
            if target.endswith(suffix):
                target = target[: -len(suffix)].strip()
                break
        target = target.strip(" .,:;!\"'")
        if not target:
            return "__launcher__"
        if target in BROWSER_TARGET_ALIASES:
            return None
        if target in GENERIC_APP_TAILS:
            return "__launcher__"
        if target.startswith(("algum ", "alguma ", "qualquer ")):
            return "__launcher__"
        return target
    return None


def extract_direct_visual_shortcut(prompt: str) -> tuple[str, str] | None:
    close_browser_target = extract_direct_close_browser_target(prompt)
    if close_browser_target:
        return ("fechar_app", close_browser_target)
    browser_target = extract_direct_browser_target(prompt)
    if browser_target:
        return ("abrir_app", browser_target)
    app_target = extract_direct_app_target(prompt)
    if app_target == "__launcher__":
        return ("atalho_teclado", "win")
    if app_target:
        lowered = _lower_prompt(prompt)
        if any(token in lowered.split() for token in {"fecha", "fechar", "feche", "close", "quit", "exit"}):
            return ("fechar_app", app_target)
        return ("abrir_app", app_target)
    return None
