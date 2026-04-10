from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_PY = REPO_ROOT / "main.py"
SETUP_CLI_PY = REPO_ROOT / "ui" / "setup_cli.py"


def build_setup_env(home_dir: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "NEXUS_HOME": home_dir,
            "NEXUS_UI_MODE": "plain",
            "NEXUS_PASSWORD": "1234",
            "NEXUS_ACCOUNT_NAME": "Conta teste",
            "NEXUS_AGENT_NAME": "Agente teste",
            "NEXUS_PROVIDER": "OpenAI",
            "NEXUS_API_KEY": "sk-test",
            "NEXUS_MODEL_NAME": "gpt-4o-mini",
        }
    )
    return env


class EntrypointExecutionTests(unittest.TestCase):
    def _assert_setup_result(self, result: subprocess.CompletedProcess[str], home_dir: str) -> None:
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        config_path = Path(home_dir) / "config.json"
        self.assertTrue(config_path.exists(), msg=result.stdout + result.stderr)

        payload = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["accounts"][0]["name"], "Conta teste")
        self.assertEqual(payload["agents"][0]["name"], "Agente teste")
        self.assertEqual(payload["ui_mode"], "plain")

    def test_main_setup_runs_from_outside_repo(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as work_dir:
            result = subprocess.run(
                [sys.executable, str(MAIN_PY), "setup"],
                cwd=work_dir,
                capture_output=True,
                text=True,
                env=build_setup_env(home_dir),
            )
            self._assert_setup_result(result, home_dir)

    def test_setup_cli_runs_from_outside_repo(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as work_dir:
            result = subprocess.run(
                [sys.executable, str(SETUP_CLI_PY)],
                cwd=work_dir,
                capture_output=True,
                text=True,
                env=build_setup_env(home_dir),
            )
            self._assert_setup_result(result, home_dir)
