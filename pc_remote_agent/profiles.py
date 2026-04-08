PROFILES = {
    "default": {
        "chat_region": (0.28, 0.14, 0.90, 0.88),
        "ready_anchors": ("ok",),
    },
    "chatgpt": {
        "window_keywords": ("chatgpt", "codex e chatgpt"),
        "chat_region": (0.28, 0.12, 0.90, 0.88),
        "ready_anchors": (
            "pergunte alguma coisa",
            "chatgpt pode cometer erros",
            "novo chat",
            "compartilhar",
        ),
    },
    "youtube": {
        "window_keywords": ("youtube",),
        "chat_region": (0.67, 0.18, 0.98, 0.92),
        "ready_anchors": (
            "pesquisar",
            "inscrever-se",
            "gostei",
            "comentarios",
        ),
    },
    "google": {
        "window_keywords": ("google", "pesquisa google"),
        "chat_region": (0.18, 0.18, 0.86, 0.88),
        "ready_anchors": (
            "pesquisar",
            "ferramentas",
            "imagens",
        ),
    },
}


def profile_for_window(window_name):
    lower = (window_name or "").lower()
    for name, profile in PROFILES.items():
        for keyword in profile.get("window_keywords", ()):
            if keyword in lower:
                return name, profile
    return "default", PROFILES["default"]
