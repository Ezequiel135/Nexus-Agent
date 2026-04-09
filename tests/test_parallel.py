from __future__ import annotations

import unittest

from core.config import add_account, add_agent, build_initial_config, make_account, make_agent
from core.parallel import ParallelAgentRunner


class FakeBridge:
    def __init__(self, config, monitor) -> None:
        self.config = config
        self.monitor = monitor

    def chat(self, conversation, max_rounds=6):
        agent = self.config.active_agent
        account = self.config.active_account
        task = conversation[-1]["content"]
        return f"{agent.name}:{account.name}:{task}:{max_rounds}", [f"log:{agent.id}"]

    def chat_with_plan(self, goal):
        agent = self.config.active_agent
        return {
            "goal": goal,
            "plan_steps": 1,
            "results": [
                {
                    "step": 1,
                    "task": f"Planejar como {agent.name}",
                    "tool": None,
                    "args": {},
                    "result": "OK",
                }
            ],
            "summary": f"Plano gerado por {agent.name}",
        }


def make_config():
    account_a = make_account("Conta A", "OpenAI", "key-a", "gpt-4o-mini")
    agent_a = make_agent("Agente A", account_a.id, "Foco em execucao")
    config = build_initial_config("hash", "salt", "plain", account_a, agent_a)

    account_b = make_account(
        "Conta B",
        "OpenAI",
        "key-b",
        "gpt-4o-mini",
        existing_ids={item.id for item in config.accounts},
    )
    add_account(config, account_b, activate=False)
    add_agent(
        config,
        make_agent("Agente B", account_b.id, "Foco em revisao", existing_ids={item.id for item in config.agents}),
        activate=False,
    )
    return config


class ParallelAgentRunnerTests(unittest.TestCase):
    def test_run_chat_with_all_agents(self) -> None:
        runner = ParallelAgentRunner(make_config(), bridge_factory=lambda config, monitor: FakeBridge(config, monitor))

        result = runner.run("Resumo tecnico", mode="chat")

        self.assertEqual(result["agent_count"], 2)
        self.assertTrue(result["ok"])
        outputs = {item["output"] for item in result["results"]}
        self.assertIn("Agente A:Conta A:Resumo tecnico:6", outputs)
        self.assertIn("Agente B:Conta B:Resumo tecnico:6", outputs)

    def test_run_plan_with_selected_agent(self) -> None:
        runner = ParallelAgentRunner(make_config(), bridge_factory=lambda config, monitor: FakeBridge(config, monitor))

        result = runner.run("Planejar release", agent_queries=["Agente B"], mode="plan")

        self.assertEqual(result["agent_count"], 1)
        self.assertEqual(result["results"][0]["agent_name"], "Agente B")
        self.assertEqual(result["results"][0]["plan_steps"], 1)
        self.assertEqual(result["results"][0]["output"], "Plano gerado por Agente B")


if __name__ == "__main__":
    unittest.main()
