#!/usr/bin/env python3
"""Single-trigger entrypoint for bank-statement distribution.

Commands:
  python run.py auth        One-time browser login (caches token.json).
  python run.py discover    List the entity folders found in Drive.
  python run.py dry-run     Do everything except actually send the emails.
  python run.py send        Pull -> regroup -> zip/split -> email. The monthly job.

Add `--config path.yaml` to point at a different config file.
"""
from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

from bankstmt.config import load_config
from bankstmt.google_auth import get_credentials
from bankstmt.pipeline import run as run_pipeline


def cmd_auth(_args) -> int:
    get_credentials(interactive=True)
    print("✓ Authorized. token.json saved — future runs are unattended.")
    return 0


def cmd_discover(args) -> int:
    from bankstmt.drive import Drive

    cfg = load_config(args.config)
    creds = get_credentials(interactive=True)
    by_entity = Drive(creds).list_entities(cfg.source_folders)
    if not by_entity:
        print("No entity sub-folders found. Check folder IDs / sharing.")
        return 1
    print(f"Entities available across {len(cfg.source_folders)} source folder(s):\n")
    for entity in sorted(by_entity):
        files = by_entity[entity]
        banks = sorted({f.bank for f in files})
        print(f"  • {entity:<14} {len(files):>3} file(s)   banks: {', '.join(banks)}")
    print("\nUse these exact names in the `entities:` lists in config.yaml.")
    return 0


def _run(args, dry_run: bool) -> int:
    cfg = load_config(args.config)
    creds = get_credentials(interactive=not args.unattended)
    result = run_pipeline(cfg, creds, dry_run=dry_run)
    print("\n" + "=" * 60)
    print(f"Period: {result.period} | emails sent: {result.emails_sent} | "
          f"dry-run: {result.dry_run}")
    if result.warnings:
        print("\nWarnings:")
        for w in result.warnings:
            print(f"  ! {w}")
    return 0


def cmd_dry_run(args) -> int:
    return _run(args, dry_run=True)


def cmd_send(args) -> int:
    return _run(args, dry_run=False)


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    except Exception:
        pass
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config.yaml", help="path to config.yaml")
    parser.add_argument("--unattended", action="store_true",
                        help="never prompt; fail if token.json is missing (for scheduled runs)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("auth").set_defaults(func=cmd_auth)
    sub.add_parser("discover").set_defaults(func=cmd_discover)
    sub.add_parser("dry-run").set_defaults(func=cmd_dry_run)
    sub.add_parser("send").set_defaults(func=cmd_send)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as e:  # surface a clean error to the scheduler log
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
