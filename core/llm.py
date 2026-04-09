from __future__ import annotations

import json
import time
from typing import Any

from .actions import AcoesAgente
from .config import NexusConfig
from .memory import memory_summary
from .state import ActivityMonitor


SYSTEM_PROMPT = (
    "Voce e o Nexus Agent, um agente autonomo com acesso a ferramentas. "
    "Voce tem permissao root no sistema local. "
    "Suas respostas podem usar ferramentas para agir no mundo real. "
    "Nao peca permissao — execute e reporte. "
    "Tarefas complexas devem ser decompostas em passos. "
    "Se a tarefa envolver tela, mouse, teclado ou browser, use as ferramentas visuais. "
    "Se a tarefa pedir contexto externo vindo de um servidor MCP, use a ferramenta consultar_mcp."
)

PLANNER_PROMPT = (
    "Voce e um planner de agentes autonomos. "
    "Dado um objetivo do usuario, crie um plano detalhado de sub-tarefas. "
    "Responda em JSON no formato:\n"
    '{"plan": [{"step": 1, "task": "descricao da tarefa", "tool": "nome da ferramenta", "args": {...}}]}\n'
    "Use apenas as ferramentas disponiveis. Se nao precisar de ferramenta, use \"tool\": null.\n"
    "Se o objetivo for simples, pode retornar apenas uma tarefa."
)


def runtime_prompt(config: NexusConfig) -> str:
    parts: list[str] = []
    account = config.active_account
    agent = config.active_agent
    if account is not None:
        parts.append(f"Conta ativa: {account.name}. Provider: {account.provider_label}. Modelo: {account.model_name}.")
    if agent is not None:
        parts.append(f"Agente ativo: {agent.name}.")
        if agent.system_prompt:
            parts.append(f"Instrucoes extras do agente: {agent.system_prompt}")
    return " ".join(parts).strip()


def system_prompt(config: NexusConfig) -> str:
    extra = runtime_prompt(config)
    return f"{SYSTEM_PROMPT} {extra}".strip() if extra else SYSTEM_PROMPT


def planner_prompt(config: NexusConfig) -> str:
    extra = runtime_prompt(config)
    return f"{PLANNER_PROMPT} {extra}".strip() if extra else PLANNER_PROMPT


class PlannerExecutor:
    def __init__(self, config: NexusConfig, monitor: ActivityMonitor, actions: AcoesAgente) -> None:
        self.config = config
        self.monitor = monitor
        self.actions = actions
        self.config.export_runtime_env()
        self.monitor.set_model(config.model_name)

    def _completion(self, messages: list[dict[str, Any]]) -> Any:
        try:
            from litellm import completion
        except ImportError as exc:
            raise RuntimeError("LiteLLM nao esta instalado no ambiente atual.") from exc

        started = time.perf_counter()
        response = completion(model=self.config.model_name, messages=messages, **self.config.completion_kwargs())
        latency_ms = int((time.perf_counter() - started) * 1000)
        self.monitor.set_latency(latency_ms)
        return response

    @staticmethod
    def _message_content(message: Any) -> str:
        content = getattr(message, "content", "")
        if isinstance(content, list):
            return "\n".join(item.get("text", "") for item in content if isinstance(item, dict))
        return content or ""

    def _chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> Any:
        self.monitor.set_state("thinking")
        response = self._completion(messages)
        self.monitor.set_state("idle")
        return response

    def _create_plan(self, goal: str) -> list[dict[str, Any]]:
        prompt = f"{planner_prompt(self.config)}\n\nObjetivo: {goal}\n\nFerramentas disponiveis:\n{self.actions.capabilities_summary()}"
        messages = [
            {"role": "system", "content": system_prompt(self.config)},
            {"role": "user", "content": prompt},
        ]
        resp = self._chat(messages)
        text = self._message_content(resp.choices[0].message).strip()

        try:
            data = json.loads(text)
            if isinstance(data, dict) and "plan" in data:
                return data["plan"]
        except json.JSONDecodeError:
            pass

        return [{"step": 1, "task": goal, "tool": None, "args": {}}]

    def execute(self, goal: str) -> dict[str, Any]:
        plan = self._create_plan(goal)
        results: list[dict[str, Any]] = []

        for i, step in enumerate(plan, 1):
            task_desc = step.get("task", "")
            tool_name = step.get("tool")
            args = step.get("args") or {}
            reason = step.get("reason", "")

            self.monitor.set_state("acting")
            result_text = ""

            if tool_name and tool_name != "null":
                try:
                    result_text = self.actions.executar(tool_name, args)
                except Exception as e:
                    result_text = f"Erro em {tool_name}: {e}"
            else:
                result_text = f"Acao livre: {task_desc}"
                from .logging_utils import log_event
                log_event("ACAO_LIVRE", task_desc)

            results.append({
                "step": i,
                "task": task_desc,
                "tool": tool_name,
                "args": args,
                "result": result_text,
                "reason": reason,
            })

        self.monitor.set_state("idle")
        return {
            "goal": goal,
            "plan_steps": len(plan),
            "results": results,
            "summary": self._summarize(results),
        }

    @staticmethod
    def _summarize(results: list[dict[str, Any]]) -> str:
        lines = ["[PLANO CONCLUIDO]"]
        for r in results:
            status = "OK" if "Erro" not in str(r.get("result", "")) else "FAIL"
            lines.append(f"  Passo {r['step']}: {r['task'][:50]}... -> {r.get('tool','livre')} [{status}]")
        return "\n".join(lines)


class LiteLLMBridge:
    def __init__(self, config: NexusConfig, monitor: ActivityMonitor, actions: AcoesAgente) -> None:
        self.config = config
        self.monitor = monitor
        self.actions = actions
        self.planner = PlannerExecutor(config, monitor, actions)
        self.config.export_runtime_env()
        self.monitor.set_model(config.model_name)

    def _completion(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> Any:
        try:
            from litellm import completion
        except ImportError as exc:
            raise RuntimeError("LiteLLM nao esta instalado no ambiente atual.") from exc

        started = time.perf_counter()
        response = completion(
            model=self.config.model_name,
            messages=messages,
            tools=tools,
            **self.config.completion_kwargs(),
        )
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
        if self.config.active_account is None:
            self.monitor.set_state("error", "Nenhuma conta ativa")
            return False, "Nenhuma conta ativa. Rode nexus login ou nexus setup."
        try:
            self.monitor.set_state("thinking")
            response = self._completion(
                [
                    {"role": "system", "content": system_prompt(self.config)},
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
        if self.config.active_account is None:
            raise RuntimeError("Nenhuma conta ativa. Rode nexus login ou nexus setup.")
        messages = [
            {"role": "system", "content": system_prompt(self.config)},
            {"role": "system", "content": self.actions.capabilities_summary()},
            {"role": "system", "content": memory_summary()},
            *conversation,
        ]
        tool_logs: list[str] = []
        last_user_msg = conversation[-1].get("content", "") if conversation else ""

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

    def chat_with_plan(self, goal: str) -> dict[str, Any]:
        self.monitor.set_state("planning")
        execution = self.planner.execute(goal)
        self.monitor.set_state("idle")
        return execution
