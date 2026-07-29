from unittest.mock import MagicMock, patch

from operations.api_watchdog import ApiWatchdog
from operations.pre_flight_checklist import run_pre_flight


def test_pre_flight_passes_with_skip_ping():
    monitor = MagicMock()
    monitor.heartbeat.return_value = False
    monitor.last_error = "offline"

    result = run_pre_flight(connection_monitor=monitor, skip_binance_ping=True)

    assert result.ok is True
    names = {c.name for c in result.checks}
    assert "trading_pairs" in names
    assert "telegram_optional" in names


def test_pre_flight_fails_when_binance_ping_fails():
    monitor = MagicMock()
    monitor.heartbeat.return_value = False
    monitor.last_error = "timeout"

    result = run_pre_flight(connection_monitor=monitor, skip_binance_ping=False)

    assert result.ok is False
    assert any(not c.passed for c in result.checks)


def test_api_watchdog_detects_missing_calendar(tmp_path, monkeypatch):
    from config import settings as settings_module

    settings_module._settings = None
    monkeypatch.setenv("ENV", "dev")

    with patch.object(ApiWatchdog, "run", wraps=ApiWatchdog().run) as run:
        monitor = MagicMock()
        monitor.heartbeat.return_value = True
        monitor.last_error = None
        result = run(monitor)
        assert "economic_calendar" in result.checks
