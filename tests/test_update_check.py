from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys

from core.config import NexusPaths
from core.update_check import check_for_update, installed_repo_url


class UpdateCheckTests(unittest.TestCase):
    def test_installed_repo_url_prefers_repo_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "repo.txt"
            repo_path.write_text("https://github.com/test/repo.git\n", encoding="utf-8")
            with patch.object(NexusPaths, "repo_path", repo_path):
                self.assertEqual(installed_repo_url(), "https://github.com/test/repo.git")

    def test_check_for_update_detects_newer_version_and_caches(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "update_check.json"
            fake_response = SimpleNamespace(
                text='APP_VERSION = "26.4.1"\n',
                raise_for_status=lambda: None,
            )
            fake_requests = SimpleNamespace(get=lambda *args, **kwargs: fake_response)
            with patch.object(NexusPaths, "update_check_path", cache_path), patch.dict(
                sys.modules,
                {"requests": fake_requests},
            ):
                info = check_for_update("26.3.1", "https://github.com/Ezequiel135/Nexus-Agent.git")

            self.assertTrue(info.checked)
            self.assertTrue(info.update_available)
            self.assertEqual(info.latest_version, "26.4.1")
            self.assertTrue(cache_path.exists())
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["latest_version"], "26.4.1")

    def test_check_for_update_uses_recent_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "update_check.json"
            cache_path.write_text(
                json.dumps(
                    {
                        "checked_at": "2026-04-11T12:00:00Z",
                        "latest_version": "26.4.1",
                        "repo_url": "https://github.com/Ezequiel135/Nexus-Agent.git",
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(NexusPaths, "update_check_path", cache_path), patch(
                "core.update_check.datetime"
            ) as mock_datetime:
                from datetime import datetime, timezone

                mock_datetime.now.return_value = datetime(2026, 4, 11, 13, 0, 0, tzinfo=timezone.utc)
                mock_datetime.fromisoformat.side_effect = datetime.fromisoformat
                info = check_for_update("26.3.1", "https://github.com/Ezequiel135/Nexus-Agent.git")

            self.assertTrue(info.update_available)
            self.assertEqual(info.latest_version, "26.4.1")


if __name__ == "__main__":
    unittest.main()
