from unittest.mock import patch

from data.connection_monitor import ConnectionMonitor


def test_disconnected_after_timeout():
    monitor = ConnectionMonitor(timeout_seconds=30)

    with patch("data.connection_monitor.time.monotonic", return_value=100.0):
        monitor.record_success()

    with patch("data.connection_monitor.time.monotonic", return_value=125.0):
        assert monitor.seconds_since_last_success() == 25.0
        assert monitor.is_connected() is True

    with patch("data.connection_monitor.time.monotonic", return_value=131.0):
        assert monitor.is_disconnected() is True
        assert monitor.seconds_since_last_success() == 31.0


def test_not_disconnected_before_first_ping():
    monitor = ConnectionMonitor(timeout_seconds=30)
    assert monitor.is_connected() is True
    assert monitor.seconds_since_last_success() is None
