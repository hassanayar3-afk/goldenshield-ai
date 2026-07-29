"""إعداد OAuth لـ Google Drive — يُنشئ token.json من client_secret.json."""

from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

CLIENT_SECRET = BASE / "storage" / "gdrive_client_secret.json"
TOKEN_PATH = BASE / "storage" / "gdrive_token.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def main() -> int:
    if not CLIENT_SECRET.exists():
        print("❌ ضع ملف client_secret من Google Cloud هنا:")
        print(f"   {CLIENT_SECRET}")
        print("\nالخطوات:")
        print("1) https://console.cloud.google.com → APIs → Enable Google Drive API")
        print("2) Credentials → OAuth Client ID → Desktop app")
        print("3) حمّل JSON واحفظه بالمسار أعلاه")
        return 1

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("❌ ثبّت: pip install google-auth-oauthlib google-api-python-client")
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    print(f"✅ تم حفظ token: {TOKEN_PATH}")
    print("ضع في .env:")
    print(f"GDRIVE_CREDENTIALS_PATH={TOKEN_PATH}")
    print("GDRIVE_FOLDER_ID=معرّف_مجلد_Drive")
    return 0


if __name__ == "__main__":
    sys.exit(main())
