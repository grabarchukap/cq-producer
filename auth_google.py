"""
Run this script once locally to authorize Google API access.
It will open a browser window — log in and click Allow.
A token.json file will be saved. Copy it to the server alongside .env.

Usage:
    python auth_google.py
"""
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

_SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"


def main():
    creds_path = Path(CREDENTIALS_FILE)
    if not creds_path.exists():
        print(f"ERROR: {CREDENTIALS_FILE} not found. Download it from Google Cloud Console:")
        print("  APIs & Services → Credentials → OAuth 2.0 Client IDs → Download JSON")
        return

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), _SCOPES)
    creds = flow.run_local_server(port=0)

    Path(TOKEN_FILE).write_text(creds.to_json(), encoding="utf-8")
    print(f"\nAuthorization successful! Token saved to {TOKEN_FILE}")
    print(f"Copy {TOKEN_FILE} to your server alongside .env")


if __name__ == "__main__":
    main()
