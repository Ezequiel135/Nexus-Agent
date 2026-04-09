from __future__ import annotations

import json
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

import requests

from .actions import AcoesAgente
from .config import NexusConfig, NexusRemoteIntegration, config_exists, find_remote_integration, load_config
from .llm import LiteLLMBridge
from .logging_utils import log_event
from .state import ActivityMonitor

DEFAULT_WHATSAPP_GRAPH_VERSION = "v23.0"


@dataclass(slots=True)
class RemoteTask:
    integration: NexusRemoteIntegration
    sender_id: str
    text: str
    reply_func: Callable[[str], None]


class RemoteTaskProcessor:
    def __init__(self, config: NexusConfig) -> None:
        if config.active_account is None:
            raise RuntimeError("Nenhuma conta ativa. Rode nexus login antes de iniciar a automacao remota.")
        self.config = config
        self.monitor = ActivityMonitor()
        self.monitor.start()
        self.monitor.set_autonomous_mode(True)
        self.bridge = LiteLLMBridge(config, self.monitor, AcoesAgente(config))
        self._stop_event = threading.Event()
        self._queue: queue.Queue[RemoteTask | None] = queue.Queue()
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop_event.set()
        self._queue.put(None)
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self.monitor.stop()

    def submit(
        self,
        integration: NexusRemoteIntegration,
        *,
        sender_id: str,
        text: str,
        reply_func: Callable[[str], None],
    ) -> None:
        self._queue.put(RemoteTask(integration=integration, sender_id=sender_id, text=text, reply_func=reply_func))

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            task = self._queue.get()
            if task is None:
                break

            response_text = ""
            try:
                live_config = load_config() if config_exists() else self.config
                live_integration = find_remote_integration(live_config, task.integration.id)
                if not live_config.remote_armed or live_integration is None or not live_integration.enabled:
                    response_text = "Modo remoto desarmado ou integracao removida. Nenhuma acao foi executada."
                else:
                    self.config = live_config
                    self.bridge.config = live_config
                    self.bridge.actions.config = live_config
                    self.bridge.planner.config = live_config
                    self.bridge.planner.actions.config = live_config
                    self.monitor.set_model(live_config.model_name)
                    log_event(
                        "REMOTE",
                        f"{task.integration.channel}:{task.integration.name} sender={task.sender_id} task={task.text[:160]}",
                    )
                    response_text, _tool_logs = self.bridge.chat([{"role": "user", "content": task.text}])
                    response_text = response_text.strip() or "Tarefa executada no PC."
            except Exception as exc:
                self.monitor.set_state("error", str(exc))
                response_text = f"Erro ao executar no PC: {exc}"
                log_event("REMOTE", response_text, status="ERROR")

            try:
                task.reply_func(_clip_text(response_text, _reply_limit(task.integration.channel)))
            except Exception as exc:
                log_event(
                    "REMOTE",
                    f"Falha ao responder via {task.integration.channel}:{task.integration.name}: {exc}",
                    status="ERROR",
                )
            finally:
                self._queue.task_done()


def list_remote_integrations(config: NexusConfig) -> list[dict[str, Any]]:
    items = []
    for integration in config.remote_integrations:
        items.append(
            {
                "id": integration.id,
                "name": integration.name,
                "channel": integration.channel,
                "enabled": integration.enabled,
                "command_prefix": integration.command_prefix,
                "allowed_senders": list(integration.allowed_senders),
            }
        )
    return items


def run_remote_integration(
    config: NexusConfig,
    integration_query: str,
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
) -> None:
    integration = find_remote_integration(config, integration_query)
    if integration is None:
        raise RuntimeError(f"Integracao remota nao encontrada: {integration_query}")
    if not integration.enabled:
        raise RuntimeError(f"Integracao remota desabilitada: {integration.name}")
    if not config.remote_armed:
        raise RuntimeError("Modo remoto desarmado. Rode nexus remote arm antes de iniciar.")

    processor = RemoteTaskProcessor(config)
    try:
        if integration.channel == "telegram":
            TelegramBotRunner(integration, processor).run()
            return
        if integration.channel == "whatsapp":
            WhatsAppWebhookRunner(integration, processor, host=host, port=port).run()
            return
        raise RuntimeError(f"Canal remoto nao suportado: {integration.channel}")
    finally:
        processor.close()


