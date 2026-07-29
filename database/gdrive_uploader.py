"""رفع النسخ الاحتياطية إلى Google Drive."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GDriveUploadResult:
    uploaded: bool
    message: str
    file_id: str | None = None


def _load_credentials(creds_path: Path):
    try:
        from google.oauth2 import service_account
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        raise ImportError(
            "ثبّت: pip install google-api-python-client google-auth google-auth-oauthlib"
        ) from exc

    scopes = ["https://www.googleapis.com/auth/drive.file"]
    raw = json.loads(creds_path.read_text(encoding="utf-8"))

    if raw.get("type") == "service_account":
        return service_account.Credentials.from_service_account_file(
            str(creds_path),
            scopes=scopes,
        )

    if "installed" in raw or "web" in raw:
        raise ValueError(
            "ملف OAuth client — شغّل scripts/setup_gdrive_oauth.py أولاً لإنشاء token.json"
        )

    return Credentials.from_authorized_user_file(str(creds_path), scopes=scopes)


def upload_backup(backup_path: str) -> GDriveUploadResult:
    creds_path = os.getenv("GDRIVE_CREDENTIALS_PATH", "").strip()
    folder_id = os.getenv("GDRIVE_FOLDER_ID", "").strip()

    if not creds_path or not folder_id:
        return GDriveUploadResult(
            uploaded=False,
            message="ضع GDRIVE_CREDENTIALS_PATH و GDRIVE_FOLDER_ID في .env",
        )

    path = Path(creds_path)
    if not path.exists():
        return GDriveUploadResult(
            uploaded=False,
            message=f"ملف اعتماد Google غير موجود: {creds_path}",
        )

    backup = Path(backup_path)
    if not backup.exists():
        return GDriveUploadResult(False, message="ملف النسخة الاحتياطية غير موجود")

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        return GDriveUploadResult(
            uploaded=False,
            message="ثبّت google-api-python-client: pip install google-api-python-client",
        )

    try:
        creds = _load_credentials(path)
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
        metadata = {"name": backup.name, "parents": [folder_id]}
        media = MediaFileUpload(str(backup), mimetype="application/x-sqlite3", resumable=True)
        created = (
            service.files()
            .create(body=metadata, media_body=media, fields="id,name")
            .execute()
        )
        return GDriveUploadResult(
            uploaded=True,
            message=f"تم الرفع: {created.get('name')} → Drive",
            file_id=created.get("id"),
        )
    except Exception as exc:
        return GDriveUploadResult(
            uploaded=False,
            message=f"فشل رفع Drive: {exc}",
        )
