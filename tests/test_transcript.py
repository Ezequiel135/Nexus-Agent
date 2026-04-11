from __future__ import annotations

import unittest

from core.transcript import background_interaction, format_activity_log, format_duration, worked_banner


class TranscriptTests(unittest.TestCase):
    def test_format_duration_prefers_compact_units(self) -> None:
        self.assertEqual(format_duration(9), "9s")
        self.assertEqual(format_duration(71), "1m 11s")
        self.assertEqual(format_duration(3661), "1h 1m 1s")

    def test_worked_banner_contains_elapsed_time(self) -> None:
        banner = worked_banner(71)

        self.assertIn("Worked for 1m 11s", banner)

    def test_format_activity_log_for_command_start(self) -> None:
        line = format_activity_log("EXECUTANDO: sudo systemctl status ssh")

        self.assertIn("• Ran `sudo systemctl status ssh`", line)

    def test_format_activity_log_for_structured_log_line(self) -> None:
        line = format_activity_log("[12:00:00] [OK] ARQUIVO: escrever /tmp/demo.txt")

        self.assertIn("Vou mexer em arquivos locais", line)
        self.assertIn("escrever /tmp/demo.txt", line)

    def test_background_interaction_uses_codex_like_shape(self) -> None:
        line = background_interaction("sudo prompt aberto para senha manual")

        self.assertIn("↳ Interacted with background terminal", line)
        self.assertIn("└ sudo prompt aberto para senha manual", line)


if __name__ == "__main__":
    unittest.main()
