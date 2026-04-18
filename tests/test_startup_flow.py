from __future__ import annotations

from types import SimpleNamespace
import unittest

import main
from core.assistant_actions import extract_assistant_command, normalize_assistant_answer, parse_assistant_actions
from ui.plain_cli import format_onboarding_message, format_session_summary


def make_config():
    account = SimpleNamespace(name="Conta teste", provider_label="OpenAI", model_name="gpt-4o-mini")
    agent = SimpleNamespace(name="Agente teste")
    return SimpleNamespace(active_account=account, active_agent=agent)


class StartupFlowTests(unittest.TestCase):
    def test_resolve_initial_task_prefers_explicit_task(self) -> None:
        self.assertEqual(main.resolve_initial_task("Executa diagnostico", fresh_setup=True), "Executa diagnostico")

    def test_resolve_initial_task_injects_first_run_onboarding(self) -> None:
        task = main.resolve_initial_task(None, fresh_setup=True)

        self.assertIsNotNone(task)
        self.assertIn("primeira execucao", task)
        self.assertIn("/help", task)

    def test_resolve_initial_task_keeps_regular_start_clean(self) -> None:
        self.assertIsNone(main.resolve_initial_task(None, fresh_setup=False))

    def test_format_session_summary_contains_active_profile(self) -> None:
        summary = format_session_summary(make_config())

        self.assertIn("Conta ativa: Conta teste", summary)
        self.assertIn("Agente ativo: Agente teste", summary)
        self.assertIn("Provider: OpenAI", summary)
        self.assertIn("Modelo: gpt-4o-mini", summary)

    def test_format_onboarding_message_mentions_parallel_and_tools(self) -> None:
        message = format_onboarding_message(first_run=True)

        self.assertIn("Primeira sessao concluida", message)
        self.assertIn("/tools", message)
        self.assertIn("nexus parallel run", message)

    def test_normalize_assistant_answer_flags_raw_tool_json_without_execution(self) -> None:
        text, executed = normalize_assistant_answer('[{"tool":"bash","command":"google-chrome &"}]', "abre o chrome", [])

        self.assertFalse(executed)
        self.assertIn("execucao automatica nao foi concluida", text)

    def test_normalize_assistant_answer_hides_long_operational_text_without_execution(self) -> None:
        text, executed = normalize_assistant_answer(
            "Okay, the user just said to close Chrome. I need to think step by step before deciding what command to run.",
            "fecha o chrome que esta aberto",
            [],
        )

        self.assertFalse(executed)
        self.assertIn("sem executar", text)

    def test_extract_assistant_command_accepts_single_safe_command_line(self) -> None:
        self.assertEqual(extract_assistant_command("gh auth status"), "gh auth status")
        self.assertEqual(extract_assistant_command("```bash\ngit status\n```"), "git status")

    def test_extract_assistant_command_rejects_long_reasoning_text(self) -> None:
        self.assertIsNone(
            extract_assistant_command(
                "Okay, the user asked me to check auth. I will think first and maybe use gh auth status after that."
            )
        )

    def test_parse_assistant_actions_supports_terminal_and_visual_formats(self) -> None:
        parsed = parse_assistant_actions(
            '[{"tool":"bash","command":"gh auth status"},{"tool":"controle_periferico","acao":"abrir_app","texto":"chrome"}]'
        )

        self.assertEqual(
            parsed,
            [
                {"kind": "command", "command": "gh auth status"},
                {"kind": "visual", "action": "abrir_app", "target": "chrome"},
            ],
        )

    def test_parse_assistant_actions_supports_close_app_visual_format(self) -> None:
        parsed = parse_assistant_actions('{"tool":"controle_periferico","acao":"fechar_app","texto":"chrome"}')

        self.assertEqual(parsed, [{"kind": "visual", "action": "fechar_app", "target": "chrome"}])
