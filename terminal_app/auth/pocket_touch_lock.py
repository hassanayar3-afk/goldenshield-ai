"""Pocket Touch Lock — منع اللمس العشوائي في الجيب للأزرار القيادية."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from terminal_app.auth.pin_guard import PinGuard, PinVerificationResult
from terminal_app.auth.token_guard import TokenGuard, TokenVerificationResult


class CriticalAction(str, Enum):
    PANIC = "panic"
    CLOSE_ALL = "close_all"
    CLOSE_WINNERS = "close_winners"
    CLOSE_LOSERS = "close_losers"
    CLOSE_SYMBOL = "close_symbol"
    RESUME = "resume"
    PAUSE = "pause"


@dataclass(frozen=True)
class PocketLockDecision:
    allowed: bool
    reason: str
    code: str
    pin_result: PinVerificationResult | None = None
    token_result: TokenVerificationResult | None = None
    cooldown_seconds_left: float = 0.0


def _runtime_dir() -> Path:
    root = Path(
        (os.getenv("GOLDENSHIELD_OFFICIAL_ROOT") or os.getcwd()).strip()
    )
    if not root.is_dir():
        root = Path.cwd()
    path = root / "storage" / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _state_path() -> Path:
    override = (os.getenv("POCKET_LOCK_STATE_FILE") or "").strip()
    if override:
        return Path(override)
    return _runtime_dir() / "pocket_touch_lock.json"


class PocketTouchLock:
    """قفل جيب: cooldown + confirm + PIN + token للأفعال الحرجة."""

    def __init__(
        self,
        *,
        token_guard: TokenGuard | None = None,
        pin_guard: PinGuard | None = None,
        state_path: Path | None = None,
    ) -> None:
        self._token_guard = token_guard or TokenGuard.from_env()
        self._pin_guard = pin_guard or PinGuard()
        self._state_path = state_path or _state_path()
        self._min_interval = float(os.getenv("POCKET_LOCK_MIN_INTERVAL_SEC", "3.0") or 3.0)
        self._hold_seconds = float(os.getenv("POCKET_LOCK_HOLD_SECONDS", "1.2") or 1.2)

    def enabled(self) -> bool:
        raw = (os.getenv("POCKET_LOCK_ENABLED", "true") or "true").strip().lower()
        return raw in {"1", "true", "yes", "on"}

    def _load_state(self) -> dict[str, Any]:
        if not self._state_path.exists():
            return {}
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_state(self, data: dict[str, Any]) -> None:
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _panic_confirm_expected(self) -> str:
        return (os.getenv("MOBILE_PANIC_CONFIRM") or "CONFIRM-PANIC").strip()

    def _action_is_critical(self, action: str) -> bool:
        try:
            CriticalAction(action)
            return True
        except ValueError:
            return False

    def _check_cooldown(self, action: str) -> PocketLockDecision | None:
        state = self._load_state()
        key = f"last_{action}"
        last = float(state.get(key) or 0.0)
        now = time.time()
        elapsed = now - last
        if elapsed < self._min_interval:
            left = self._min_interval - elapsed
            return PocketLockDecision(
                False,
                f"Pocket Lock: انتظر {left:.1f}s بين الأوامر الحرجة",
                "cooldown",
                cooldown_seconds_left=left,
            )
        return None

    def _touch_cooldown(self, action: str) -> None:
        state = self._load_state()
        state[f"last_{action}"] = time.time()
        self._save_state(state)

    def _verify_hold(self, body: Mapping[str, Any]) -> PocketLockDecision | None:
        hold = body.get("hold_seconds")
        if hold is None:
            hold = body.get("hold_ms")
            if hold is not None:
                try:
                    hold = float(hold) / 1000.0
                except (TypeError, ValueError):
                    hold = 0.0
        try:
            hold_val = float(hold or 0.0)
        except (TypeError, ValueError):
            hold_val = 0.0
        if hold_val + 1e-6 < self._hold_seconds:
            return PocketLockDecision(
                False,
                f"Pocket Lock: مطلوب ضغط {self._hold_seconds:.1f}s (hold_seconds)",
                "hold_required",
            )
        return None

    def _verify_confirm(self, action: str, body: Mapping[str, Any]) -> PocketLockDecision | None:
        if action != CriticalAction.PANIC.value:
            return None
        confirm = str(
            body.get("confirm")
            or body.get("touch_lock_token")
            or body.get("pocket_confirm")
            or ""
        ).strip()
        expected = self._panic_confirm_expected()
        if confirm != expected:
            return PocketLockDecision(
                False,
                "Pocket Lock: confirm غير صالح لطوارئ panic",
                "touch_lock_required",
            )
        return None

    def evaluate_critical_action(
        self,
        action: str,
        body: Mapping[str, Any],
        reader,
    ) -> PocketLockDecision:
        action = (action or "").strip().lower()
        if not self.enabled():
            token_result = self._token_guard.verify(reader)
            if not token_result.ok:
                return PocketLockDecision(
                    False,
                    "unauthorized",
                    "token",
                    token_result=token_result,
                )
            return PocketLockDecision(True, "pocket_lock_disabled", "ok", token_result=token_result)

        if not self._action_is_critical(action):
            token_result = self._token_guard.verify(reader)
            if not token_result.ok:
                return PocketLockDecision(
                    False,
                    "unauthorized",
                    "token",
                    token_result=token_result,
                )
            return PocketLockDecision(True, "non_critical", "ok", token_result=token_result)

        cooldown = self._check_cooldown(action)
        if cooldown is not None:
            return cooldown

        token_result = self._token_guard.verify(reader)
        if not token_result.ok:
            return PocketLockDecision(
                False,
                "unauthorized",
                "token",
                token_result=token_result,
            )

        hold = self._verify_hold(body)
        if hold is not None:
            return hold

        confirm_block = self._verify_confirm(action, body)
        if confirm_block is not None:
            return confirm_block

        pin_result: PinVerificationResult | None = None
        if self._pin_guard.require_pin_for_action(action):
            pin = str(body.get("pin") or body.get("pin_code") or "").strip()
            pin_result = self._pin_guard.verify_pin(pin)
            if not pin_result.ok:
                return PocketLockDecision(
                    False,
                    pin_result.reason,
                    "pin",
                    pin_result=pin_result,
                    token_result=token_result,
                )

        self._touch_cooldown(action)
        latch_path = _runtime_dir() / "panic_touch_lock.flag"
        if action == CriticalAction.PANIC.value:
            try:
                latch_path.write_text("latched", encoding="utf-8")
            except Exception:
                pass

        return PocketLockDecision(
            True,
            "pocket_lock_ok",
            "ok",
            pin_result=pin_result,
            token_result=token_result,
        )
