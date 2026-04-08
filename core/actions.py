from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .config import NexusPaths
from .logging_utils import log_event
from .memory import remember, search_memory
from .safeguards import command_is_safe


class AcoesAgente:
    def __init__(self) -> None:
        NexusPaths.ensure()
        self._event_callback = None

    def set_event_callback(self, callback) -> None:
        self._event_callback = callback

    def _emit(self, text: str) -> None:
        if self._event_callback is not None:
            self._event_callback(text)

    @staticmethod
    def tool_schemas() -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "executar_comando",
                    "description": "Executa um comando de shell local com captura de stdout e stderr. Use para instalar, listar, mover, inspecionar sistema e operar no terminal.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "comando": {"type": "string"},
                        },
                        "required": ["comando"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gerenciar_arquivos",
                    "description": "Le, escreve, deleta, move ou lista arquivos locais. Use quando a tarefa envolver editar codigo, criar documentos, reorganizar pastas ou inspecionar arquivos.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "acao": {"type": "string"},
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                            "target_path": {"type": "string"},
                        },
                        "required": ["acao", "path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "controle_periferico",
                    "description": "Controla mouse, teclado e captura de tela. Acoes aceitas: clicar, digitar, mover_mouse, screenshot, posicao_cursor. Use quando a tarefa exigir mexer no PC visualmente.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "acao": {"type": "string"},
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                            "texto": {"type": "string"},
                        },
                        "required": ["acao"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "memoria_local",
                    "description": "Salva ou busca memoria local persistente do usuario. Use quando o usuario pedir para lembrar de algo, guardar uma preferencia ou recuperar contexto salvo.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "acao": {"type": "string"},
                            "texto": {"type": "string"},
                            "consulta": {"type": "string"},
                        },
                        "required": ["acao"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "verificar_pixel",
                    "description": "Retorna a cor RGB de um pixel da tela. Use para verificar se um botao, janela ou indicador mudou de cor depois de uma acao.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                        },
                        "required": ["x", "y"],
                    },
                },
            },
        ]

    @staticmethod
    def capabilities_summary() -> str:
        return (
            "Ferramentas locais disponiveis: "
            "1) executar_comando para operar no shell; "
            "2) gerenciar_arquivos para ler, escrever, mover e deletar arquivos; "
            "3) controle_periferico para clicar, digitar, mover o mouse, capturar screenshot e ler a posicao do cursor; "
            "4) memoria_local para salvar e buscar lembrancas persistentes; "
            "5) verificar_pixel para ler a cor RGB de um ponto da tela. "
            "Se a tarefa mencionar tela, botao, navegador, janela, clicar, digitar no PC, mover mouse ou verificar cor, use controle_periferico e verificar_pixel em vez de responder apenas em texto."
        )

    def executar_comando(self, comando: str) -> str:
        allowed, reason = command_is_safe(comando)
        if not allowed:
            line = log_event("BLOQUEADO", comando, status="BLOCKED")
            self._emit(line)
            return json.dumps({"ok": False, "erro": reason, "log": line}, ensure_ascii=False)

        log_event("EXECUTANDO", comando)
        self._emit(f"EXECUTANDO: {comando}")
        result = subprocess.run(comando, shell=True, capture_output=True, text=True)
        payload = {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
        line = log_event("RESULTADO", f"{comando} rc={result.returncode}", status="OK" if result.returncode == 0 else "ERROR")
        self._emit(line)
        return json.dumps(payload, ensure_ascii=False)

    def gerenciar_arquivos(self, acao: str, path: str, content: str | None = None, target_path: str | None = None) -> str:
        target = Path(path).expanduser()
        line = log_event("ARQUIVO", f"{acao} {target}")
        self._emit(line)

        if acao == "ler":
            return target.read_text(encoding="utf-8")
        if acao == "escrever":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content or "", encoding="utf-8")
            return f"Arquivo salvo em {target}"
        if acao == "listar":
            if not target.exists():
                return "[]"
            return json.dumps(sorted(item.name for item in target.iterdir()), ensure_ascii=False)
        if acao == "mover":
            if not target_path:
                raise ValueError("target_path e obrigatorio para mover")
            destination = Path(target_path).expanduser()
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(destination))
            return f"Movido para {destination}"
        if acao == "deletar":
            if target.is_dir():
                trash_target = NexusPaths.trash_dir / target.name
                shutil.move(str(target), str(trash_target))
                return f"Diretorio movido para lixeira segura: {trash_target}"
            if target.exists():
                trash_target = NexusPaths.trash_dir / target.name
                shutil.move(str(target), str(trash_target))
                return f"Arquivo movido para lixeira segura: {trash_target}"
            return "Arquivo inexistente"
        raise ValueError(f"Acao de arquivo desconhecida: {acao}")

    def controle_periferico(self, acao: str, x: int | None = None, y: int | None = None, texto: str | None = None) -> str:
        line = log_event("PERIFERICO", f"{acao} x={x} y={y}")
        self._emit(line)
        from pc_remote_agent import runtime

        if acao == "clicar":
            runtime.click(x=x, y=y)
            return "Clique executado"
        if acao == "digitar":
            runtime.type_text(texto or "")
            return "Texto digitado"
        if acao == "mover_mouse":
            if x is None or y is None:
                raise ValueError("x e y sao obrigatorios para mover_mouse")
            runtime.move_to(x, y)
            return "Mouse movido"
        if acao == "screenshot":
            image, _, _ = runtime.screen_image()
            shot_path = NexusPaths.base_dir / "last_screenshot.png"
            image.save(shot_path)
            return f"Screenshot salva em {shot_path}"
        if acao == "posicao_cursor":
            pos = runtime.mouse_position()
            return json.dumps({"x": int(pos[0]), "y": int(pos[1])}, ensure_ascii=False)
        raise ValueError(f"Acao periferica desconhecida: {acao}")

    def verificar_pixel(self, x: int, y: int) -> str:
        from pc_remote_agent import runtime

        image, _, _ = runtime.screen_image()
        r, g, b = image.getpixel((x, y))
        self._emit(f"PIXEL: ({x},{y}) -> rgb({r},{g},{b})")
        return json.dumps({"x": x, "y": y, "rgb": [r, g, b]}, ensure_ascii=False)

    def memoria_local(self, acao: str, texto: str | None = None, consulta: str | None = None) -> str:
        if acao == "salvar":
            if not texto:
                raise ValueError("texto e obrigatorio para salvar memoria")
            item = remember(texto, source="assistant", kind="memory")
            self._emit(f"MEMORIA: salvo -> {item.text}")
            return json.dumps({"ok": True, "saved": item.text, "timestamp": item.timestamp}, ensure_ascii=False)
        if acao == "buscar":
            items = search_memory(consulta or "")
            payload = [{"timestamp": item.timestamp, "text": item.text, "kind": item.kind} for item in items]
            self._emit(f"MEMORIA: busca por '{consulta or ''}' retornou {len(payload)} itens")
            return json.dumps(payload, ensure_ascii=False)
        raise ValueError(f"Acao de memoria desconhecida: {acao}")

    def dispatch_tool(self, name: str, arguments: dict[str, Any]) -> str:
        if name == "executar_comando":
            return self.executar_comando(**arguments)
        if name == "gerenciar_arquivos":
            return self.gerenciar_arquivos(**arguments)
        if name == "controle_periferico":
            return self.controle_periferico(**arguments)
        if name == "memoria_local":
            return self.memoria_local(**arguments)
        if name == "verificar_pixel":
            return self.verificar_pixel(**arguments)
        raise ValueError(f"Ferramenta desconhecida: {name}")
