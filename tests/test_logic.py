"""Offline checks for the parts that don't need Drive/Gmail: selection,
bin-packing, the 25 MB split, and per-email batching. Run with:

    python -m tests.test_logic     (from the project root)
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from bankstmt.config import Selection
from bankstmt.drive import DriveFile
from bankstmt.packaging import (
    pack_attachments_into_emails,
    package_entity,
    raw_budget_bytes,
    Part,
)
from bankstmt.selection import resolve_period, select


def _df(name, bank, modified, size=1000):
    return DriveFile(id=name, name=name, mime_type="application/pdf",
                     size=size, modified=modified, bank=bank, entity="SMI")


def test_resolve_period():
    import datetime
    assert resolve_period("2026-05") == "2026-05"
    assert resolve_period("previous", datetime.date(2026, 1, 15)) == "2025-12"
    assert resolve_period("current", datetime.date(2026, 6, 1)) == "2026-06"
    print("✓ period resolution")


def test_selection_latest():
    files = [
        _df("may.pdf", "BCA", "2026-05-31T00:00:00Z"),
        _df("apr.pdf", "BCA", "2026-04-30T00:00:00Z"),
        _df("may_mandiri.pdf", "Mandiri", "2026-05-15T00:00:00Z"),
    ]
    sel = Selection(mode="latest_per_folder", latest_count=1)
    chosen = select(files, sel, "2026-05")
    names = {f.name for f in chosen}
    assert names == {"may.pdf", "may_mandiri.pdf"}, names  # newest per bank
    print("✓ latest_per_folder picks newest per bank")


def test_selection_filename_period():
    files = [_df("Statement May 2026.pdf", "BCA", "2026-06-02T00:00:00Z"),
             _df("Statement Apr 2026.pdf", "BCA", "2026-05-02T00:00:00Z")]
    sel = Selection(mode="filename_period")
    chosen = select(files, sel, "2026-05")
    assert {f.name for f in chosen} == {"Statement May 2026.pdf"}
    print("✓ filename_period matches month names")


def test_packaging_splits_under_budget():
    budget = raw_budget_bytes(25)
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        src = d / "src"
        src.mkdir()
        # Five ~7 MB incompressible files => must span multiple zips under budget.
        paths = []
        for i in range(5):
            p = src / f"stmt_{i}.bin"
            p.write_bytes(os.urandom(7 * 1024 * 1024))
            paths.append(str(p))
        parts, warns = package_entity("SMI", paths, str(d / "out"), "2026-05", 25)
        assert len(parts) >= 2, "expected a split into multiple zips"
        for part in parts:
            assert part.size <= budget, f"{part.path} {part.size} > {budget}"
        assert not warns
        print(f"✓ packaging split 35 MB into {len(parts)} zips, all <= budget")


def test_email_batching():
    budget = raw_budget_bytes(25)
    parts = [Part(path=f"z{i}.zip", size=10 * 1024 * 1024) for i in range(5)]
    batches = pack_attachments_into_emails(parts, 25)
    assert len(batches) >= 3
    for b in batches:
        assert sum(p.size for p in b) <= budget
    print(f"✓ 50 MB of zips batched into {len(batches)} emails, each <= budget")


def main():
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    except Exception:
        pass
    test_resolve_period()
    test_selection_latest()
    test_selection_filename_period()
    test_packaging_splits_under_budget()
    test_email_batching()
    print("\nAll offline checks passed.")


if __name__ == "__main__":
    main()
