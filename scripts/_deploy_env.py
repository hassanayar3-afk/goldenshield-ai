"""قراءة اعتمادات النشر من .env فقط — بلا كلمات مرور مضمّنة."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]


def load_deploy_env() -> None:
    load_dotenv(_ROOT / ".env", override=True)


def require_deploy_credentials() -> tuple[str, str, str]:
    """يعيد (host, user, password) أو يوقف السكربت برسالة واضحة."""
    load_deploy_env()
    host = (os.environ.get("DEPLOY_HOST") or "").strip()
    user = (os.environ.get("DEPLOY_USER") or "root").strip()
    password = (os.environ.get("DEPLOY_PASSWORD") or "").strip()
    if not host:
        print("DEPLOY_HOST مفقود — أضفه إلى .env", file=sys.stderr)
        raise SystemExit(2)
    if not password:
        print(
            "DEPLOY_PASSWORD مفقود — أضفه إلى .env (لا تُخزَّن كلمات المرور في السكربتات)",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return host, user, password
