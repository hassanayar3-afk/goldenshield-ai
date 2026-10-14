from __future__ import annotations

import json


def test_autopilot_missing_creds_returns_report(monkeypatch, tmp_path):
    monkeypatch.setenv("GOLDENSHIELD_OFFICIAL_ROOT", str(tmp_path))
    (tmp_path / ".env").write_text("MOBILE_PUBLIC_BASE_URL=https://violafashioniq.com/\n", encoding="utf-8")
    (tmp_path / "deploy_ops").mkdir(parents=True, exist_ok=True)
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "cloudflared.exe").write_bytes(b"fake")

    import deploy_ops.cloudflare_tunnel_autopilot as ap

    monkeypatch.setattr(ap, "_cloudflared_exe", lambda _r: tools / "cloudflared.exe")
    monkeypatch.setattr(ap, "_ensure_local_api", lambda _r: False)
    monkeypatch.setattr(ap, "_public_health", lambda *_a, **_k: (False, "skip"))

    rep = ap.run_autopilot()
    assert rep["hostname"] == "violafashioniq.com"
    assert rep.get("ok") is False
    assert "missing_credentials" in str(rep.get("error", "")) or "api_provision" in str(rep.get("error", ""))
