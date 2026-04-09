from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from typing import Any, Callable

from .actions import AcoesAgente
from .config import NexusConfig, activate_agent, find_agent
from .llm import LiteLLMBridge
from .logging_utils import log_event
from .state import ActivityMonitor


class ParallelAgentRunner:
    def __init__(
        self,
        config: NexusConfig,
        *,
        bridge_factory: Callable[[NexusConfig, ActivityMonitor], LiteLLMBridge] | None = None,
        monitor_factory: Callable[[], ActivityMonitor] = ActivityMonitor,
    ) -> None:
        self.config = config
        self._monitor_factory = monitor_factory
        self._bridge_factory = bridge_factory or self._default_bridge_factory

    def run(
        self,
        task: str,
        *,
        agent_queries: list[str] | None = None,
        mode: str = "plan",
        max_rounds: int = 6,
    ) -> dict[str, Any]:
        normalized_mode = (mode or "chat").strip().lower()
        if normalized_mode not in {"chat", "plan"}:
            raise ValueError(f"Modo paralelo nao suportado: {mode}")

        task = (task or "").strip()
        if not task:
            raise ValueError("Tarefa paralela vazia.")

        agents = self._resolve_agents(agent_queries or [])
        worker_count = min(len(agents), 8) or 1
        log_event(
            "PARALLEL",
            f"mode={normalized_mode} agents={','.join(agent.name for agent in agents)} task={task[:160]}",
        )

        results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_map = {
                executor.submit(self._run_agent, agent.id, task, normalized_mode, max_rounds): agent.id
                for agent in agents
            }
            for future in as_completed(future_map):
                results.append(future.result())

        results.sort(key=lambda item: item["agent_name"].lower())
        completed = sum(1 for item in results if item["ok"])
        failed = len(results) - completed
        summary = (
            f"Execucao paralela concluida: {completed}/{len(results)} agente(s) finalizaram com sucesso."
            if failed == 0
            else f"Execucao paralela concluida: {completed}/{len(results)} sucesso(s) e {failed} falha(s)."
        )
        return {
            "ok": failed == 0,
            "mode": normalized_mode,
            "task": task,
            "agent_count": len(results),
            "results": results,
            "summary": summary,
        }

    def _resolve_agents(self, agent_queries: list[str]) -> list[Any]:
        if not self.config.agents:
            raise ValueError("Nenhum agente configurado. Rode nexus add-agent primeiro.")

        if not agent_queries:
            return list(self.config.agents)

        resolved = []
        seen_ids: set[str] = set()
        for query in agent_queries:
            agent = find_agent(self.config, query)
            if agent is None:
                raise ValueError(f"Agente nao encontrado: {query}")
            if agent.id in seen_ids:
                continue
            seen_ids.add(agent.id)
            resolved.append(agent)
        return resolved

    def _run_agent(self, agent_query: str, task: str, mode: str, max_rounds: int) -> dict[str, Any]:
        started = time.perf_counter()
        monitor = self._monitor_factory()
        monitor.start()
        try:
            agent_config = self._clone_config_for_agent(agent_query)
            monitor.set_model(agent_config.model_name)
            monitor.set_autonomous_mode(mode == "chat")
            bridge = self._bridge_factory(agent_config, monitor)

            if mode == "plan":
                execution = bridge.chat_with_plan(task)
                steps = execution.get("results", [])
                tool_logs = [
                    f"{step.get('tool')}({json.dumps(step.get('args', {}), ensure_ascii=False)})"
                    for step in steps
                    if step.get("tool")
                ]
                output = (execution.get("summary") or "").strip() or "Plano gerado."
                payload = {
                    "plan_steps": execution.get("plan_steps", len(steps)),
                    "steps": steps,
                }
            else:
                output, tool_logs = bridge.chat([{"role": "user", "content": task}], max_rounds=max_rounds)
                payload = {}

            elapsed_ms = int((time.perf_counter() - started) * 1000)
            agent = agent_config.active_agent
            account = agent_config.active_account
            return {
                "ok": True,
                "agent_id": agent.id if agent else "",
                "agent_name": agent.name if agent else agent_query,
                "account_name": account.name if account else "-",
                "mode": mode,
                "elapsed_ms": elapsed_ms,
                "output": output.strip(),
                "tool_logs": tool_logs,
                **payload,
            }
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            log_event("PARALLEL", f"Falha em {agent_query}: {exc}", status="ERROR")
            return {
                "ok": False,
                "agent_id": agent_query,
                "agent_name": agent_query,
                "account_name": "-",
                "mode": mode,
                "elapsed_ms": elapsed_ms,
                "output": "",
                "tool_logs": [],
                "error": str(exc),
            }
        finally:
            monitor.stop()

    @staticmethod
    def _default_bridge_factory(config: NexusConfig, monitor: ActivityMonitor) -> LiteLLMBridge:
        return LiteLLMBridge(config, monitor, AcoesAgente(config), export_env=False)

    def _clone_config_for_agent(self, agent_query: str) -> NexusConfig:
        cloned = deepcopy(self.config)
        activate_agent(cloned, agent_query)
        return cloned
