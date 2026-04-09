from __future__ import annotations

from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from textual.containers import Container
from textual.widgets import Input, Select

from ui.app import SetupApp


class SetupUiTests(IsolatedAsyncioTestCase):
    async def test_setup_starts_focused_and_reveals_custom_provider_fields(self) -> None:
        app = SetupApp()

        async with app.run_test(size=(52, 18)) as pilot:
            await pilot.pause()
            self.assertIsNotNone(app.focused)
            self.assertEqual(app.focused.id, "account_name")

            provider = app.query_one("#provider", Select)
            provider.value = "Custom"
            await pilot.pause()

            custom_wrap = app.query_one("#custom-provider-wrap", Container)
            self.assertTrue(custom_wrap.display)

    async def test_setup_submit_returns_payload(self) -> None:
        app = SetupApp()

        with patch("ui.app.save_config") as save_config:
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                app.query_one("#api_key", Input).value = "sk-test"
                app.query_one("#model_name", Input).value = "gpt-4o-mini"
                app.query_one("#password", Input).value = "1234"
                app.action_submit_setup()
                await pilot.pause()

        save_config.assert_called_once()
        self.assertIsNotNone(app.return_value)
        self.assertEqual(app.return_value.ui_mode, "visual")
        self.assertEqual(app.return_value.provider, "OpenAI")
        self.assertEqual(app.return_value.model_name, "gpt-4o-mini")
