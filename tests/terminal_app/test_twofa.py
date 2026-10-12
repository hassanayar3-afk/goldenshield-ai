import os

from terminal_app.auth.twofa_guard import twofa_enabled, verify_totp


def test_twofa_disabled_by_default():
    assert twofa_enabled() is False
    assert verify_totp("").ok


def test_twofa_with_secret(monkeypatch):
    monkeypatch.setenv("MOBILE_2FA_ENABLED", "true")
    monkeypatch.setenv("MOBILE_TOTP_SECRET", "JBSWY3DPEHPK3PXP")
    bad = verify_totp("000000")
    assert not bad.ok
