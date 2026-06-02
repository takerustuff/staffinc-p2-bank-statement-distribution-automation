"""Google OAuth 2.0 — one-time browser login, then silent token refresh."""
from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

_DEFAULT_CLIENT_SECRETS = "credentials.json"
_DEFAULT_TOKEN = "token.json"


def get_credentials(
    client_secrets: str = _DEFAULT_CLIENT_SECRETS,
    token_file: str = _DEFAULT_TOKEN,
) -> Credentials:
    """Return valid credentials, running the browser flow on first use."""
    creds = None
    token_path = Path(token_file)
    secrets_path = Path(client_secrets)

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not secrets_path.exists():
                raise FileNotFoundError(
                    f"OAuth client secrets not found at '{secrets_path}'.\n"
                    "Download credentials.json from Google Cloud Console → "
                    "APIs & Services → Credentials → your OAuth 2.0 Client ID.\n"
                    "Scopes needed: Drive (read-only) + Gmail (send)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
            creds = flow.run_local_server(port=0)

        token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds
