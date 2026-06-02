"""Google OAuth: one shared credential for Drive (read) + Gmail (send).

First run does an interactive browser consent and caches a refresh token in
token.json. Every run after that is fully unattended — the token auto-refreshes,
so the monthly scheduled job never needs a human.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
]

TOKEN_FILE = "token.json"
CLIENT_SECRET_FILE = "client_secret.json"


def _client_config_from_env() -> dict | None:
    cid = os.environ.get("GOOGLE_CLIENT_ID")
    secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    if not (cid and secret):
        return None
    return {
        "installed": {
            "client_id": cid,
            "client_secret": secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def _run_consent_flow() -> Credentials:
    if Path(CLIENT_SECRET_FILE).exists():
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    else:
        cfg = _client_config_from_env()
        if cfg is None:
            raise FileNotFoundError(
                "No OAuth client found. Provide client_secret.json (Desktop app) "
                "or set GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET in .env."
            )
        flow = InstalledAppFlow.from_client_config(cfg, SCOPES)
    # Opens a browser, runs a tiny local server to catch the redirect.
    # Desktop clients accept any loopback port (use 0). To REUSE an existing
    # "Web" client (e.g. from p1), set GOOGLE_OAUTH_PORT to a fixed port and add
    # http://localhost:<that-port>/ to the client's Authorized redirect URIs.
    port = int(os.environ.get("GOOGLE_OAUTH_PORT", "0"))
    return flow.run_local_server(port=port, prompt="consent")


def get_credentials(interactive: bool = True) -> Credentials:
    """Return valid credentials, refreshing or running consent as needed."""
    creds: Credentials | None = None
    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_info(
            json.loads(Path(TOKEN_FILE).read_text(encoding="utf-8")), SCOPES
        )

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not interactive:
            raise RuntimeError(
                "No valid token and interactive=False. Run `python run.py auth` once."
            )
        creds = _run_consent_flow()

    Path(TOKEN_FILE).write_text(creds.to_json(), encoding="utf-8")
    return creds
