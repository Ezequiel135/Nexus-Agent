from __future__ import annotations

import os
import unittest

from core.config import (
    DEFAULT_OLLAMA_BASE_URL,
    LOCAL_API_KEY_PLACEHOLDER,
    build_initial_config,
    make_account,
    make_agent,
)


class LocalRuntimeConfigTests(unittest.TestCase):
    def test_ollama_defaults_base_url_and_model_prefix(self) -> None:
        account = make_account("Conta local", "Ollama", "", "llama3.2")
        agent = make_agent("Agente local", account.id)
        config = build_initial_config("hash", "salt", "plain", account, agent, runtime_mode="offline")

        self.assertEqual(config.model_name, "ollama/llama3.2")
        self.assertEqual(account.completion_kwargs()["base_url"], DEFAULT_OLLAMA_BASE_URL)
        self.assertEqual(account.completion_kwargs()["api_key"], LOCAL_API_KEY_PLACEHOLDER)

    def test_loopback_openai_compatible_runtime_injects_local_api_key(self) -> None:
        account = make_account("Conta local", "OpenAI", "", "gpt-4o-mini", "http://127.0.0.1:1234/v1")
        agent = make_agent("Agente local", account.id)
        config = build_initial_config("hash", "salt", "plain", account, agent, runtime_mode="offline")

        config.export_runtime_env()

        self.assertEqual(account.completion_kwargs()["api_key"], LOCAL_API_KEY_PLACEHOLDER)
        self.assertEqual(os.environ["OPENAI_API_KEY"], LOCAL_API_KEY_PLACEHOLDER)
        self.assertEqual(os.environ["OPENAI_BASE_URL"], "http://127.0.0.1:1234/v1")


if __name__ == "__main__":
    unittest.main()
