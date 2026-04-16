from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

APP_VERSION = "26.4.4"
CALVER_FORMAT = "YY.MICRO.PATCH"
_CALVER_RE = re.compile(r"^(?P<year>\d{2})\.(?P<micro>\d+)\.(?P<patch>\d+)$")


@dataclass(frozen=True, slots=True)
class CalVer:
    year: int
    micro: int
    patch: int

    def __str__(self) -> str:
        return f"{self.year:02d}.{self.micro}.{self.patch}"


def current_calver_year(today: date | None = None) -> int:
    current = today or date.today()
    return current.year % 100


def parse_calver(version: str) -> CalVer:
    match = _CALVER_RE.fullmatch((version or "").strip())
    if match is None:
        raise ValueError(f"Versao CalVer invalida: {version!r}")
    return CalVer(
        year=int(match.group("year")),
        micro=int(match.group("micro")),
        patch=int(match.group("patch")),
    )


def initial_version_for_year(year: int | None = None) -> str:
    return str(CalVer(year=current_calver_year() if year is None else year % 100, micro=1, patch=0))


def bump_feature(version: str, *, year: int | None = None) -> str:
    target_year = current_calver_year() if year is None else year % 100
    parsed = parse_calver(version)
    if parsed.year != target_year:
        return initial_version_for_year(target_year)
    return str(CalVer(year=parsed.year, micro=parsed.micro + 1, patch=0))


def bump_bugfix(version: str, *, year: int | None = None) -> str:
    target_year = current_calver_year() if year is None else year % 100
    parsed = parse_calver(version)
    if parsed.year != target_year:
        return initial_version_for_year(target_year)
    return str(CalVer(year=parsed.year, micro=parsed.micro, patch=parsed.patch + 1))
