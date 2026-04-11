from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import NexusConfig, NexusPaths
from .logging_utils import log_event
from .mcp import call_mcp_tool, list_mcp_resources, list_mcp_servers, list_mcp_tools, read_mcp_resource
from .memory import remember, search_memory
from .safeguards import (
    PATH_LIKE_RE,
    command_assessment,
    ensure_safe_write_path,
    normalize_user_path,
)
from .tool_registry import ToolRegistry

COMMAND_POLL_INTERVAL_SECONDS = 0.1
DEFAULT_COMMAND_TIMEOUT_SECONDS = 120


class CancelledExecution(RuntimeError):
    pass


class AcoesAgente(ToolRegistry):
    def __init__(self, config: NexusConfig | None = None) -> None:
        super().__init__()
        NexusPaths.ensure()
        self.config = config
        self._event_callback = None
        self._cancel_event: threading.Event | None = None
        self._register_tools()

    def set_event_callback(self, callback) -> None:
        self._event_callback = callback

    def set_cancel_event(self, cancel_event: threading.Event | None) -> None:
        self._cancel_event = cancel_event

    def _emit(self, text: str) -> None:
        if self._event_callback is not None:
            self._event_callback(text)

    def _cancelled(self) -> bool:
        return bool(self._cancel_event and self._cancel_event.is_set())

    @staticmethod
    def _json(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False)

    def _register_tools(self) -> None:
        self.register(
            name="executar_comando",
            description=(
                "Executa um comando shell local seguro com whitelist, timeout, logs de auditoria e dry-run. "
                "Comandos que modificam o sistema exigem confirmacao/dry-run."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "comando": {"type": "string", "description": "Comando shell a executar"},
                    "timeout": {"type": "integer", "description": "Timeout opcional em segundos"},
                    "dry_run": {"type": "boolean", "description": "Se true, apenas mostra o que faria"},
                },
                "required": ["comando"],
            },
            func=self.executar_comando,
        )
        self.register(
            name="gerenciar_arquivos",
            description=(
                "Le, escreve, deleta, move ou lista arquivos locais com saneamento de path, backup automatico e dry-run."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "acao": {"type": "string", "enum": ["ler", "escrever", "listar", "mover", "deletar"]},
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "target_path": {"type": "string"},
                    "dry_run": {"type": "boolean"},
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
        if self._cancelled():
            raise CancelledExecution("Execucao cancelada pelo usuario.")
        return self.executar(name, arguments)

    def _effective_dry_run(self, requested: bool | None = None) -> bool:
        if requested is not None:
            return bool(requested)
        return bool(self.config.dry_run) if self.config is not None else False

    def _candidate_paths_from_argv(self, argv: list[str]) -> list[Path]:
        paths: list[Path] = []
        for token in argv[1:]:
            if token.startswith("-") or not PATH_LIKE_RE.search(token):
                continue
            try:
                candidate = normalize_user_path(token)
            except ValueError:
                continue
            paths.append(candidate)
        return paths

    def _create_backup_snapshot(self, target: Path, *, reason: str) -> str | None:
        if not target.exists():
            return None
        stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        destination = NexusPaths.backups_dir / f"{stamp}-{target.name}"
        counter = 2
        while destination.exists():
            destination = NexusPaths.backups_dir / f"{stamp}-{counter}-{target.name}"
            counter += 1
        if target.is_dir():
            shutil.copytree(target, destination)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, destination)
        log_event("BACKUP", f"{reason}: {target} -> {destination}", metadata={"reason": reason})
        return str(destination)

    def _preview_payload(self, action: str, target: str, *, reason: str, extra: dict[str, Any] | None = None) -> str:
        payload = {
            "ok": True,
            "dry_run": True,
            "requires_confirmation": True,
            "action": action,
            "target": target,
            "reason": reason,
        }
        if extra:
            payload.update(extra)
        return self._json(payload)

    # --- Ferramentas ---

    def executar_comando(self, comando: str, timeout: int | None = None, dry_run: bool | None = None) -> str:
        assessment = command_assessment(comando)
        if not assessment.allowed:
            line = log_event("BLOQUEADO", comando, status="BLOCKED", metadata={"reason": assessment.reason})
            self._emit(line)
            return self._json(
                {
                    "ok": False,
                    "erro": assessment.reason,
                    "assessment": assessment.level,
                    "log": line,
                }
            )

        effective_dry_run = self._effective_dry_run(dry_run)
        if assessment.needs_confirmation and effective_dry_run:
            line = log_event("DRY_RUN", comando, status="WARN", metadata={"reason": assessment.reason})
            self._emit(line)
            return self._preview_payload(
                "executar_comando",
                comando,
                reason=assessment.reason,
                extra={"argv": assessment.argv},
            )

        snapshots: list[str] = []
        if assessment.modifies_state:
            for path in self._candidate_paths_from_argv(assessment.argv):
                if not path.exists():
                    continue
                try:
                    snapshot = self._create_backup_snapshot(path, reason=f"command:{assessment.executable}")
                except OSError as exc:
                    return self._json({"ok": False, "erro": f"Falha ao criar backup de {path}: {exc}"})
                if snapshot:
                    snapshots.append(snapshot)

        log_event(
            "EXECUTANDO",
            comando,
            metadata={"argv": assessment.argv, "timeout": timeout or DEFAULT_COMMAND_TIMEOUT_SECONDS},
        )
        self._emit(f"EXECUTANDO: {assessment.executable} {' '.join(assessment.argv[1:])}".strip())

        proc = subprocess.Popen(
            assessment.argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        started = time.monotonic()
        effective_timeout = max(1, int(timeout or DEFAULT_COMMAND_TIMEOUT_SECONDS))

        while proc.poll() is None:
            if self._cancelled():
                proc.terminate()
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    proc.kill()
                line = log_event("CANCELADO", comando, status="WARN")
                self._emit(line)
                raise CancelledExecution("Comando cancelado pelo usuario.")
            if time.monotonic() - started > effective_timeout:
                proc.terminate()
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    proc.kill()
                line = log_event("TIMEOUT", comando, status="ERROR")
                self._emit(line)
                return self._json({"ok": False, "erro": f"Timeout apos {effective_timeout}s", "backups": snapshots})
            time.sleep(COMMAND_POLL_INTERVAL_SECONDS)

        stdout, stderr = proc.communicate()
        payload = {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": (stdout or "").strip(),
            "stderr": (stderr or "").strip(),
            "backups": snapshots,
        }
        line = log_event(
            "RESULTADO",
            f"{comando} rc={proc.returncode}",
            status="OK" if proc.returncode == 0 else "ERROR",
            metadata={"returncode": proc.returncode},
        )
        self._emit(line)
        return self._json(payload)

    def gerenciar_arquivos(
        self,
        acao: str,
        path: str,
        content: str | None = None,
        target_path: str | None = None,
        dry_run: bool | None = None,
    ) -> str:
        effective_dry_run = self._effective_dry_run(dry_run)
        try:
            target = normalize_user_path(path)
        except ValueError as exc:
            return self._json({"ok": False, "erro": str(exc)})

        line = log_event("ARQUIVO", f"{acao} {target}")
        self._emit(line)

        try:
            if acao == "ler":
                if not target.exists():
                    return self._json({"ok": False, "erro": f"Arquivo nao encontrado: {target}"})
                return target.read_text(encoding="utf-8")

            if acao == "listar":
                if not target.exists():
                    return "[]"
                return self._json({"ok": True, "items": sorted([item.name for item in target.iterdir()], key=lambda x: x.lower())})

            safe_target = ensure_safe_write_path(path)

            if acao == "escrever":
                if effective_dry_run:
                    return self._preview_payload("escrever", str(safe_target), reason="Dry-run ativo para escrita.")
                backup = None
                if safe_target.exists():
                    backup = self._create_backup_snapshot(safe_target, reason="write")
                safe_target.parent.mkdir(parents=True, exist_ok=True)
                safe_target.write_text(content or "", encoding="utf-8")
                return self._json({"ok": True, "path": str(safe_target), "backup": backup})

            if acao == "mover":
                if not target_path:
                    raise ValueError("target_path e obrigatorio para mover")
                destination = ensure_safe_write_path(target_path)
                source = ensure_safe_write_path(path)
                if not source.exists():
                    return self._json({"ok": False, "erro": f"Arquivo nao encontrado: {source}"})
                if effective_dry_run:
                    return self._preview_payload(
                        "mover",
                        str(source),
                        reason="Dry-run ativo para mover.",
                        extra={"to": str(destination)},
                    )
                backup = self._create_backup_snapshot(source, reason="move")
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(destination))
                return self._json({"ok": True, "from": str(source), "to": str(destination), "backup": backup})

            if acao == "deletar":
                if not safe_target.exists():
                    return self._json({"ok": False, "erro": "Arquivo inexistente"})
                if effective_dry_run:
                    return self._preview_payload("deletar", str(safe_target), reason="Dry-run ativo para delete.")
                backup = self._create_backup_snapshot(safe_target, reason="delete")
                trash_target = NexusPaths.trash_dir / safe_target.name
                counter = 2
                while trash_target.exists():
                    trash_target = NexusPaths.trash_dir / f"{safe_target.stem}-{counter}{safe_target.suffix}"
                    counter += 1
                shutil.move(str(safe_target), str(trash_target))
                return self._json({"ok": True, "moved_to": str(trash_target), "backup": backup})
        except CancelledExecution:
            raise
        except PermissionError as exc:
            return self._json({"ok": False, "erro": f"Permissao negada: {exc}"})
        except OSError as exc:
            return self._json({"ok": False, "erro": f"Falha de IO: {exc}"})
        raise ValueError(f"Acao de arquivo desconhecida: {acao}")

    def controle_periferico(self, acao: str, x: int | None = None, y: int | None = None, texto: str | None = None) -> str:
        if self._cancelled():
            raise CancelledExecution("Execucao cancelada pelo usuario.")
        line = log_event("PERIFERICO", f"{acao} x={x} y={y}")
        self._emit(line)
        from pc_remote_agent import runtime

        if acao == "clicar":
            runtime.click(x=x, y=y)
            return self._json({"ok": True, "action": "clicar", "x": x, "y": y})
        if acao == "digitar":
            runtime.type_text(texto or "")
            return self._json({"ok": True, "action": "digitar", "text_len": len(texto or "")})
        if acao == "mover_mouse":
            if x is None or y is None:
                return self._json({"ok": False, "erro": "x e y sao obrigatorios"})
            runtime.move_to(x, y)
            return self._json({"ok": True, "action": "mover_mouse", "x": x, "y": y})
        if acao == "screenshot":
            image, _, _ = runtime.screen_image()
            shot_path = NexusPaths.base_dir / "last_screenshot.png"
            image.save(shot_path)
            return self._json({"ok": True, "path": str(shot_path)})
        if acao == "posicao_cursor":
            pos = runtime.mouse_position()
            return self._json({"x": int(pos[0]), "y": int(pos[1])})
        raise ValueError(f"Acao periferica desconhecida: {acao}")

    def verificar_pixel(self, x: int, y: int) -> str:
        from pc_remote_agent import runtime

        image, _, _ = runtime.screen_image()
        r, g, b = image.getpixel((x, y))
        self._emit(f"PIXEL: ({x},{y}) -> rgb({r},{g},{b})")
        return self._json({"x": x, "y": y, "rgb": [r, g, b]})

    def memoria_local(self, acao: str, texto: str | None = None, consulta: str | None = None) -> str:
        if acao == "salvar":
            if not texto:
                return self._json({"ok": False, "erro": "texto e obrigatorio"})
            item = remember(texto, source="assistant", kind="memory")
            self._emit(f"MEMORIA: salvo -> {item.text}")
            return self._json({"ok": True, "saved": item.text, "timestamp": item.timestamp})
        if acao == "buscar":
            limit = self.config.max_memory_items if self.config is not None else 8
            items = search_memory(consulta or "", limit=limit)
            payload = [{"timestamp": item.timestamp, "text": item.text, "kind": item.kind} for item in items]
            self._emit(f"MEMORIA: busca por '{consulta or ''}' retornou {len(payload)} itens")
            return self._json({"ok": True, "items": payload})
        if acao == "limpar":
            from .memory import clear_memory

            clear_memory()
            return self._json({"ok": True, "cleared": True})
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
            return self._json({"ok": False, "erro": "Configuracao MCP indisponivel no runtime."})

        line = log_event("MCP", f"{acao} servidor={servidor or '-'}")
        self._emit(line)

        if acao == "listar_servidores":
            servers = list_mcp_servers(self.config)
            return self._json({"ok": True, "servers": servers})
        if acao == "listar_recursos":
            if not servidor:
                return self._json({"ok": False, "erro": "servidor e obrigatorio"})
            resources = list_mcp_resources(self.config, servidor)
            return self._json({"ok": True, "resources": resources})
        if acao == "ler_recurso":
            if not servidor or not uri:
                return self._json({"ok": False, "erro": "servidor e uri sao obrigatorios"})
            payload = read_mcp_resource(self.config, servidor, uri)
            return self._json({"ok": True, **payload})
        if acao == "listar_ferramentas":
            if not servidor:
                return self._json({"ok": False, "erro": "servidor e obrigatorio"})
            tools = list_mcp_tools(self.config, servidor)
            return self._json({"ok": True, "tools": tools})
        if acao == "chamar_ferramenta":
            if not servidor or not ferramenta:
                return self._json({"ok": False, "erro": "servidor e ferramenta sao obrigatorios"})
            payload = call_mcp_tool(self.config, servidor, ferramenta, argumentos or {})
            return self._json({"ok": True, **payload})
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
            return self._json({"ok": True, "notebooks": payload})
        if acao == "criar":
            if not path:
                return self._json({"ok": False, "erro": "path e obrigatorio"})
            payload = create_notebook(path, title=title or "", kernel_name=(kernel_name or "").strip() or "python3")
            return self._json(payload)
        if acao == "ler":
            if not path:
                return self._json({"ok": False, "erro": "path e obrigatorio"})
            payload = read_notebook(path)
            return self._json(payload)
        if acao == "adicionar_codigo":
            if not path or content is None:
                return self._json({"ok": False, "erro": "path e content sao obrigatorios"})
            payload = append_cell(path, content, cell_type="code")
            return self._json(payload)
        if acao == "adicionar_markdown":
            if not path or content is None:
                return self._json({"ok": False, "erro": "path e content sao obrigatorios"})
            payload = append_cell(path, content, cell_type="markdown")
            return self._json(payload)
        if acao == "executar":
            if not path:
                return self._json({"ok": False, "erro": "path e obrigatorio"})
            payload = execute_notebook(
                path,
                kernel_name=(kernel_name or "").strip(),
                timeout=int(timeout or 300),
                cwd=(cwd or "").strip(),
            )
            return self._json(payload)
        raise ValueError(f"Acao de notebook desconhecida: {acao}")
