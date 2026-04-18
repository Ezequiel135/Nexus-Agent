from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import core.llm as llm


class DummyMonitor:
    def __init__(self) -> None:
        self.latencies: list[int] = []
        self.states: list[tuple[str, str]] = []

    def set_latency(self, latency_ms: int) -> None:
        self.latencies.append(latency_ms)

    def set_state(self, state: str, error: str = "") -> None:
        self.states.append((state, error))


class LlmRetryTests(TestCase):
    def test_system_prompt_requires_executable_json_for_operational_requests(self) -> None:
        config = SimpleNamespace(
            runtime_mode="hybrid",
            execution_profile="quick",
            active_account=SimpleNamespace(name="Conta", provider_label="OpenAI", model_name="gpt-4o-mini"),
            active_agent=SimpleNamespace(name="Agente", system_prompt=""),
            dry_run=False,
            plan_before_execute=False,
            response_language="pt-BR",
        )

        prompt = llm.system_prompt(config, latest_user_prompt="abre o chrome", conversational=False)

        self.assertIn("prefira tool calls", prompt)
        self.assertIn("devolva apenas JSON executavel", prompt)

    def test_system_prompt_keeps_conversation_mode_without_operational_json_contract(self) -> None:
        config = SimpleNamespace(
            runtime_mode="hybrid",
            execution_profile="quick",
            active_account=None,
            active_agent=None,
            dry_run=False,
            plan_before_execute=False,
            response_language="pt-BR",
        )

        prompt = llm.system_prompt(config, latest_user_prompt="oi", conversational=True)

        self.assertIn("Modo atual: conversa direta", prompt)
        self.assertNotIn("devolva apenas JSON executavel", prompt)

    def test_parse_tool_arguments_accepts_json_and_python_dict(self) -> None:
        self.assertEqual(llm._parse_tool_arguments('{"comando":"gh auth status"}'), {"comando": "gh auth status"})
        self.assertEqual(llm._parse_tool_arguments("{'acao': 'abrir_app', 'texto': 'chrome'}"), {"acao": "abrir_app", "texto": "chrome"})
        self.assertEqual(llm._parse_tool_arguments("{invalido"), {})

    def test_retry_delay_seconds_is_progressive(self) -> None:
        self.assertEqual(llm.retry_delay_seconds(1), 10)
        self.assertEqual(llm.retry_delay_seconds(2), 20)
        self.assertEqual(llm.retry_delay_seconds(3), 30)

    def test_is_retryable_llm_error_detects_quota_errors(self) -> None:
        self.assertTrue(llm.is_retryable_llm_error(RuntimeError("429 insufficient_quota")))
        self.assertTrue(llm.is_retryable_llm_error(RuntimeError("Too Many Requests")))
        self.assertFalse(llm.is_retryable_llm_error(RuntimeError("invalid api key")))

    def test_completion_with_retries_waits_and_recovers(self) -> None:
        config = SimpleNamespace(model_name="gpt-4o-mini", completion_kwargs=lambda: {})
        monitor = DummyMonitor()
        calls = {"count": 0}

        def fake_completion(**_kwargs):
            calls["count"] += 1
            if calls["count"] < 3:
                raise RuntimeError("429 insufficient_quota")
            return SimpleNamespace(choices=[])

        fake_litellm = SimpleNamespace(completion=fake_completion)
        sleep_calls: list[int] = []

        with patch.dict("sys.modules", {"litellm": fake_litellm}):
            with patch("core.llm.time.sleep", side_effect=lambda seconds: sleep_calls.append(seconds)):
                response = llm.completion_with_retries(config, monitor, [{"role": "user", "content": "oi"}])

        self.assertEqual(calls["count"], 3)
        self.assertEqual(sleep_calls, [10, 20])
        self.assertEqual(response.choices, [])

    def test_completion_with_retries_does_not_retry_invalid_key(self) -> None:
        config = SimpleNamespace(model_name="gpt-4o-mini", completion_kwargs=lambda: {})
        monitor = DummyMonitor()

        def fake_completion(**_kwargs):
            raise RuntimeError("invalid api key")

        fake_litellm = SimpleNamespace(completion=fake_completion)

        with patch.dict("sys.modules", {"litellm": fake_litellm}):
            with patch("core.llm.time.sleep") as sleep_mock:
                with self.assertRaises(RuntimeError):
                    llm.completion_with_retries(config, monitor, [{"role": "user", "content": "oi"}])

        sleep_mock.assert_not_called()
