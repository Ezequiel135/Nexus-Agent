from __future__ import annotations

import hashlib
import json
import threading
import time
from types import SimpleNamespace
from typing import Any

from .actions import AcoesAgente, CancelledExecution
from .config import NexusConfig, NexusPaths
from .logging_utils import log_event
from .memory import memory_summary
from .safeguards import command_assessment
from .state import ActivityMonitor


SYSTEM_PROMPT = (
    "Voce e o Nexus Agent, um agente operacional local. "
    "Planeje antes de agir, explique brevemente o que esta fazendo e use ferramentas apenas quando necessario. "
    "Nunca assuma permissao irrestrita; respeite dry-run, confirmacoes, limites do runtime e modo offline. "
    "Se uma acao for arriscada, mostre o plano e sinalize a necessidade de aprovacao. "
    "Se o runtime estiver sem LLM remoto, ofereca modo offline local, comandos slash e instrucoes de configuracao. "
    "Se a tarefa envolver tela, mouse, teclado ou browser, use as ferramentas visuais. "
    "Se a tarefa pedir contexto externo vindo de um servidor MCP, use a ferramenta consultar_mcp. "
    "Se a tarefa envolver notebooks Jupyter, use a ferramenta gerenciar_notebooks."
)

PLANNER_PROMPT = (
    "Voce e um planner de agentes autonomos. "
    "Dado um objetivo do usuario, gere um plano curto, seguro e executavel. "
    "Responda em JSON no formato:\n"
    '{"plan": [{"step": 1, "task": "descricao", "tool": "nome_da_ferramenta_ou_null", "args": {}, "reason": "por que esse passo existe"}]}\n'
    "Use apenas as ferramentas disponiveis. "
    "Nao invente ferramentas. "
    "Evite passos redundantes e limite o plano ao minimo necessario."
)

LLM_MAX_RETRY_ATTEMPTS = 10
LLM_RETRY_DELAY_STEP_SECONDS = 10
LLM_RETRY_ERROR_MARKERS = (
    "429",
    "quota",
    "insufficient_quota",
    "rate limit",
    "rate_limit",
    "too many requests",
    "resource exhausted",
    "resource_exhausted",
    "retry after",
    "requests per min",
    "tokens per min",
)

_CACHE_LOCK = threading.Lock()


def runtime_prompt(config: NexusConfig) -> str:
    parts: list[str] = [f"Runtime: {config.runtime_mode}."]
    account = config.active_account
    agent = config.active_agent
    if account is not None:
        parts.append(f"Conta ativa: {account.name}. Provider: {account.provider_label}. Modelo: {account.model_name}.")
    else:
        parts.append("Nenhuma conta ativa. Comandos locais e slash devem continuar disponiveis.")
    if agent is not None:
        parts.append(f"Agente ativo: {agent.name}.")
        if agent.system_prompt:
            parts.append(f"Instrucoes extras do agente: {agent.system_prompt}")
    if config.dry_run:
        parts.append("Dry-run padrao ativo para acoes modificadoras.")
    if config.plan_before_execute:
        parts.append("Planejamento antes de executar esta habilitado.")
    return " ".join(parts).strip()


def system_prompt(config: NexusConfig) -> str:
    extra = runtime_prompt(config)
    return f"{SYSTEM_PROMPT} {extra}".strip() if extra else SYSTEM_PROMPT


def planner_prompt(config: NexusConfig) -> str:
    extra = runtime_prompt(config)
    return f"{PLANNER_PROMPT} {extra}".strip() if extra else PLANNER_PROMPT


def retry_delay_seconds(attempt_number: int) -> int:
    return max(1, attempt_number) * LLM_RETRY_DELAY_STEP_SECONDS


def is_retryable_llm_error(exc: Exception) -> bool:
    details = [type(exc).__name__, str(exc)]
    status_code = getattr(exc, "status_code", None)
    if status_code is not None:
        details.append(str(status_code))
    response = getattr(exc, "response", None)
    if response is not None:
        response_status = getattr(response, "status_code", None)
        if response_status is not None:
            details.append(str(response_status))
    haystack = " ".join(part for part in details if part).lower()
    return any(marker in haystack for marker in LLM_RETRY_ERROR_MARKERS)


