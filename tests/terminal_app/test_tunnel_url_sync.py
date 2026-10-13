from __future__ import annotations

from pathlib import Path

from terminal_app.services import bot_bridge as bb


def test_tunnel_url_prefers_runtime_file_over_stale_log(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    logs = tmp_path / "logs"
    runtime.mkdir()
    logs.mkdir()
    monkeypatch.setattr(bb, "RUNTIME", runtime)
    monkeypatch.setattr(bb, "ROOT", tmp_path)
    monkeypatch.setattr(bb, "_CLOUDFLARE_TUNNEL_LOG", logs / "cloudflare_tunnel.log")
    monkeypatch.delenv("MOBILE_PUBLIC_BASE_URL", raising=False)

    (runtime / "mobile_tunnel_url.txt").write_text(
        "https://active-host.trycloudflare.com/\n", encoding="utf-8"
    )
    (logs / "cloudflare_tunnel.log").write_text(
        '{"message":"|  https://stale-log-host.trycloudflare.com  |"}\n',
        encoding="utf-8",
    )
    assert bb.tunnel_url().startswith("https://active-host.trycloudflare.com")


def test_tunnel_url_falls_back_to_log_when_file_missing(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    logs = tmp_path / "logs"
    runtime.mkdir()
    logs.mkdir()
    monkeypatch.setattr(bb, "RUNTIME", runtime)
    monkeypatch.setattr(bb, "ROOT", tmp_path)
    monkeypatch.setattr(bb, "_CLOUDFLARE_TUNNEL_LOG", logs / "cloudflare_tunnel.log")
    monkeypatch.delenv("MOBILE_PUBLIC_BASE_URL", raising=False)

    (logs / "cloudflare_tunnel.log").write_text(
        'Requesting new quick Tunnel on trycloudflare.com\n'
        '{"message":"|  https://new-host.trycloudflare.com  |"}\n',
        encoding="utf-8",
    )
    assert bb.tunnel_url().startswith("https://new-host.trycloudflare.com")
