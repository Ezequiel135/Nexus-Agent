from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from textual.widgets import Button, Input

from ui.app import NexusApp


class DummyActions:
    def set_event_callback(self, callback) -> None:
        self.callback = callback

    def privilege_status(self):
        return SimpleNamespace(summary=lambda: "desativado")


class DummyBridge:
    def __init__(self) -> None:
        self.actions = DummyActions()
        self.config = SimpleNamespace(
            active_account=None,
            active_agent=None,
            mcp_servers=[],
            remote_integrations=[],
            remote_armed=False,
            execution_profile="planned",
            runtime_mode="hybrid",
            dry_run=True,
            plan_before_execute=True,
            llm_cache_enabled=True,
            max_tool_rounds=6,
            max_output_tokens=1200,
        )

    def handshake(self):
        return True, "ok"


class DummyMonitor:
    def read(self):
        return SimpleNamespace(
            state="idle",
            current_model="gpt-4o-mini",
            api_latency_ms=0,
            autonomous_mode=False,
            pulse_on=False,
        )


class NexusUiTests(IsolatedAsyncioTestCase):
    async def test_nexus_app_opens_launcher_then_focuses_prompt_after_profile_choice(self) -> None:
        app = NexusApp(DummyBridge(), DummyMonitor())

        with patch("ui.app.save_config"):
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                mode_button = app.query_one("#profile_quick", Button)

                self.assertEqual(app.focused, mode_button)

                app._apply_profile_and_enter("quick")
                await pilot.pause()
                prompt = app.query_one("#prompt", Input)

                self.assertIsNotNone(prompt)
                self.assertEqual(app.focused, prompt)
