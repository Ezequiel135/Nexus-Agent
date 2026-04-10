from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase

from textual.widgets import Input

from ui.app import NexusApp


class DummyActions:
    def set_event_callback(self, callback) -> None:
        self.callback = callback


class DummyBridge:
    def __init__(self) -> None:
        self.actions = DummyActions()
        self.config = SimpleNamespace(
            active_account=None,
            active_agent=None,
            mcp_servers=[],
            remote_integrations=[],
            remote_armed=False,
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
    async def test_nexus_app_mounts_and_focuses_prompt(self) -> None:
        app = NexusApp(DummyBridge(), DummyMonitor())

        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            prompt = app.query_one("#prompt", Input)

            self.assertIsNotNone(prompt)
            self.assertEqual(app.focused, prompt)
