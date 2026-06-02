"""Load and validate config.yaml."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class SourceFolder:
    name: str
    id: str


@dataclass
class Financier:
    name: str
    email: str
    entities: list[str]


@dataclass
class Selection:
    mode: str = "latest_per_folder"
    latest_count: int = 1
    period: str = "previous"


@dataclass
class EmailCfg:
    from_name: str = "Finance"
    from_address: str = ""
    max_message_mb: int = 25
    subject_template: str = "Bank Statements — {entity_list} — {period}"
    body_template: str = (
        "Dear {financier},\n\nPlease find attached the latest bank statements "
        "for: {entity_list}.\nReporting period: {period}.\n{part_note}\n"
        "Kind regards,\n{from_name}\n"
    )


@dataclass
class Config:
    source_folders: list[SourceFolder]
    financiers: list[Financier]
    selection: Selection = field(default_factory=Selection)
    email: EmailCfg = field(default_factory=EmailCfg)

    @property
    def needed_entities(self) -> set[str]:
        """Every entity any financier asks for (lower-cased for matching)."""
        wanted: set[str] = set()
        for f in self.financiers:
            wanted.update(e.strip().lower() for e in f.entities)
        return wanted


_VALID_MODES = {"latest_per_folder", "month", "filename_period"}


def load_config(path: str | os.PathLike = "config.yaml") -> Config:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"{p} not found. Copy config.example.yaml to config.yaml and edit it."
        )
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}

    folders = [SourceFolder(**f) for f in raw.get("source_folders", [])]
    if not folders:
        raise ValueError("config.yaml: 'source_folders' is empty.")

    sel_raw = raw.get("selection", {}) or {}
    selection = Selection(
        mode=sel_raw.get("mode", "latest_per_folder"),
        latest_count=int(sel_raw.get("latest_count", 1)),
        period=str(sel_raw.get("period", "previous")),
    )
    if selection.mode not in _VALID_MODES:
        raise ValueError(
            f"selection.mode '{selection.mode}' invalid. Use one of {_VALID_MODES}."
        )

    email = EmailCfg(**{**EmailCfg().__dict__, **(raw.get("email", {}) or {})})

    financiers = []
    for f in raw.get("financiers", []):
        if not f.get("email") or not f.get("entities"):
            raise ValueError(f"Financier '{f.get('name')}' needs email and entities.")
        financiers.append(
            Financier(name=f.get("name", f["email"]), email=f["email"], entities=list(f["entities"]))
        )
    if not financiers:
        raise ValueError("config.yaml: 'financiers' is empty.")

    return Config(source_folders=folders, financiers=financiers, selection=selection, email=email)
