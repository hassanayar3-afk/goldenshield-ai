from __future__ import annotations

from datetime import date

from operations.report_archive import (
    build_monthly_review_pack,
    list_month_reports,
    log_bot_activity,
    read_month_bundle,
    save_daily_report_file,
    summarize_activity,
)


def test_save_and_list_month_reports(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_FILE_ARCHIVE_ENABLED", "true")
    monkeypatch.setenv("BOT_ACTIVITY_ARCHIVE_ENABLED", "true")
    monkeypatch.setenv("REPORT_ARCHIVE_DIR", str(tmp_path))
    d = date(2026, 8, 2)
    path = save_daily_report_file("تقرير تجريبي\nPnL=1", report_date=d)
    assert path is not None
    assert path.exists()
    files = list_month_reports(2026, 8)
    assert len(files) == 1
    bundle = read_month_bundle(2026, 8)
    assert "2026-08-02.txt" in bundle
    assert "تقرير تجريبي" in bundle


def test_activity_and_review_pack(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_FILE_ARCHIVE_ENABLED", "true")
    monkeypatch.setenv("BOT_ACTIVITY_ARCHIVE_ENABLED", "true")
    monkeypatch.setenv("REPORT_ARCHIVE_DIR", str(tmp_path))
    log_bot_activity("trade_open", symbol="BTC/USDT", score=9)
    log_bot_activity("trade_close", symbol="BTC/USDT", pnl=1.5)
    log_bot_activity("error", message="test fail")
    summary = summarize_activity(2026, 8)
    assert summary["trade_opens"] == 1
    assert summary["trade_closes"] == 1
    assert summary["errors"] == 1
    pack = build_monthly_review_pack(2026, 8)
    assert pack is not None
    text = pack.read_text(encoding="utf-8")
    assert "الإيجابيات" in text
    assert "يُحذف" in text


def test_archive_can_be_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_FILE_ARCHIVE_ENABLED", "false")
    monkeypatch.setenv("BOT_ACTIVITY_ARCHIVE_ENABLED", "false")
    monkeypatch.setenv("REPORT_ARCHIVE_DIR", str(tmp_path))
    assert save_daily_report_file("x", report_date=date(2026, 8, 2)) is None
    assert list_month_reports(2026, 8) == []