def _cache_key(config: NexusConfig, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None) -> str:
    payload = {
        "model": config.model_name,
        "runtime_mode": getattr(config, "runtime_mode", "hybrid"),
        "max_output_tokens": getattr(config, "max_output_tokens", 1200),
        "messages": messages,
        "tools": tools or [],
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_cache() -> dict[str, Any]:
    NexusPaths.ensure()
    if not NexusPaths.llm_cache_path.exists():
        return {}
    try:
        return json.loads(NexusPaths.llm_cache_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(payload: dict[str, Any]) -> None:
    NexusPaths.ensure()
    NexusPaths.llm_cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _serialize_tool_calls(tool_calls: list[Any]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for call in tool_calls or []:
        if isinstance(call, dict):
            payload.append(call)
            continue
        fn = getattr(call, "function", None)
        payload.append(
            {
                "id": getattr(call, "id", ""),
                "type": "function",
                "function": {
                    "name": getattr(fn, "name", ""),
                    "arguments": getattr(fn, "arguments", "{}"),
                },
            }
        )
    return payload


def _serialize_response(response: Any) -> dict[str, Any]:
    message = response.choices[0].message
    return {
        "message": {
            "role": getattr(message, "role", "assistant"),
            "content": getattr(message, "content", ""),
            "tool_calls": _serialize_tool_calls(getattr(message, "tool_calls", []) or []),
        }
    }


def _deserialize_response(payload: dict[str, Any]) -> Any:
    message_payload = payload.get("message", {})
    message = SimpleNamespace(
        role=message_payload.get("role", "assistant"),
        content=message_payload.get("content", ""),
        tool_calls=message_payload.get("tool_calls", []),
    )
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _extract_json(text: str) -> str:
    stripped = (text or "").strip()
    if stripped.startswith("```"):
        lines = [line for line in stripped.splitlines() if not line.startswith("```")]
        return "\n".join(lines).strip()
    return stripped


def _trim_conversation(config: NexusConfig, conversation: list[dict[str, Any]]) -> list[dict[str, Any]]:
    limit = max(1, config.max_history_messages)
    return conversation[-limit:]


def completion_with_retries(
    config: NexusConfig,
    monitor: ActivityMonitor,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> Any:
    if not getattr(config, "llm_allowed", True):
        raise RuntimeError("LLM indisponivel no runtime atual. Use modo offline/local ou configure uma conta ativa.")

    request_kwargs: dict[str, Any] = {
        "model": config.model_name,
        "messages": messages,
        "max_tokens": getattr(config, "max_output_tokens", 1200),
        **config.completion_kwargs(),
    }
    if tools is not None:
        request_kwargs["tools"] = tools

    cache_key = _cache_key(config, messages, tools)
    if getattr(config, "llm_cache_enabled", False):
        with _CACHE_LOCK:
            cache = _load_cache()
            if cache_key in cache:
                monitor.set_latency(0)
                log_event("LLM_CACHE_HIT", f"model={config.model_name}")
                return _deserialize_response(cache[cache_key])

    try:
        from litellm import completion
    except ImportError as exc:
        raise RuntimeError("LiteLLM nao esta instalado no ambiente atual.") from exc

    last_exc: Exception | None = None
    for attempt in range(1, LLM_MAX_RETRY_ATTEMPTS + 1):
        started = time.perf_counter()
        try:
            response = completion(**request_kwargs)
            latency_ms = int((time.perf_counter() - started) * 1000)
            monitor.set_latency(latency_ms)
            if getattr(config, "llm_cache_enabled", False):
                with _CACHE_LOCK:
                    cache = _load_cache()
                    cache[cache_key] = _serialize_response(response)
                    if len(cache) > 200:
                        oldest_keys = list(cache.keys())[:-200]
                        for key in oldest_keys:
                            cache.pop(key, None)
                    _save_cache(cache)
            return response
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            monitor.set_latency(latency_ms)
            last_exc = exc
            if not is_retryable_llm_error(exc):
                raise
            if attempt >= LLM_MAX_RETRY_ATTEMPTS:
                break
            wait_seconds = retry_delay_seconds(attempt)
            detail = (
                f"Erro de cota/rate limit na API ({attempt}/{LLM_MAX_RETRY_ATTEMPTS}). "
                f"Nova tentativa em {wait_seconds}s."
            )
            monitor.set_state("thinking", detail)
            log_event("LLM_RETRY", detail, status="WARN")
            time.sleep(wait_seconds)

    raise RuntimeError(
        f"Falha apos {LLM_MAX_RETRY_ATTEMPTS} tentativas por erro de cota/rate limit: {last_exc}"
    ) from last_exc


class PlannerExecutor:
    def __init__(
        self,
        config: NexusConfig,
        monitor: ActivityMonitor,
        actions: AcoesAgente,
        *,
        export_env: bool = True,
    ) -> None:
        self.config = config
        self.monitor = monitor
        self.actions = actions
        if export_env:
            self.config.export_runtime_env()
        self.monitor.set_model(config.model_name or "offline")

    def _completion(self, messages: list[dict[str, Any]]) -> Any:
        return completion_with_retries(self.config, self.monitor, messages)

    @staticmethod
    def _message_content(message: Any) -> str:
        content = getattr(message, "content", "")
        if isinstance(content, list):
            return "\n".join(item.get("text", "") for item in content if isinstance(item, dict))
        return content or ""

    def _annotate_step(self, step: dict[str, Any]) -> dict[str, Any]:
        annotated = dict(step)
        tool_name = annotated.get("tool")
        args = annotated.get("args") or {}
        risk_level = "green"
        risk_reason = ""
        needs_confirmation = False

        if tool_name == "executar_comando":
            assessment = command_assessment(str(args.get("comando", "")))
            risk_level = assessment.level
            risk_reason = assessment.reason
            needs_confirmation = assessment.needs_confirmation
        elif tool_name == "gerenciar_arquivos":
            if args.get("acao") in {"escrever", "mover", "deletar"}:
                risk_level = "yellow"
                risk_reason = "Operacao de arquivo com modificacao local."
                needs_confirmation = True

        annotated["risk_level"] = risk_level
        annotated["risk_reason"] = risk_reason
        annotated["needs_confirmation"] = needs_confirmation
        return annotated

    def create_plan(self, goal: str) -> list[dict[str, Any]]:
        if not self.config.llm_allowed:
            return [{"step": 1, "task": goal, "tool": None, "args": {}, "reason": "Runtime offline sem LLM."}]

        prompt = (
            f"{planner_prompt(self.config)}\n\n"
            f"Limite o plano a no maximo {self.config.max_plan_steps} passos.\n"
            f"Objetivo: {goal}\n\n"
            f"Ferramentas disponiveis:\n{self.actions.capabilities_summary()}"
        )
        messages = [
            {"role": "system", "content": system_prompt(self.config)},
            {"role": "user", "content": prompt},
        ]
        self.monitor.set_state("planning", detail="Gerando plano de execucao...")
        resp = self._completion(messages)
        text = _extract_json(self._message_content(resp.choices[0].message))

        try:
            data = json.loads(text)
            plan = data.get("plan", []) if isinstance(data, dict) else []
            if isinstance(plan, list) and plan:
                normalized: list[dict[str, Any]] = []
                for index, item in enumerate(plan[: self.config.max_plan_steps], start=1):
                    if not isinstance(item, dict):
                        continue
                    normalized.append(
                        {
                            "step": index,
                            "task": str(item.get("task", goal)).strip() or goal,
                            "tool": item.get("tool"),
                            "args": item.get("args") or {},
                            "reason": str(item.get("reason", "")).strip(),
                        }
                    )
                if normalized:
                    return normalized
        except json.JSONDecodeError:
            pass

        return [{"step": 1, "task": goal, "tool": None, "args": {}, "reason": "Fallback de plano simples."}]

    def preview(self, goal: str) -> dict[str, Any]:
        plan = [self._annotate_step(step) for step in self.create_plan(goal)]
        requires_confirmation = bool(self.config.plan_before_execute or any(step.get("needs_confirmation") for step in plan))
        summary_lines = ["[PLANO PREVIEW]"]
        for step in plan:
            risk = step.get("risk_level", "green").upper()
            summary_lines.append(f"  Passo {step['step']}: {step['task']} [{risk}]")
        self.monitor.set_state("idle")
        return {
            "goal": goal,
            "plan_steps": len(plan),
            "steps": plan,
            "summary": "\n".join(summary_lines),
            "requires_confirmation": requires_confirmation,
        }

    def execute_plan(self, goal: str, plan: list[dict[str, Any]]) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        total = len(plan)
        self.monitor.set_goal(goal)
        self.monitor.set_cancellable(True)
        for index, step in enumerate(plan, start=1):
            if self.actions._cancelled():
                raise CancelledExecution("Plano cancelado pelo usuario.")
            task_desc = step.get("task", "")
            tool_name = step.get("tool")
            args = step.get("args") or {}
            reason = step.get("reason", "")

            self.monitor.set_state("acting", detail=f"Passo {index}/{total}: {task_desc}")
            self.monitor.set_step_progress(index, total, f"Executando: {task_desc}")
            result_text = ""

            if tool_name and tool_name != "null":
                try:
                    result_text = self.actions.dispatch_tool(tool_name, args)
                except Exception as exc:
                    result_text = f"Erro em {tool_name}: {exc}"
            else:
                result_text = f"Acao livre: {task_desc}"
                log_event("ACAO_LIVRE", task_desc)

            results.append(
                {
                    "step": index,
                    "task": task_desc,
                    "tool": tool_name,
                    "args": args,
                    "result": result_text,
                    "reason": reason,
                    "risk_level": step.get("risk_level", "green"),
                    "needs_confirmation": bool(step.get("needs_confirmation", False)),
                }
            )

        self.monitor.set_state("idle")
        self.monitor.set_cancellable(False)
        self.monitor.set_step_progress(0, total)
        return {
            "goal": goal,
            "plan_steps": total,
            "results": results,
            "summary": self._summarize(results),
        }

    @staticmethod
    def _summarize(results: list[dict[str, Any]]) -> str:
        lines = ["[PLANO CONCLUIDO]"]
        for result in results:
            status = "OK" if "Erro" not in str(result.get("result", "")) else "FAIL"
            lines.append(f"  Passo {result['step']}: {result['task'][:60]} -> {result.get('tool') or 'livre'} [{status}]")
        return "\n".join(lines)


class LiteLLMBridge:
    def __init__(
        self,
        config: NexusConfig,
        monitor: ActivityMonitor,
        actions: AcoesAgente,
        export_env: bool = True,
    ) -> None:
        self.config = config
        self.monitor = monitor
        self.actions = actions
        self.planner = PlannerExecutor(config, monitor, actions, export_env=False)
        if export_env and self.config.active_account is not None:
            self.config.export_runtime_env()
        self.monitor.set_model(config.model_name or "offline")

    def _completion(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> Any:
        return completion_with_retries(self.config, self.monitor, messages, tools=tools)

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
            self.monitor.set_state("idle", detail="Modo local sem conta ativa.")
            return True, "Modo offline/local pronto. Comandos slash e ferramentas locais seguem disponiveis."
        if not self.config.llm_allowed:
            label = "modelo local" if self.config.local_llm_enabled else "comandos locais"
            self.monitor.set_state("idle", detail=f"Runtime sem LLM remoto; usando {label}.")
            return True, f"Runtime pronto em modo {self.config.runtime_mode}. Use {label}."
        if not self.config.startup_probe:
            self.monitor.set_state("idle", detail="Handshake remoto adiado para acelerar o boot.")
            return True, f"NEXUS pronto ({self.config.runtime_mode}) sem probe inicial para acelerar a abertura."
        try:
            self.monitor.set_state("thinking", detail="Validando conexao do modelo...")
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
            self.monitor.set_state("idle", detail="Falha no probe inicial; interface segue disponivel.")
            return True, "Probe inicial falhou, mas a interface continua disponivel. Tente novamente ou use modo offline."

    def chat(self, conversation: list[dict[str, Any]], max_rounds: int | None = None) -> tuple[str, list[str]]:
        if not self.config.llm_allowed:
            return (
                "Modo offline/local sem LLM remoto ativo. Use comandos slash, configure um modelo local (Ollama/localhost) ou troque o runtime.",
                [],
            )

        messages = [
            {"role": "system", "content": system_prompt(self.config)},
            {"role": "system", "content": self.actions.capabilities_summary()},
            {"role": "system", "content": memory_summary(max_items=self.config.max_memory_items)},
            *_trim_conversation(self.config, conversation),
        ]
        tool_logs: list[str] = []
        rounds = max(1, int(max_rounds or self.config.max_tool_rounds))
        self.monitor.set_cancellable(True)

        for round_number in range(1, rounds + 1):
            if self.actions._cancelled():
                raise CancelledExecution("Execucao cancelada pelo usuario.")

            self.monitor.set_state("thinking", detail=f"Pensando... rodada {round_number}/{rounds}")
            response = self._completion(messages, tools=self.actions.tool_schemas())
            assistant_message = response.choices[0].message
            tool_calls = self._tool_calls(assistant_message)
            messages.append(self._message_to_dict(assistant_message))

            if not tool_calls:
                self.monitor.set_state("idle")
                self.monitor.set_cancellable(False)
                return self._message_content(assistant_message), tool_logs

            for call in tool_calls:
                if self.actions._cancelled():
                    raise CancelledExecution("Execucao cancelada pelo usuario.")
                call_id = getattr(call, "id", None) or call.get("id")
                fn = getattr(call, "function", None) or call.get("function", {})
                fn_name = getattr(fn, "name", None) or fn.get("name")
                raw_args = getattr(fn, "arguments", None) or fn.get("arguments", "{}")
                arguments = json.loads(raw_args or "{}")
                self.monitor.set_state("acting", detail=f"Executando ferramenta: {fn_name}")
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
        self.monitor.set_cancellable(False)
        return "Tarefa interrompida apos muitas rodadas de ferramentas. Revise o objetivo ou refine a estrategia.", tool_logs

    def preview_plan(self, goal: str) -> dict[str, Any]:
        return self.planner.preview(goal)

    def execute_plan(self, goal: str, plan: list[dict[str, Any]]) -> dict[str, Any]:
        return self.planner.execute_plan(goal, plan)

    def chat_with_plan(self, goal: str, auto_execute: bool = False) -> dict[str, Any]:
        preview = self.preview_plan(goal)
        if not auto_execute:
            return preview
        return self.execute_plan(goal, preview.get("steps", []))
