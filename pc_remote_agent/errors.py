import subprocess


def friendly_error_message(exc):
    text = str(exc).strip()

    if isinstance(exc, PermissionError):
        return "Permissao negada. A IA precisa pedir acesso antes de tentar essa acao."
    if isinstance(exc, FileNotFoundError):
        return "Arquivo, pasta ou comando nao encontrado. Verifique o caminho ou instale a dependencia."
    if isinstance(exc, subprocess.TimeoutExpired):
        return "A acao demorou mais do que o permitido. Tente novamente com menos passos ou revise o alvo."
    if "not found" in text.lower() and "xdotool" in text.lower():
        return "A dependencia xdotool nao esta instalada. No Linux, instale xdotool; no Windows, use o modo nativo."
    if "playwright" in text.lower():
        return "Playwright nao esta instalado. Use OCR normal ou instale playwright para modo DOM."
    if "display" in text.lower():
        return "Nao foi possivel acessar a tela grafica. Verifique DISPLAY, permissao do desktop ou modo headless."
    if "No such file" in text:
        return "O caminho informado nao existe."
    if "Operation not permitted" in text:
        return "O sistema bloqueou a acao. A IA precisa de permissao ou de um comando permitido."
    if text:
        return f"Falha ao executar a acao: {text}"
    return "Falha desconhecida ao executar a acao."