class TelegramBotRunner:
    def __init__(self, integration: NexusRemoteIntegration, processor: RemoteTaskProcessor) -> None:
        self.integration = integration
        self.processor = processor
        self.bot_token = integration.settings.get("bot_token", "").strip()
        self.poll_timeout = max(10, int(integration.settings.get("poll_timeout", "30") or "30"))
        if not self.bot_token:
            raise RuntimeError("Integracao Telegram sem bot_token configurado.")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def run(self) -> None:
        offset = self._bootstrap_offset()
        log_event("REMOTE", f"Telegram {self.integration.name} em polling continuo")
        print(f"Telegram ativo: {self.integration.name}. Prefixo: {self.integration.command_prefix}. Ctrl+C para sair.")
        while True:
            try:
                payload = self._api(
                    "getUpdates",
                    params={
                        "timeout": self.poll_timeout,
                        "offset": offset,
                    },
                    method="GET",
                )
                for update in payload.get("result", []):
                    offset = int(update.get("update_id", 0)) + 1
                    self._handle_update(update)
            except KeyboardInterrupt:
                print("\nTelegram encerrado.")
                return
            except Exception as exc:
                log_event("REMOTE", f"Telegram polling falhou: {exc}", status="ERROR")
                time.sleep(2.0)

    def _bootstrap_offset(self) -> int:
        payload = self._api("getUpdates", params={"timeout": 1}, method="GET")
        updates = payload.get("result", [])
        if not updates:
            return 0
        return int(updates[-1].get("update_id", 0)) + 1

    def _handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message") or update.get("edited_message") or {}
        text = (message.get("text") or "").strip()
        chat_id = str(message.get("chat", {}).get("id", "")).strip()
        user_id = str(message.get("from", {}).get("id", "")).strip()
        if not text or not _is_allowed_sender(self.integration, chat_id, user_id):
            return

        task = _extract_task_text(text, self.integration.command_prefix)
        if not task:
            return

        if chat_id:
            self.processor.submit(
                self.integration,
                sender_id=chat_id or user_id,
                text=task,
                reply_func=lambda body, target=chat_id: self.send_text(target, body),
            )
            try:
                self.send_text(chat_id, "Comando recebido. Executando no PC...")
            except Exception as exc:
                log_event("REMOTE", f"Telegram sem ACK para {chat_id}: {exc}", status="ERROR")

    def send_text(self, chat_id: str, text: str) -> None:
        self._api(
            "sendMessage",
            method="POST",
            payload={
                "chat_id": chat_id,
                "text": _clip_text(text, _reply_limit("telegram")),
                "disable_web_page_preview": True,
            },
        )

    def _api(
        self,
        method_name: str,
        *,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        method: str = "POST",
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{method_name}"
        if method == "GET":
            response = requests.get(url, params=params, timeout=self.poll_timeout + 5)
        else:
            response = requests.post(url, json=payload or {}, timeout=20)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok", False):
            raise RuntimeError(data.get("description", "Falha na API do Telegram"))
        return data


class WhatsAppWebhookRunner:
    def __init__(
        self,
        integration: NexusRemoteIntegration,
        processor: RemoteTaskProcessor,
        *,
        host: str,
        port: int,
    ) -> None:
        self.integration = integration
        self.processor = processor
        self.host = host
        self.port = port
        self.access_token = integration.settings.get("access_token", "").strip()
        self.phone_number_id = integration.settings.get("phone_number_id", "").strip()
        self.verify_token = integration.settings.get("verify_token", "").strip()
        self.graph_version = integration.settings.get("graph_version", DEFAULT_WHATSAPP_GRAPH_VERSION).strip()
        if not self.access_token or not self.phone_number_id or not self.verify_token:
            raise RuntimeError("Integracao WhatsApp incompleta. Configure access_token, phone_number_id e verify_token.")
        self._seen_lock = threading.Lock()
        self._seen_order: deque[str] = deque()
        self._seen_ids: set[str] = set()

    def run(self) -> None:
        runner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                runner._handle_get(self)

            def do_POST(self) -> None:
                runner._handle_post(self)

            def log_message(self, fmt: str, *args: Any) -> None:
                return

        server = ThreadingHTTPServer((self.host, self.port), Handler)
        log_event("REMOTE", f"WhatsApp webhook {self.integration.name} ouvindo em http://{self.host}:{self.port}/webhook")
        print(
            f"WhatsApp ativo: {self.integration.name} em http://{self.host}:{self.port}/webhook. "
            "Exponha esse endpoint publicamente para a Cloud API. Ctrl+C para sair."
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nWhatsApp encerrado.")
        finally:
            server.server_close()

    def send_text(self, target: str, text: str) -> None:
        url = f"https://graph.facebook.com/{self.graph_version}/{self.phone_number_id}/messages"
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "to": target,
                "type": "text",
                "text": {
                    "body": _clip_text(text, _reply_limit("whatsapp")),
                    "preview_url": False,
                },
            },
            timeout=20,
        )
        response.raise_for_status()

    def _handle_get(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(handler.path)
        if parsed.path not in {"/", "/webhook"}:
            handler.send_response(404)
            handler.end_headers()
            return

        query = parse_qs(parsed.query)
        mode = query.get("hub.mode", [""])[0]
        token = query.get("hub.verify_token", [""])[0]
        challenge = query.get("hub.challenge", [""])[0]
        if mode == "subscribe" and token == self.verify_token:
            handler.send_response(200)
            handler.send_header("Content-Type", "text/plain; charset=utf-8")
            handler.end_headers()
            handler.wfile.write(challenge.encode("utf-8"))
            return

        handler.send_response(403)
        handler.end_headers()

    def _handle_post(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(handler.path)
        if parsed.path not in {"/", "/webhook"}:
            handler.send_response(404)
            handler.end_headers()
            return

        content_length = int(handler.headers.get("Content-Length", "0") or "0")
        raw_body = handler.rfile.read(content_length) if content_length else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            handler.send_response(400)
            handler.end_headers()
            return

        try:
            self._consume_payload(payload)
        except Exception as exc:
            log_event("REMOTE", f"Falha webhook WhatsApp: {exc}", status="ERROR")

        handler.send_response(200)
        handler.send_header("Content-Type", "text/plain; charset=utf-8")
        handler.end_headers()
        handler.wfile.write(b"EVENT_RECEIVED")

    def _consume_payload(self, payload: dict[str, Any]) -> None:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for message in value.get("messages", []):
                    if message.get("type") != "text":
                        continue
                    message_id = str(message.get("id", "")).strip()
                    if message_id and not self._remember_message(message_id):
                        continue
                    sender = str(message.get("from", "")).strip()
                    if not _is_allowed_sender(self.integration, sender):
                        continue
                    text = (message.get("text", {}).get("body") or "").strip()
                    task = _extract_task_text(text, self.integration.command_prefix)
                    if not task:
                        continue
                    self.processor.submit(
                        self.integration,
                        sender_id=sender,
                        text=task,
                        reply_func=lambda body, target=sender: self.send_text(target, body),
                    )

    def _remember_message(self, message_id: str) -> bool:
        with self._seen_lock:
            if message_id in self._seen_ids:
                return False
            self._seen_ids.add(message_id)
            self._seen_order.append(message_id)
            while len(self._seen_order) > 1024:
                expired = self._seen_order.popleft()
                self._seen_ids.discard(expired)
            return True


def _is_allowed_sender(integration: NexusRemoteIntegration, *sender_ids: str) -> bool:
    allowed = {item.strip() for item in integration.allowed_senders if item.strip()}
    if not allowed:
        return False
    for sender_id in sender_ids:
        if sender_id and sender_id.strip() in allowed:
            return True
    return False


def _extract_task_text(text: str, prefix: str) -> str:
    clean = (text or "").strip()
    normalized_prefix = (prefix or "").strip()
    if not clean:
        return ""
    if not normalized_prefix:
        return clean
    if clean.lower().startswith(normalized_prefix.lower()):
        return clean[len(normalized_prefix) :].strip()
    return ""


def _clip_text(text: str, limit: int) -> str:
    clean = (text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 3)].rstrip() + "..."


def _reply_limit(channel: str) -> int:
    return 3500 if channel == "telegram" else 1400
