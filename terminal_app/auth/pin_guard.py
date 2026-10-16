"""PIN Guard — PBKDF2، قفل بعد محاولات فاشلة، حماية الأزرار القيادية."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PinVerificationResult:
    ok: bool
    reason: str
    locked_until: float | None = None
    attempts_remaining: int | None = None


def _runtime_dir() -> Path:
    root = Path(
        (os.getenv("GOLDENSHIELD_OFFICIAL_ROOT") or os.getcwd()).strip()
    )
    if not root.is_dir():
        root = Path.cwd()
    path = root / "storage" / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _pin_store_path() -> Path:
    override = (os.getenv("MOBILE_PIN_STORE") or "").strip()
    if override:
        return Path(override)
    return _runtime_dir() / "mobile_pin_guard.json"


def _hash_pin(pin: str, salt_hex: str, iterations: int) -> str:
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        pin.encode("utf-8"),
        salt,
        iterations,
        dklen=32,
    )
    return digest.hex()


class PinGuard:
    """إدارة PIN للتطبيق — اختياري عبر MOBILE_PIN_ENABLED."""

    def __init__(
        self,
        *,
        store_path: Path | None = None,
        max_attempts: int | None = None,
        lockout_seconds: int | None = None,
        pbkdf2_iterations: int | None = None,
    ) -> None:
        self._path = store_path or _pin_store_path()
        self._max_attempts = max_attempts or int(os.getenv("MOBILE_PIN_MAX_ATTEMPTS", "5") or 5)
        self._lockout_seconds = lockout_seconds or int(
            os.getenv("MOBILE_PIN_LOCKOUT_SECONDS", "900") or 900
        )
        self._iterations = pbkdf2_iterations or int(
            os.getenv("MOBILE_PIN_PBKDF2_ITERATIONS", "210000") or 210000
        )

    def enabled(self) -> bool:
        raw = (os.getenv("MOBILE_PIN_ENABLED", "true") or "true").strip().lower()
        return raw in {"1", "true", "yes", "on"}

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save(self, data: dict) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def is_configured(self) -> bool:
        data = self._load()
        return bool(data.get("salt_hex") and data.get("pin_hash_hex"))

    def bootstrap_from_env_if_needed(self) -> None:
        """إذا وُجد MOBILE_PIN في البيئة ولم يُحفظ بعد — يُنشأ المتجر."""
        if self.is_configured():
            return
        env_pin = (os.getenv("MOBILE_PIN") or "").strip()
        if not env_pin:
            return
        self.set_pin(env_pin)

    def set_pin(self, pin: str) -> PinVerificationResult:
        pin = (pin or "").strip()
        if len(pin) < 4 or len(pin) > 12:
            return PinVerificationResult(False, "pin_length_invalid")
        if not pin.isdigit():
            return PinVerificationResult(False, "pin_digits_only")
        salt_hex = secrets.token_hex(16)
        pin_hash_hex = _hash_pin(pin, salt_hex, self._iterations)
        self._save(
            {
                "salt_hex": salt_hex,
                "pin_hash_hex": pin_hash_hex,
                "iterations": self._iterations,
                "failed_attempts": 0,
                "locked_until": 0.0,
                "updated_at": time.time(),
            }
        )
        return PinVerificationResult(True, "pin_set")

    def _locked_state(self, data: dict) -> PinVerificationResult | None:
        locked_until = float(data.get("locked_until") or 0.0)
        now = time.time()
        if locked_until > now:
            return PinVerificationResult(
                False,
                "pin_locked",
                locked_until=locked_until,
                attempts_remaining=0,
            )
        return None

    def verify_pin(self, pin: str) -> PinVerificationResult:
        if not self.enabled():
            return PinVerificationResult(True, "pin_disabled")
        self.bootstrap_from_env_if_needed()
        if not self.is_configured():
            env_pin = (os.getenv("MOBILE_PIN") or "").strip()
            if env_pin and pin.strip() == env_pin:
                return PinVerificationResult(True, "pin_env_fallback")
            return PinVerificationResult(True, "pin_not_configured_skip")

        data = self._load()
        locked = self._locked_state(data)
        if locked is not None:
            return locked

        pin = (pin or "").strip()
        salt_hex = str(data.get("salt_hex") or "")
        expected = str(data.get("pin_hash_hex") or "")
        iterations = int(data.get("iterations") or self._iterations)
        if not salt_hex or not expected:
            return PinVerificationResult(False, "pin_store_corrupt")

        candidate = _hash_pin(pin, salt_hex, iterations)
        if hmac_compare(candidate, expected):
            data["failed_attempts"] = 0
            data["locked_until"] = 0.0
            self._save(data)
            return PinVerificationResult(True, "pin_ok")

        failed = int(data.get("failed_attempts") or 0) + 1
        data["failed_attempts"] = failed
        remaining = max(0, self._max_attempts - failed)
        if failed >= self._max_attempts:
            data["locked_until"] = time.time() + float(self._lockout_seconds)
            data["failed_attempts"] = 0
            self._save(data)
            return PinVerificationResult(
                False,
                "pin_locked_after_failures",
                locked_until=float(data["locked_until"]),
                attempts_remaining=0,
            )
        self._save(data)
        return PinVerificationResult(
            False,
            "pin_wrong",
            attempts_remaining=remaining,
        )

    def require_pin_for_action(self, action: str) -> bool:
        critical = {
            "panic",
            "close_all",
            "close_winners",
            "close_losers",
            "close_symbol",
            "kill",
            "resume",
        }
        return action in critical


def hmac_compare(a: str, b: str) -> bool:
    import hmac

    try:
        return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
    except Exception:
        return False
