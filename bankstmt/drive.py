"""Google Drive access: walk bank->entity folders and download statement files."""
from __future__ import annotations

import io
from dataclasses import dataclass

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

FOLDER_MIME = "application/vnd.google-apps.folder"
# Google-native docs can't be downloaded raw; we export them. Statements are
# almost always real PDFs/Excel, but handle exports gracefully just in case.
EXPORT_MAP = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
}


@dataclass
class DriveFile:
    id: str
    name: str
    mime_type: str
    size: int            # bytes (0 for Google-native docs)
    modified: str        # RFC3339 timestamp
    bank: str            # source/bank folder name
    entity: str          # entity folder name


class Drive:
    def __init__(self, creds):
        self.svc = build("drive", "v3", credentials=creds, cache_discovery=False)

    # -- listing -----------------------------------------------------------
    def _list_children(self, folder_id: str) -> list[dict]:
        out, token = [], None
        while True:
            resp = (
                self.svc.files()
                .list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    fields="nextPageToken, files(id, name, mimeType, size, modifiedTime)",
                    pageSize=1000,
                    pageToken=token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            out.extend(resp.get("files", []))
            token = resp.get("nextPageToken")
            if not token:
                break
        return out

    def _walk_files(self, folder_id: str, bank: str, entity: str) -> list[DriveFile]:
        """All real files under a folder, recursing into any sub-folders."""
        found: list[DriveFile] = []
        for child in self._list_children(folder_id):
            if child["mimeType"] == FOLDER_MIME:
                found.extend(self._walk_files(child["id"], bank, entity))
            else:
                found.append(
                    DriveFile(
                        id=child["id"],
                        name=child["name"],
                        mime_type=child["mimeType"],
                        size=int(child.get("size", 0) or 0),
                        modified=child.get("modifiedTime", ""),
                        bank=bank,
                        entity=entity,
                    )
                )
        return found

    def list_entities(self, source_folders) -> dict[str, list[DriveFile]]:
        """Return {entity_name: [DriveFile, ...]} merged across all banks.

        Each immediate sub-folder of a bank folder is treated as an entity.
        """
        by_entity: dict[str, list[DriveFile]] = {}
        for src in source_folders:
            for sub in self._list_children(src.id):
                if sub["mimeType"] != FOLDER_MIME:
                    continue  # loose files directly under a bank folder are ignored
                entity = sub["name"].strip()
                files = self._walk_files(sub["id"], bank=src.name, entity=entity)
                by_entity.setdefault(entity, []).extend(files)
        return by_entity

    # -- downloading -------------------------------------------------------
    def download(self, f: DriveFile, dest_dir) -> str:
        from pathlib import Path

        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        name = f.name
        if f.mime_type in EXPORT_MAP:
            export_mime, ext = EXPORT_MAP[f.mime_type]
            if not name.lower().endswith(ext):
                name += ext
            request = self.svc.files().export_media(fileId=f.id, mimeType=export_mime)
        else:
            request = self.svc.files().get_media(fileId=f.id, supportsAllDrives=True)

        # Prefix with bank to avoid collisions when two banks share a filename.
        safe_bank = "".join(c for c in f.bank if c.isalnum() or c in " _-").strip()
        out_path = dest_dir / f"{safe_bank} — {name}" if safe_bank else dest_dir / name

        buf = io.FileIO(out_path, "wb")
        downloader = MediaIoBaseDownload(buf, request, chunksize=8 * 1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        buf.close()
        return str(out_path)
