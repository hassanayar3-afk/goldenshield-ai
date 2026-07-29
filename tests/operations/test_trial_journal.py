"""اختبارات سجل مرحلة التجربة."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from operations import trial_journal


class _Settings:
    trial_mode = True
    trial_journal_enabled = True


@pytest.fixture
def journal_path(tmp_path: Path, monkeypatch):
    path = tmp_path / "trial_journal.jsonl"
    monkeypatch.setattr(trial_journal, "JOURNAL_PATH", path)
    return path


def test_log_trade_open_writes_jsonl(journal_path: Path, monkeypatch):
    monkeypatch.setattr("operations.trial_journal.get_settings", lambda: _Settings())

    trial_journal.log_trade_open(
        symbol="BTC/USDT",
        position_id="pos-1",
        entry_price=100.0,
        amount=0.5,
        stop_loss=97.0,
        take_profit=106.0,
        score=8,
        mode="LIVE",
    )

    lines = journal_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event"] == "trade_open"
    assert record["symbol"] == "BTC/USDT"
    assert record["stop_loss"] == 97.0


def test_journal_skipped_when_disabled(journal_path: Path, monkeypatch):
    class S:
        trial_mode = False
        trial_journal_enabled = True

    monkeypatch.setattr("operations.trial_journal.get_settings", lambda: S())
    trial_journal.log_trade_close(
        symbol="BTC/USDT",
        position_id="pos-1",
        exit_price=105.0,
        pnl=2.5,
        reason="Take Profit",
    )
    assert not journal_path.exists()
