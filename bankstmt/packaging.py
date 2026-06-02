"""Compress an entity's files into one or more independently-openable zips,
each small enough that emailing it stays under the provider's message limit.

Why independently-openable zips (not a single split .z01/.z02 archive):
financiers' locked-down IT can't always reassemble multi-part archives, but a
plain .zip opens everywhere. So we bin-pack files into several normal zips.

Sizing: providers cap the *encoded* message at ~25 MB and base64 inflates bytes
by ~37%. We therefore target a raw zip size that, once base64-encoded with email
headers, still fits. See `raw_budget_bytes`.
"""
from __future__ import annotations

import math
import zipfile
from dataclasses import dataclass
from pathlib import Path

BASE64_OVERHEAD = 1.37   # base64 grows payload ~4/3; add slack for MIME headers
SAFETY = 0.95            # extra margin so we never graze the limit
COMPRESS_LEVEL = 9       # max deflate compression — helps Excel/images, negligible for PDFs


def raw_budget_bytes(max_message_mb: int) -> int:
    """Largest raw attachment payload that still fits one message."""
    return int(max_message_mb * 1024 * 1024 / BASE64_OVERHEAD * SAFETY)


@dataclass
class Part:
    path: str
    size: int            # raw bytes on disk


def _bin_pack(paths: list[str], budget: int) -> list[list[str]]:
    """Greedy first-fit-decreasing: group file paths into bins <= budget.

    A single file larger than the budget gets its own bin (we can't split a PDF
    here); the caller logs that so it can be handled manually.
    """
    sized = sorted(((p, Path(p).stat().st_size) for p in paths), key=lambda t: -t[1])
    bins: list[list[str]] = []
    bin_sizes: list[int] = []
    for path, size in sized:
        placed = False
        for i, used in enumerate(bin_sizes):
            if used + size <= budget:
                bins[i].append(path)
                bin_sizes[i] += size
                placed = True
                break
        if not placed:
            bins.append([path])
            bin_sizes.append(size)
    return bins


def package_entity(
    entity: str,
    file_paths: list[str],
    out_dir: str,
    period_ym: str,
    max_message_mb: int,
) -> tuple[list[Part], list[str]]:
    """Zip an entity's files into <=budget parts.

    Returns (parts, oversized_warnings).
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    budget = raw_budget_bytes(max_message_mb)

    warnings: list[str] = []
    for p in file_paths:
        if Path(p).stat().st_size > budget:
            warnings.append(
                f"OVERSIZED FILE: '{Path(p).name}' is {_mb(Path(p).stat().st_size)} "
                f"— larger than the {_mb(budget)} per-attachment limit. It will be "
                f"sent as its own zip but the email will likely bounce. "
                f"Manually split this file or request a smaller export from the bank."
            )

    bins = _bin_pack(file_paths, budget)
    multi = len(bins) > 1
    parts: list[Part] = []
    for idx, group in enumerate(bins, start=1):
        suffix = f"_part{idx}of{len(bins)}" if multi else ""
        safe_entity = "".join(c for c in entity if c.isalnum() or c in " _-").strip()
        zip_path = out / f"{safe_entity}_{period_ym}{suffix}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=COMPRESS_LEVEL) as zf:
            for fp in group:
                zf.write(fp, arcname=Path(fp).name)
        parts.append(Part(path=str(zip_path), size=zip_path.stat().st_size))
    return parts, warnings


def pack_attachments_into_emails(parts: list[Part], max_message_mb: int) -> list[list[Part]]:
    """Group finished zips into per-email batches that each fit one message."""
    budget = raw_budget_bytes(max_message_mb)
    batches: list[list[Part]] = []
    cur: list[Part] = []
    cur_size = 0
    for part in sorted(parts, key=lambda p: -p.size):
        if cur and cur_size + part.size > budget:
            batches.append(cur)
            cur, cur_size = [], 0
        cur.append(part)
        cur_size += part.size
    if cur:
        batches.append(cur)
    return batches


def _mb(b: int) -> str:
    return f"{b / 1024 / 1024:.1f} MB"
