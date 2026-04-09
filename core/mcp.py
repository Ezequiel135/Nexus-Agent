from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from dataclasses import asdict
from typing import Any

from .config import NexusConfig, NexusMcpServer, find_mcp_server
from .logging_utils import log_event

MCP_PROTOCOL_VERSION = "2025-06-18"
MCP_CLIENT_VERSION = "2.2.0"


class McpError(RuntimeError):
    pass


class McpClient:
    def __init__(self, server: NexusMcpServer, timeout: float = 10.0) -> None:
        self.server = server
        self.timeout = timeout
        self._proc: subprocess.Popen[bytes] | None = None
        self._queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._request_id = 0

    def __enter__(self) -> "McpClient":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def start(self) -> None:
        if self._proc is not None:
            return
        self._proc = subprocess.Popen(
            self.server.command,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert self._proc.stdout is not None
        assert self._proc.stderr is not None
        threading.Thread(target=self._pump_stdout, daemon=True).start()
        threading.Thread(target=self._pump_stderr, daemon=True).start()
        result = self._request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "nexus-agent", "version": MCP_CLIENT_VERSION},
            },
        )
        negotiated = result.get("protocolVersion", "")
        log_event("MCP", f"{self.server.name} inicializado (protocol={negotiated or MCP_PROTOCOL_VERSION})")
        self._notify("notifications/initialized")

    def close(self) -> None:
        if self._proc is None:
            return
        try:
            self._proc.terminate()
            self._proc.wait(timeout=1)
        except Exception:
            self._proc.kill()
        finally:
            self._proc = None

    def list_resources(self) -> list[dict[str, Any]]:
        result = self._request("resources/list", {})
        return result.get("resources", [])

    def read_resource(self, uri: str) -> dict[str, Any]:
        result = self._request("resources/read", {"uri": uri})
        return {"contents": result.get("contents", [])}

    def list_tools(self) -> list[dict[str, Any]]:
        result = self._request("tools/list", {})
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self._request("tools/call", {"name": name, "arguments": arguments or {}})
        return result

    def _pump_stdout(self) -> None:
        assert self._proc is not None
        assert self._proc.stdout is not None
        while True:
            raw = self._proc.stdout.readline()
            if not raw:
                self._queue.put(("eof", None))
                return
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                self._queue.put(("stdout", line))
                continue
            self._queue.put(("message", payload))

    def _pump_stderr(self) -> None:
        assert self._proc is not None
        assert self._proc.stderr is not None
        while True:
            raw = self._proc.stderr.readline()
            if not raw:
                return
            line = raw.decode("utf-8", errors="replace").strip()
            if line:
                self._queue.put(("stderr", line))

    def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._request_id += 1
        request_id = self._request_id
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        deadline = time.monotonic() + self.timeout
        logs: list[str] = []

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                detail = f"Timeout aguardando resposta do servidor MCP {self.server.name}"
                if logs:
                    detail += f" | logs: {' | '.join(logs[-3:])}"
                raise McpError(detail)

            try:
                kind, payload = self._queue.get(timeout=remaining)
            except queue.Empty as exc:
                raise McpError(f"Timeout aguardando resposta do servidor MCP {self.server.name}") from exc

            if kind == "message":
                if isinstance(payload, dict) and payload.get("id") == request_id:
                    if "error" in payload:
                        message = payload["error"].get("message", "Erro MCP")
                        raise McpError(f"{self.server.name}: {message}")
                    return payload.get("result", {})
                continue

            if kind == "stderr":
                logs.append(payload)
                continue
            if kind == "eof":
                detail = f"Servidor MCP {self.server.name} encerrou a conexao."
                if logs:
                    detail += f" Logs: {' | '.join(logs[-3:])}"
                raise McpError(detail)

    def _send(self, payload: dict[str, Any]) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise McpError("Servidor MCP nao iniciado.")
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n"
        self._proc.stdin.write(body)
        self._proc.stdin.flush()


def _require_server(config: NexusConfig, server_query: str) -> NexusMcpServer:
    server = find_mcp_server(config, server_query)
    if server is None:
        raise McpError(f"Servidor MCP nao encontrado: {server_query}")
    if not server.enabled:
        raise McpError(f"Servidor MCP desabilitado: {server.name}")
    return server


def list_mcp_servers(config: NexusConfig) -> list[dict[str, Any]]:
    return [asdict(server) for server in config.mcp_servers]


def list_mcp_resources(config: NexusConfig, server_query: str) -> list[dict[str, Any]]:
    server = _require_server(config, server_query)
    with McpClient(server) as client:
        return client.list_resources()


def read_mcp_resource(config: NexusConfig, server_query: str, uri: str) -> dict[str, Any]:
    server = _require_server(config, server_query)
    with McpClient(server) as client:
        return client.read_resource(uri)


def list_mcp_tools(config: NexusConfig, server_query: str) -> list[dict[str, Any]]:
    server = _require_server(config, server_query)
    with McpClient(server) as client:
        return client.list_tools()


def call_mcp_tool(config: NexusConfig, server_query: str, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    server = _require_server(config, server_query)
    with McpClient(server) as client:
        return client.call_tool(tool_name, arguments)
