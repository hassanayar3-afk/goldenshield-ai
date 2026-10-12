"""2FA Guard — TOTP اختياري للأفعال الحرجة."""

from __future__ import annotations

import hashlib
import hmac
import os
import struct
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class TwoFAResult:
    ok: bool
    reason: str


def twofa_enabled() -> bool:
    raw = (os.getenv("MOBILE_2FA_ENABLED", "false") or "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _secret_bytes() -> bytes | None:
    secret = (os.getenv("MOBILE_TOTP_SECRET") or "").strip()
    if not secret:
        return None
    try:
        import base64

        pad = "=" * ((8 - len(secret) % 8) % 8)
        return base64.b32decode((secret + pad).upper(), casefold=True)
    except Exception:
        return hashlib.sha256(secret.encode("utf-8")).digest()


def _totp_at(secret: bytes, counter: int, digits: int = 6) -> str:
    msg = struct.pack(">Q", counter)
    digest = hmac.new(secret, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10**digits)).zfill(digits)


def verify_totp(code: str, *, window: int = 1) -> TwoFAResult:
    if not twofa_enabled():
        return TwoFAResult(True, "2fa_disabled")
    secret = _secret_bytes()
    if secret is None:
        return TwoFAResult(False, "totp_secret_missing")
    text = (code or "").strip()
    if not text.isdigit() or len(text) not in {6, 8}:
        return TwoFAResult(False, "totp_format_invalid")
    counter = int(time.time()) // 30
    for step in range(-window, window + 1):
        if _totp_at(secret, counter + step) == text:
            return TwoFAResult(True, "totp_ok")
    return TwoFAResult(False, "totp_invalid")
