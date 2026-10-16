"""اتصال SSH بـ Windows VPS — كلمة مرور أو مفتاح خاص (Cursor Secrets)."""

from __future__ import annotations

import os
import sys
from io import StringIO
from pathlib import Path

import paramiko
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]

class WindowsSSHError(Exception):
    """فشل اتصال SSH بـ Windows VPS."""


DEPLOY_ENV_KEYS = (
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
    "BINANCE_API_KEY_2",
    "BINANCE_API_SECRET_2",
    "BINANCE_DEMO_TRADING",
    "DISCORD_WEBHOOK_URL",
    "DISCORD_BOT_TOKEN",
    "DISCORD_CHANNEL_ID",
    "DISCORD_NOTIFY_ENABLED",
    "TELEGRAM_TOKEN",
    "TELEGRAM_BOT_USERNAME",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_BACKUP_CHANNEL_ID",
    "EXECUTION_MODE",
    "EXECUTION_BACKEND",
)


def load_deploy_env() -> None:
    load_dotenv(_ROOT / ".env", override=True)


def load_local_env_for_deploy() -> dict[str, str]:
    """دمج .env المحلي (إن وُجد) مع متغيرات Cursor Secrets."""
    local: dict[str, str] = {}
    env_file = _ROOT / ".env"
    if env_file.is_file():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                local[k.strip()] = v.strip()
        except OSError:
            pass
    for key in DEPLOY_ENV_KEYS:
        val = (os.environ.get(key) or "").strip()
        if val:
            local[key] = val
    return local


def _load_private_key() -> paramiko.PKey | None:
    raw = (os.environ.get("WIN_SSH_PRIVATE_KEY") or os.environ.get("SSH_PRIVATE_KEY") or "").strip()
    if not raw:
        return None
    if "\\n" in raw and "\n" not in raw:
        raw = raw.replace("\\n", "\n")
    buf = StringIO(raw)
    for key_cls in (
        paramiko.Ed25519Key,
        paramiko.RSAKey,
        paramiko.ECDSAKey,
    ):
        try:
            buf.seek(0)
            return key_cls.from_private_key(buf)  # type: ignore[attr-defined]
        except Exception:
            continue
    return None


def require_windows_credentials() -> tuple[str, str, str, paramiko.PKey | None]:
    load_deploy_env()
    host = (os.environ.get("WIN_HOST") or "").strip()
    user = (os.environ.get("WIN_USER") or "").strip()
    password = (os.environ.get("WIN_PASSWORD") or "").strip()
    pkey = _load_private_key()
    if not host or not user:
        print("WIN_HOST / WIN_USER مفقود — أضفهما إلى Cursor Secrets", file=sys.stderr)
        raise SystemExit(2)
    if not pkey and not password:
        print(
            "لا يمكن SSH: أضف WIN_SSH_PRIVATE_KEY (مُفضّل) أو WIN_PASSWORD "
            "مع PasswordAuthentication على السيرفر",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return host, user, password, pkey


def connect_windows_ssh(timeout: int = 45) -> paramiko.SSHClient:
    host, user, password, pkey = require_windows_credentials()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        if pkey:
            ssh.connect(
                host,
                username=user,
                pkey=pkey,
                timeout=timeout,
                allow_agent=False,
                look_for_keys=False,
            )
        else:
            ssh.connect(
                host,
                username=user,
                password=password,
                timeout=timeout,
                allow_agent=False,
                look_for_keys=False,
            )
    except paramiko.BadAuthenticationType as exc:
        allowed = getattr(exc, "allowed_types", None) or []
        raise WindowsSSHError(
            "SSH يرفض طريقة الدخول. المسموح: "
            f"{allowed}. "
            "أضف WIN_SSH_PRIVATE_KEY في Cursor Secrets "
            "أو فعّل PasswordAuthentication في sshd_config على ويندوز."
        ) from exc
    except Exception as exc:
        raise WindowsSSHError(f"SSH connect failed: {type(exc).__name__}") from exc
    return ssh
