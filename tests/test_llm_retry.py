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
