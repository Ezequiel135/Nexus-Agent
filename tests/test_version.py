from __future__ import annotations

import unittest

from core.version import APP_VERSION, bump_bugfix, bump_feature, initial_version_for_year, parse_calver


class VersionTests(unittest.TestCase):
    def test_app_version_matches_release(self) -> None:
        self.assertEqual(APP_VERSION, "26.4.6")

    def test_initial_version_for_year(self) -> None:
        self.assertEqual(initial_version_for_year(2026), "26.1.0")

    def test_bump_feature_same_year(self) -> None:
        self.assertEqual(bump_feature("26.1.0", year=2026), "26.2.0")

    def test_bump_bugfix_same_year(self) -> None:
        self.assertEqual(bump_bugfix("26.1.0", year=2026), "26.1.1")

    def test_year_rollover_resets(self) -> None:
        self.assertEqual(bump_feature("26.9.4", year=2027), "27.1.0")
        self.assertEqual(bump_bugfix("26.9.4", year=2027), "27.1.0")

    def test_parse_invalid_version_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_calver("26.1")


if __name__ == "__main__":
    unittest.main()
