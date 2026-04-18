from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.actions import AcoesAgente
from core.config import NexusPaths, build_initial_config, make_account, make_agent
from core.execution import (
    apply_execution_profile,
    extract_direct_app_target,
    extract_direct_browser_target,
    extract_direct_visual_shortcut,
    should_preview_plan,
)
from core.llm import LiteLLMBridge
from core.privilege import PrivilegeSessionManager
from core.safeguards import command_assessment
from core.state import ActivityMonitor


def make_config(*, runtime_mode: str = "hybrid"):
    account = make_account("Conta", "OpenAI", "sk-test", "gpt-4o-mini")
    agent = make_agent("Agente", account.id)
    config = build_initial_config("hash", "salt", "plain", account, agent, runtime_mode=runtime_mode)
    config.dry_run = False
    return config


class SecurityRuntimeTests(unittest.TestCase):
    def test_malicious_command_is_blocked(self) -> None:
        assessment = command_assessment("rm -rf /")

        self.assertFalse(assessment.allowed)
        self.assertEqual(assessment.level, "red")

    def test_mutating_command_requires_confirmation(self) -> None:
        assessment = command_assessment("mkdir /tmp/nexus-safe-dir")

        self.assertTrue(assessment.allowed)
        self.assertEqual(assessment.level, "yellow")
        self.assertTrue(assessment.needs_confirmation)

    def test_privileged_read_only_command_can_be_classified_as_green(self) -> None:
        assessment = command_assessment("systemctl status ssh", extra_safe_executables={"systemctl"})

        self.assertTrue(assessment.allowed)
        self.assertEqual(assessment.level, "green")
        self.assertFalse(assessment.needs_confirmation)

    def test_file_write_handles_disk_errors_gracefully(self) -> None:
        actions = AcoesAgente(SimpleNamespace(dry_run=False, max_memory_items=6))

        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "saida.txt"
            with patch.object(Path, "write_text", side_effect=OSError("No space left on device")):
                payload = json.loads(actions.gerenciar_arquivos("escrever", str(target), content="x"))

        self.assertFalse(payload["ok"])
        self.assertIn("Falha de IO", payload["erro"])

    def test_offline_runtime_skips_remote_llm_and_stays_available(self) -> None:
        config = make_config(runtime_mode="offline")
        monitor = ActivityMonitor()
        actions = AcoesAgente(config)
        bridge = LiteLLMBridge(config, monitor, actions, export_env=False)

        ok, message = bridge.handshake()
        answer, tool_logs = bridge.chat([{"role": "user", "content": "oi"}])

        self.assertTrue(ok)
        self.assertIn("modo", message.lower())
        self.assertIn("offline", answer.lower())
        self.assertEqual(tool_logs, [])

    def test_smalltalk_returns_immediate_local_reply(self) -> None:
        config = make_config()
        monitor = ActivityMonitor()
        actions = AcoesAgente(config)
        bridge = LiteLLMBridge(config, monitor, actions, export_env=False)

        answer, tool_logs = bridge.chat([{"role": "user", "content": "oi"}])

        self.assertIn("oi", answer.lower())
        self.assertEqual(tool_logs, [])

    def test_delete_in_dry_run_only_previews(self) -> None:
        config = make_config()
        config.dry_run = True
        actions = AcoesAgente(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "arquivo.txt"
            target.write_text("conteudo", encoding="utf-8")
            with patch.object(NexusPaths, "trash_dir", Path(tmpdir) / "trash"), patch.object(NexusPaths, "backups_dir", Path(tmpdir) / "backups"):
                NexusPaths.ensure()
                payload = json.loads(actions.gerenciar_arquivos("deletar", str(target)))
                still_exists = target.exists()

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["dry_run"])
        self.assertTrue(still_exists)

    def test_quick_profile_avoids_plan_for_simple_app_opening_prompt(self) -> None:
        config = make_config()
        apply_execution_profile(config, "quick")

        self.assertFalse(should_preview_plan(config, "abre o firefox e escreve openai na busca"))

    def test_elevated_command_requires_active_privilege_session(self) -> None:
        config = make_config()
        actions = AcoesAgente(config)

        payload = json.loads(actions.executar_comando("systemctl status ssh", elevated=True, privilege="sudo"))

        self.assertFalse(payload["ok"])
        self.assertTrue(payload["requires_privilege_session"])
        self.assertIn("nao esta ativa", payload["erro"])

    def test_root_activation_needs_confirm_and_becomes_active_after_manual_approval(self) -> None:
        manager = PrivilegeSessionManager()

        message = manager.request_root(600, "systemctl")
        self.assertIn("Confirmacao dupla", message)
        self.assertTrue(manager.status().pending_root)

        with patch("core.privilege.subprocess.run", return_value=SimpleNamespace(returncode=0)):
            ok, activation_message = manager.confirm_root()

        self.assertTrue(ok)
        self.assertIn("root ativo", activation_message)
        self.assertTrue(manager.status().active)
        self.assertEqual(manager.status().mode, "root")

    def test_gh_auth_status_is_allowed_as_read_only_command(self) -> None:
        assessment = command_assessment("gh auth status")

        self.assertTrue(assessment.allowed)
        self.assertEqual(assessment.level, "green")
        self.assertFalse(assessment.needs_confirmation)

    def test_gh_repo_and_pr_read_only_commands_are_allowed(self) -> None:
        for command in (
            "gh repo view Ezequiel135/Nexus-Agent",
            "gh pr status",
            "gh pr checks 12",
            "gh issue list",
            "gh run list",
        ):
            with self.subTest(command=command):
                assessment = command_assessment(command)
                self.assertTrue(assessment.allowed)
                self.assertEqual(assessment.level, "green")
                self.assertFalse(assessment.needs_confirmation)

    def test_gh_mutating_command_still_requires_confirmation(self) -> None:
        assessment = command_assessment("gh repo clone Ezequiel135/Nexus-Agent")

        self.assertTrue(assessment.allowed)
        self.assertEqual(assessment.level, "yellow")
        self.assertTrue(assessment.needs_confirmation)

    def test_command_output_is_streamed_while_process_runs(self) -> None:
        config = make_config()
        actions = AcoesAgente(config)
        events: list[str] = []
        actions.set_event_callback(events.append)

        payload = json.loads(actions.executar_comando("python3 -c \"print('nexus-stream')\""))

        self.assertTrue(payload["ok"])
        self.assertIn("nexus-stream", payload["stdout"])
        self.assertTrue(any("command_output" in event and "nexus-stream" in event for event in events))

    def test_direct_browser_prompt_extracts_chrome_alias(self) -> None:
        self.assertEqual(extract_direct_browser_target("abre o chrome"), "chrome")
        self.assertEqual(extract_direct_browser_target("oi abri meu chrome"), "chrome")
        self.assertEqual(extract_direct_browser_target("open firefox"), "firefox")
        self.assertIsNone(extract_direct_browser_target("me explica o chrome"))

    def test_direct_app_prompt_extracts_named_app_and_launcher_fallback(self) -> None:
        self.assertEqual(extract_direct_app_target("abre o spotify"), "spotify")
        self.assertEqual(extract_direct_app_target("abrir vscode no meu pc"), "vscode")
        self.assertEqual(extract_direct_app_target("abri algum app do meu pc"), "__launcher__")
        self.assertIsNone(extract_direct_app_target("me explica o spotify"))

    def test_direct_visual_shortcut_uses_launcher_for_generic_app_request(self) -> None:
        self.assertEqual(extract_direct_visual_shortcut("abre o chrome"), ("abrir_app", "chrome"))
        self.assertEqual(extract_direct_visual_shortcut("fecha o chrome que esta aberto"), ("fechar_app", "chrome"))
        self.assertEqual(extract_direct_visual_shortcut("abri algum app do meu pc"), ("atalho_teclado", "win"))

    def test_open_local_target_uses_browser_launcher(self) -> None:
        config = make_config()
        actions = AcoesAgente(config)
        fake_runtime = SimpleNamespace(
            focus_window=lambda _name: False,
            _command_exists=lambda _command: True,
            BROWSER_WINDOW_TITLES={"chrome": ("google chrome", "chrome")},
            BROWSER_COMMANDS={"linux": {"chrome": [["google-chrome"]]}},
            platform_name=lambda: "linux",
            open_url=lambda url: f"opened:{url}",
            open_application=lambda command: True,
        )

        with patch.dict(sys.modules, {"pc_remote_agent.runtime": fake_runtime}), \
             patch("core.actions.subprocess.Popen") as popen_mock:
            result = actions._open_local_target("chrome")

        self.assertEqual(result, "launched:chrome")
        popen_mock.assert_called()

    def test_close_local_target_uses_runtime_close_application(self) -> None:
        config = make_config()
        actions = AcoesAgente(config)
        fake_runtime = SimpleNamespace(close_application=lambda target: target == "chrome")

        with patch.dict(sys.modules, {"pc_remote_agent.runtime": fake_runtime}):
            result = actions._close_local_target("chrome")

        self.assertEqual(result, "closed:chrome")

    def test_keyboard_shortcut_action_uses_runtime_hotkey(self) -> None:
        config = make_config()
        actions = AcoesAgente(config)
        fake_runtime = SimpleNamespace(
            hotkey=lambda _keys: True,
            click=lambda **_kwargs: None,
            type_text=lambda _text: None,
            move_to=lambda _x, _y: None,
            screen_image=lambda: None,
            mouse_position=lambda: (0, 0),
        )

        with patch.dict(sys.modules, {"pc_remote_agent.runtime": fake_runtime}):
            payload = json.loads(actions.controle_periferico("atalho_teclado", texto="win"))

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["keys"], "win")


if __name__ == "__main__":
    unittest.main()
