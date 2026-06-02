"""End-to-end orchestration: Drive -> regroup -> zip/split -> email."""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .drive import Drive
from .mailer import GmailSender
from .packaging import pack_attachments_into_emails, package_entity
from .selection import resolve_period, select


@dataclass
class RunResult:
    period: str
    entities_found: list[str] = field(default_factory=list)
    emails_sent: int = 0
    messages: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    dry_run: bool = False


def run(cfg: Config, creds, dry_run: bool = False, work_root: str = "work", log=print) -> RunResult:
    period = resolve_period(cfg.selection.period)
    result = RunResult(period=period, dry_run=dry_run)

    drive = Drive(creds)
    log("Scanning source folders in Drive…")
    by_entity = drive.list_entities(cfg.source_folders)
    result.entities_found = sorted(by_entity)
    log(f"Found {len(by_entity)} entities: {', '.join(result.entities_found) or '(none)'}")

    # Only download entities someone actually needs.
    needed = cfg.needed_entities
    work = Path(work_root)
    if work.exists():
        shutil.rmtree(work)

    # 1) Select + download the latest files per needed entity (once, shared).
    entity_files: dict[str, list[str]] = {}
    for entity, files in by_entity.items():
        if entity.lower() not in needed:
            continue
        chosen = select(files, cfg.selection, period)
        if not chosen:
            log(f"  [{entity}] no statements matched for {period} — skipping")
            continue
        dest = work / "downloads" / entity
        log(f"  [{entity}] downloading {len(chosen)} file(s)…")
        paths = [drive.download(f, dest) for f in chosen]
        entity_files[entity] = paths

    # 2) Per-financier: bundle all entity files into one zip, split only if > 25 MB.
    sender = None
    if not dry_run:
        sender = GmailSender(cfg.email.from_name, cfg.email.from_address)

    for fin in cfg.financiers:
        all_paths: list[str] = []
        covered: list[str] = []
        for name in fin.entities:
            key = _canon(name, entity_files)
            if key and entity_files.get(key):
                all_paths.extend(entity_files[key])
                covered.append(name)
        if not all_paths:
            msg = f"[{fin.name}] nothing to send (no statements for {fin.entities})"
            log(msg)
            result.messages.append(msg)
            continue

        safe_name = "".join(c for c in fin.name if c.isalnum() or c in " _-").strip()
        parts, warns = package_entity(
            safe_name, all_paths, str(work / "packages" / safe_name), period, cfg.email.max_message_mb
        )
        result.warnings.extend(warns)

        batches = pack_attachments_into_emails(parts, cfg.email.max_message_mb)
        entity_list = ", ".join(covered)
        for i, batch in enumerate(batches, start=1):
            part_note = ""
            if len(batches) > 1:
                part_note = f"This is email {i} of {len(batches)} for this submission.\n"
            subject = cfg.email.subject_template.format(
                financier=fin.name, entity_list=entity_list, period=period,
                from_name=cfg.email.from_name, part_note=part_note,
            )
            if len(batches) > 1:
                subject += f" ({i}/{len(batches)})"
            body = cfg.email.body_template.format(
                financier=fin.name, entity_list=entity_list, period=period,
                from_name=cfg.email.from_name, part_note=part_note,
            )
            files = [p.path for p in batch]
            total_mb = sum(p.size for p in batch) / 1024 / 1024
            if dry_run:
                msg = (f"[DRY-RUN] would email {fin.email} ({entity_list}) "
                       f"#{i}/{len(batches)} — {len(files)} zip(s), {total_mb:.1f} MB")
                log(msg)
                result.messages.append(msg)
            else:
                mid = sender.send(
                    fin.email, subject, body, files,
                    financier=fin.name, entity_list=entity_list,
                    period=period, part_note=part_note,
                )
                msg = (f"[SENT] {fin.email} ({entity_list}) #{i}/{len(batches)} — "
                       f"{len(files)} zip(s), {total_mb:.1f} MB — id={mid}")
                log(msg)
                result.messages.append(msg)
                result.emails_sent += 1

    return result


def _canon(name: str, entity_files: dict[str, list[str]]) -> str | None:
    """Resolve a requested entity name to the key used in entity_files."""
    low = name.strip().lower()
    for key in entity_files:
        if key.lower() == low:
            return key
    return None
