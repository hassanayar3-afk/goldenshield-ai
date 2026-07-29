"""اختبارات الإيقاف الدائم وإعادة التشغيل."""

from __future__ import annotations

from operations.runtime_state import OperationsRuntime
from operations.shutdown_guard import (
    clear_user_stop,
    is_user_stopped,
    request_user_stop,
    should_block_signals,
)


def test_request_and_clear_stop(tmp_path, monkeypatch):
    flag = tmp_path / "user_stopped.flag"
    runtime_dir = tmp_path
    monkeypatch.setattr("operations.shutdown_guard.FLAG_PATH", flag)
    monkeypatch.setattr("operations.shutdown_guard.RUNTIME_DIR", runtime_dir)

    assert not is_user_stopped()
    request_user_stop("panic", source="test")
    assert is_user_stopped()
    assert should_block_signals()
    assert clear_user_stop() is True
    assert not is_user_stopped()


def test_runtime_stop_permanent(tmp_path, monkeypatch):
    flag = tmp_path / "user_stopped.flag"
    monkeypatch.setattr("operations.shutdown_guard.FLAG_PATH", flag)
    monkeypatch.setattr("operations.shutdown_guard.RUNTIME_DIR", tmp_path)

    runtime = OperationsRuntime()
    runtime.stop_permanently(reason="telegram_panic")
    assert runtime.user_stopped is True
    assert runtime.paused is True
    runtime.resume()
    assert runtime.paused is True
