"""Decide which files count as 'the latest statements' for a run."""
from __future__ import annotations

import re
from datetime import date

from .config import Selection
from .drive import DriveFile

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def resolve_period(period: str, today: date | None = None) -> str:
    """Turn 'previous' / 'current' / 'YYYY-MM' into a concrete 'YYYY-MM'."""
    today = today or date.today()
    if period == "current":
        return f"{today.year:04d}-{today.month:02d}"
    if period == "previous":
        y, m = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
        return f"{y:04d}-{m:02d}"
    if re.fullmatch(r"\d{4}-\d{2}", period):
        return period
    raise ValueError(f"Unrecognised period '{period}'. Use previous|current|YYYY-MM.")


def _matches_filename_period(name: str, period_ym: str) -> bool:
    year, month = period_ym.split("-")
    month_i = int(month)
    low = name.lower()
    if period_ym in low or f"{year}_{month}" in low or f"{year}{month}" in low:
        return True
    # Month-name forms: "may 2026", "may-2026", "2026 may"
    for token, idx in _MONTHS.items():
        if idx == month_i and token in low and year in low:
            return True
    return False


def select(files: list[DriveFile], sel: Selection, period_ym: str) -> list[DriveFile]:
    """Filter a single entity's files down to the ones to send this run."""
    if not files:
        return []

    if sel.mode == "latest_per_folder":
        # Newest N per (bank, leaf) so each bank's most recent statement is kept.
        groups: dict[str, list[DriveFile]] = {}
        for f in files:
            groups.setdefault(f.bank, []).append(f)
        chosen: list[DriveFile] = []
        for grp in groups.values():
            grp.sort(key=lambda f: f.modified, reverse=True)
            chosen.extend(grp[: max(1, sel.latest_count)])
        return chosen

    if sel.mode == "month":
        return [f for f in files if f.modified[:7] == period_ym]

    if sel.mode == "filename_period":
        return [f for f in files if _matches_filename_period(f.name, period_ym)]

    raise ValueError(f"Unknown selection mode: {sel.mode}")
