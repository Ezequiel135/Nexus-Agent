from __future__ import annotations

import json
import time
from typing import Any

from .actions import AcoesAgente
from .config import NexusConfig
from .memory import memory_summary
from .state import ActivityMonitor


SYSTEM_PROMPT = (
    "Voce e o Nexus Agent. Voce tem permissao Root. "
    "Suas respostas devem ser curtas e focadas em acoes. "
    "Quando precisar agir no computador, use as ferramentas disponiveis no seu toolkit. "
    "Voce nao pede permissao para subtarefas; voce executa e reporta. "
    "Quando o usuario der um objetivo complexo, decomponha em microtarefas, execute em loop e finalize apenas quando concluir. "
    "Se a tarefa envolver interface grafica, tela, janela, mouse, teclado, botao, cor, cursor, navegador ou clicar em algo no desktop, priorize o uso das tools visuais e de periferico. "
    "Se o usuario pedir para lembrar, salvar preferencia, guardar contexto ou manter uma informacao importante para depois, use a tool memoria_local."
)


class LiteLLMBridge:
    def __init__(self, config: NexusConfig, monitor: ActivityMonitor, actions: AcoesAgente) -> None:
        self.config = config
        self.monitor = monitor
        self.actions = actions
        self.config.export_runtime_env()
        self.monitor.set_model(config.model_name)

    def _completion(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> Any:
        try:
            from litellm import completion
        except ImportError as exc:
            raise RuntimeError("LiteLLM nao esta instalado no ambiente atual.") from exc

        started = time.perf_counter()
        response = completion(model=self.config.model_name, messages=messages, tools=tools)
        latency_ms = int((time.perf_counter() - started) * 1000)
        self.monitor.set_latency(latency_ms)
        return response

    @staticmethod
    def _message_content(message: Any) -> str:
        content = getattr(message, "content", "")
        if isinstance(content, list):
            return "\n".join(item.get("text", "") for item in content if isinstance(item, dict))
        return content or ""

    @staticmethod
    def _tool_calls(message: Any) -> list[Any]:
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls is None and isinstance(message, dict):
            tool_calls = message.get("tool_calls", [])
        return tool_calls or []

    @staticmethod
    def _message_to_dict(message: Any) -> dict[str, Any]:
        if isinstance(message, dict):
            return message
        payload = {"role": getattr(message, "role", "assistant"), "content": getattr(message, "content", "")}
        if getattr(message, "tool_calls", None):
            payload["tool_calls"] = message.tool_calls
        return payload

    def handshake(self) -> tuple[bool, str]:
        try:
            self.monitor.set_state("thinking")
            response = self._completion(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": "Responda apenas: NEXUS ONLINE"},
                ]
            )
            message = response.choices[0].message
            self.monitor.set_state("idle")
            return True, self._message_content(message) or "NEXUS ONLINE"
        except Exception:
            self.monitor.set_state("error", "ERRO DE COMUNICACAO")
            return False, "ERRO DE COMUNICACAO: VERIFIQUE SUA COTA OU CHAVE DE API."

    def chat(self, conversation: list[dict[str, Any]], max_rounds: int = 6) -> tuple[str, list[str]]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": self.actions.capabilities_summary()},
            {"role": "system", "content": memory_summary()},
            *conversation,
        ]
        tool_logs: list[str] = []
        for _ in range(max_rounds):
            self.monitor.set_state("thinking")
            response = self._completion(messages, tools=self.actions.tool_schemas())
            assistant_message = response.choices[0].message
            tool_calls = self._tool_calls(assistant_message)
            messages.append(self._message_to_dict(assistant_message))

            if not tool_calls:
                self.monitor.set_state("idle")
                return self._message_content(assistant_message), tool_logs

            for call in tool_calls:
                call_id = getattr(call, "id", None) or call.get("id")
                fn = getattr(call, "function", None) or call.get("function", {})
                fn_name = getattr(fn, "name", None) or fn.get("name")
                raw_args = getattr(fn, "arguments", None) or fn.get("arguments", "{}")
                arguments = json.loads(raw_args or "{}")
                self.monitor.set_state("acting")
                tool_result = self.actions.dispatch_tool(fn_name, arguments)
                tool_logs.append(f"{fn_name}({arguments})")
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": fn_name,
                        "content": tool_result,
                    }
                )

        self.monitor.set_state("idle")
        return "Tarefa interrompida apos muitas rodadas de ferramentas. Revise o objetivo ou refine a estrategia.", tool_logs
