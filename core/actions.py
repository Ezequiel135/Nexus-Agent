from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .config import NexusConfig, NexusPaths
from .logging_utils import log_event
from .mcp import call_mcp_tool, list_mcp_resources, list_mcp_servers, list_mcp_tools, read_mcp_resource
from .memory import remember, search_memory
from .safeguards import command_is_safe
from .tool_registry import ToolRegistry


class AcoesAgente(ToolRegistry):
    def __init__(self, config: NexusConfig | None = None) -> None:
        super().__init__()
        NexusPaths.ensure()
        self.config = config
        self._event_callback = None
        self._register_tools()

    def set_event_callback(self, callback) -> None:
        self._event_callback = callback

    def _emit(self, text: str) -> None:
        if self._event_callback is not None:
            self._event_callback(text)

    def _register_tools(self) -> None:
        self.register(
            name="executar_comando",
            description="Executa um comando de shell local com captura de stdout e stderr. Use para instalar, listar, mover, inspecionar sistema e operar no terminal.",
            parameters={
                "type": "object",
                "properties": {
                    "comando": {"type": "string", "description": "Comando shell a executar"},
                },
                "required": ["comando"],
            },
            func=self.executar_comando,
        )
        self.register(
            name="gerenciar_arquivos",
            description="Le, escreve, deleta, move ou lista arquivos locais. Use quando a tarefa envolver editar codigo, criar documentos, reorganizar pastas ou inspecionar arquivos.",
            parameters={
                "type": "object",
                "properties": {
                    "acao": {"type": "string", "enum": ["ler", "escrever", "listar", "mover", "deletar"]},
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "target_path": {"type": "string"},
                },
                "required": ["acao", "path"],
            },
            func=self.gerenciar_arquivos,
        )
        self.register(
            name="controle_periferico",
            description="Controla mouse, teclado e captura de tela. Acoes: clicar, digitar, mover_mouse, screenshot, posicao_cursor.",
            parameters={
                "type": "object",
                "properties": {
                    "acao": {"type": "string", "enum": ["clicar", "digitar", "mover_mouse", "screenshot", "posicao_cursor"]},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "texto": {"type": "string"},
                },
                "required": ["acao"],
            },
            func=self.controle_periferico,
        )
        self.register(
            name="memoria_local",
            description="Salva ou busca memoria local persistente do usuario.",
            parameters={
                "type": "object",
                "properties": {
                    "acao": {"type": "string", "enum": ["salvar", "buscar", "limpar"]},
                    "texto": {"type": "string"},
                    "consulta": {"type": "string"},
                },
                "required": ["acao"],
            },
            func=self.memoria_local,
        )
        self.register(
            name="verificar_pixel",
            description="Retorna a cor RGB de um pixel da tela.",
            parameters={
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
                "required": ["x", "y"],
            },
            func=self.verificar_pixel,
        )
        self.register(
            name="consultar_mcp",
            description=(
                "Consulta servidores MCP configurados no host. "
                "Acoes: listar_servidores, listar_recursos, ler_recurso, listar_ferramentas, chamar_ferramenta."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "acao": {
                        "type": "string",
                        "enum": [
                            "listar_servidores",
                            "listar_recursos",
                            "ler_recurso",
                            "listar_ferramentas",
                            "chamar_ferramenta",
                        ],
                    },
                    "servidor": {"type": "string"},
                    "uri": {"type": "string"},
                    "ferramenta": {"type": "string"},
                    "argumentos": {"type": "object"},
                },
                "required": ["acao"],
            },
            func=self.consultar_mcp,
        )
        self.register(
            name="gerenciar_notebooks",
            description=(
                "Cria, lista, le, adiciona celulas e executa notebooks Jupyter (.ipynb) no host local. "
                "Use quando a tarefa envolver analise, prototipos em Python ou integracao com Jupyter."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "acao": {
                        "type": "string",
                        "enum": [
                            "listar",
                            "criar",
                            "ler",
                            "adicionar_codigo",
                            "adicionar_markdown",
                            "executar",
                        ],
                    },
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "title": {"type": "string"},
                    "kernel_name": {"type": "string"},
                    "timeout": {"type": "integer"},
                    "cwd": {"type": "string"},
                },
                "required": ["acao"],
            },
            func=self.gerenciar_notebooks,
        )

    def dispatch_tool(self, name: str, arguments: dict[str, Any]) -> str:
        return self.executar(name, arguments)

    # --- Ferramentas ---

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
            if not target.exists():
                return json.dumps({"ok": False, "erro": f"Arquivo nao encontrado: {target}"}, ensure_ascii=False)
            return target.read_text(encoding="utf-8")
        if acao == "escrever":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content or "", encoding="utf-8")
            return json.dumps({"ok": True, "path": str(target)}, ensure_ascii=False)
        if acao == "listar":
            if not target.exists():
                return "[]"
            return json.dumps(sorted([item.name for item in target.iterdir()], key=lambda x: x.lower()), ensure_ascii=False)
        if acao == "mover":
            if not target_path:
                raise ValueError("target_path e obrigatorio para mover")
            source = Path(path).expanduser()
            destination = Path(target_path).expanduser()
            if not source.exists():
                return json.dumps({"ok": False, "erro": f"Arquivo nao encontrado: {source}"}, ensure_ascii=False)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            return json.dumps({"ok": True, "from": str(source), "to": str(destination)}, ensure_ascii=False)
        if acao == "deletar":
            target = Path(path).expanduser()
            if not target.exists():
                return json.dumps({"ok": False, "erro": "Arquivo inexistente"}, ensure_ascii=False)
            trash_target = NexusPaths.trash_dir / target.name
            if target.is_dir():
                shutil.move(str(target), str(trash_target))
                return json.dumps({"ok": True, "moved_to": str(trash_target), "type": "diretorio"}, ensure_ascii=False)
            else:
                shutil.move(str(target), str(trash_target))
                return json.dumps({"ok": True, "moved_to": str(trash_target), "type": "arquivo"}, ensure_ascii=False)
        raise ValueError(f"Acao de arquivo desconhecida: {acao}")

    def controle_periferico(self, acao: str, x: int | None = None, y: int | None = None, texto: str | None = None) -> str:
        line = log_event("PERIFERICO", f"{acao} x={x} y={y}")
        self._emit(line)
        from pc_remote_agent import runtime

        if acao == "clicar":
            runtime.click(x=x, y=y)
            return json.dumps({"ok": True, "action": "clicar", "x": x, "y": y}, ensure_ascii=False)
        if acao == "digitar":
            runtime.type_text(texto or "")
            return json.dumps({"ok": True, "action": "digitar", "text_len": len(texto or "")}, ensure_ascii=False)
        if acao == "mover_mouse":
            if x is None or y is None:
                return json.dumps({"ok": False, "erro": "x e y sao obrigatorios"}, ensure_ascii=False)
            runtime.move_to(x, y)
            return json.dumps({"ok": True, "action": "mover_mouse", "x": x, "y": y}, ensure_ascii=False)
        if acao == "screenshot":
            image, _, _ = runtime.screen_image()
            shot_path = NexusPaths.base_dir / "last_screenshot.png"
            image.save(shot_path)
            return json.dumps({"ok": True, "path": str(shot_path)}, ensure_ascii=False)
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
                return json.dumps({"ok": False, "erro": "texto e obrigatorio"}, ensure_ascii=False)
            item = remember(texto, source="assistant", kind="memory")
            self._emit(f"MEMORIA: salvo -> {item.text}")
            return json.dumps({"ok": True, "saved": item.text, "timestamp": item.timestamp}, ensure_ascii=False)
        if acao == "buscar":
            items = search_memory(consulta or "")
            payload = [{"timestamp": item.timestamp, "text": item.text, "kind": item.kind} for item in items]
            self._emit(f"MEMORIA: busca por '{consulta or ''}' retornou {len(payload)} itens")
            return json.dumps(payload, ensure_ascii=False)
        if acao == "limpar":
            from .memory import clear_memory
            clear_memory()
            return json.dumps({"ok": True, "cleared": True}, ensure_ascii=False)
        raise ValueError(f"Acao de memoria desconhecida: {acao}")

    def consultar_mcp(
        self,
        acao: str,
        servidor: str | None = None,
        uri: str | None = None,
        ferramenta: str | None = None,
        argumentos: dict[str, Any] | None = None,
    ) -> str:
        if self.config is None:
            return json.dumps({"ok": False, "erro": "Configuracao MCP indisponivel no runtime."}, ensure_ascii=False)

        line = log_event("MCP", f"{acao} servidor={servidor or '-'}")
        self._emit(line)

        if acao == "listar_servidores":
            servers = list_mcp_servers(self.config)
            return json.dumps({"ok": True, "servers": servers}, ensure_ascii=False)
        if acao == "listar_recursos":
            if not servidor:
                return json.dumps({"ok": False, "erro": "servidor e obrigatorio"}, ensure_ascii=False)
            resources = list_mcp_resources(self.config, servidor)
            return json.dumps({"ok": True, "resources": resources}, ensure_ascii=False)
        if acao == "ler_recurso":
            if not servidor or not uri:
                return json.dumps({"ok": False, "erro": "servidor e uri sao obrigatorios"}, ensure_ascii=False)
            payload = read_mcp_resource(self.config, servidor, uri)
            return json.dumps({"ok": True, **payload}, ensure_ascii=False)
        if acao == "listar_ferramentas":
            if not servidor:
                return json.dumps({"ok": False, "erro": "servidor e obrigatorio"}, ensure_ascii=False)
            tools = list_mcp_tools(self.config, servidor)
            return json.dumps({"ok": True, "tools": tools}, ensure_ascii=False)
        if acao == "chamar_ferramenta":
            if not servidor or not ferramenta:
                return json.dumps({"ok": False, "erro": "servidor e ferramenta sao obrigatorios"}, ensure_ascii=False)
            payload = call_mcp_tool(self.config, servidor, ferramenta, argumentos or {})
            return json.dumps({"ok": True, **payload}, ensure_ascii=False)
        raise ValueError(f"Acao MCP desconhecida: {acao}")

    def gerenciar_notebooks(
        self,
        acao: str,
        path: str | None = None,
        content: str | None = None,
        title: str | None = None,
        kernel_name: str | None = None,
        timeout: int | None = None,
        cwd: str | None = None,
    ) -> str:
        from .notebooks import append_cell, create_notebook, execute_notebook, list_notebooks, read_notebook

        line = log_event("NOTEBOOK", f"{acao} {path or '-'}")
        self._emit(line)

        if acao == "listar":
            payload = list_notebooks(path or None)
            return json.dumps({"ok": True, "notebooks": payload}, ensure_ascii=False)
        if acao == "criar":
            if not path:
                return json.dumps({"ok": False, "erro": "path e obrigatorio"}, ensure_ascii=False)
            payload = create_notebook(path, title=title or "", kernel_name=(kernel_name or "").strip() or "python3")
            return json.dumps(payload, ensure_ascii=False)
        if acao == "ler":
            if not path:
                return json.dumps({"ok": False, "erro": "path e obrigatorio"}, ensure_ascii=False)
            payload = read_notebook(path)
            return json.dumps(payload, ensure_ascii=False)
        if acao == "adicionar_codigo":
            if not path or content is None:
                return json.dumps({"ok": False, "erro": "path e content sao obrigatorios"}, ensure_ascii=False)
            payload = append_cell(path, content, cell_type="code")
            return json.dumps(payload, ensure_ascii=False)
        if acao == "adicionar_markdown":
            if not path or content is None:
                return json.dumps({"ok": False, "erro": "path e content sao obrigatorios"}, ensure_ascii=False)
            payload = append_cell(path, content, cell_type="markdown")
            return json.dumps(payload, ensure_ascii=False)
        if acao == "executar":
            if not path:
                return json.dumps({"ok": False, "erro": "path e obrigatorio"}, ensure_ascii=False)
            payload = execute_notebook(
                path,
                kernel_name=(kernel_name or "").strip(),
                timeout=int(timeout or 300),
                cwd=(cwd or "").strip(),
            )
            return json.dumps(payload, ensure_ascii=False)
        raise ValueError(f"Acao de notebook desconhecida: {acao}")
