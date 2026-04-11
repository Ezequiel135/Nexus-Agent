from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.actions import AcoesAgente
from core.config import NexusPaths, build_initial_config, make_account, make_agent
from core.execution import apply_execution_profile, should_preview_plan
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


if __name__ == "__main__":
    unittest.main()
