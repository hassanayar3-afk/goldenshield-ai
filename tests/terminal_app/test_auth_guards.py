import os

from terminal_app.auth.pin_guard import PinGuard
from terminal_app.auth.pocket_touch_lock import PocketTouchLock
from terminal_app.auth.token_guard import TokenGuard


class _Reader:
    def __init__(self, token: str = "", path: str = "/api/status"):
        self._token = token
        self.path = path

    def headers_get(self, name: str, default: str = "") -> str:
        if name == "X-GS-Token":
            return self._token
        return default


def test_token_guard_master(tmp_path, monkeypatch):
    monkeypatch.setenv("MOBILE_API_TOKEN", "master-secret-123")
    guard = TokenGuard.from_env()
    ok = guard.verify(_Reader("master-secret-123"))
    assert ok.ok
    bad = guard.verify(_Reader("wrong"))
    assert not bad.ok


def test_pin_guard_set_and_verify(tmp_path, monkeypatch):
    store = tmp_path / "pin.json"
    monkeypatch.setenv("MOBILE_PIN_ENABLED", "true")
    pg = PinGuard(store_path=store)
    assert pg.set_pin("1234").ok
    assert pg.verify_pin("1234").ok
    assert not pg.verify_pin("0000").ok


def test_pocket_lock_panic_confirm(tmp_path, monkeypatch):
    monkeypatch.setenv("MOBILE_API_TOKEN", "tok")
    monkeypatch.setenv("MOBILE_PANIC_CONFIRM", "CONFIRM-PANIC")
    monkeypatch.setenv("MOBILE_PIN_ENABLED", "false")
    monkeypatch.setenv("POCKET_LOCK_ENABLED", "true")
    monkeypatch.setenv("POCKET_LOCK_HOLD_SECONDS", "0")
    state = tmp_path / "pocket.json"
    monkeypatch.setenv("POCKET_LOCK_STATE_FILE", str(state))
    lock = PocketTouchLock(token_guard=TokenGuard(master_token="tok"))
    body = {"confirm": "WRONG"}
    d = lock.evaluate_critical_action("panic", body, _Reader("tok"))
    assert not d.allowed
    body2 = {"confirm": "CONFIRM-PANIC", "hold_seconds": 1.5}
    d2 = lock.evaluate_critical_action("panic", body2, _Reader("tok"))
    assert d2.allowed
