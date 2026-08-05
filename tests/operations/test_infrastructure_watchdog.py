"""اختبارات مراقب البنية التشخيصي."""

import operations.infrastructure_watchdog as wd
from operations.infrastructure_watchdog import (
    CheckResult,
    WatchdogReport,
    _failure_key,
    should_notify,
)
from operations.message_templates import format_infrastructure_alert


def _isolate_state(tmp_path, monkeypatch):
    monkeypatch.setattr(wd, "STATE_PATH", tmp_path / "state.json")


def _fail(name: str = "حاوية البوت", detail: str = "متوقفة") -> CheckResult:
    return CheckResult(
        "container_exited",
        name,
        False,
        detail,
        diagnosis="البوت انهار على Contabo.",
        action="docker start goldenshield-bot",
        location="Contabo Docker",
    )


def test_should_notify_on_new_failure(tmp_path, monkeypatch):
    _isolate_state(tmp_path, monkeypatch)
    report = WatchdogReport(checks=[_fail()])
    notify, reason = should_notify(report, remind_hours=6)
    assert notify is True
    assert reason == "new_failure"


def test_should_not_repeat_immediately(tmp_path, monkeypatch):
    _isolate_state(tmp_path, monkeypatch)
    import time

    report = WatchdogReport(checks=[_fail()])
    should_notify(report, remind_hours=6)
    wd._save_state(
        {"failure_key": _failure_key(report), "last_alert_ts": time.time()}
    )
    notify, reason = should_notify(report, remind_hours=6)
    assert notify is False
    assert reason == "unchanged"


def test_should_notify_recovery(tmp_path, monkeypatch):
    _isolate_state(tmp_path, monkeypatch)
    fail = WatchdogReport(checks=[_fail()])
    wd._save_state({"failure_key": _failure_key(fail), "last_alert_ts": 0})
    report = WatchdogReport(
        checks=[
            CheckResult("container_running", "حاوية البوت", True, "تعمل", location="Contabo")
        ]
    )
    notify, reason = should_notify(report, remind_hours=6)
    assert notify is True
    assert reason == "recovery"


def test_diagnostic_alert_format():
    text = format_infrastructure_alert(
        level="emergency",
        title="تشخيص خلل في النظام",
        summary="الخلل في: سيرفر Windows",
        checks=[
            CheckResult(
                "windows_unreachable",
                "سيرفر Windows (Binance)",
                False,
                "timed out",
                diagnosis="السيرفر مطفأ أو RDP مغلق.",
                action="ادخل RDP وشغّل 00_START.bat",
                location="Windows Contabo 169.58.15.36",
            ),
            CheckResult(
                "container_running",
                "حاوية البوت",
                True,
                "تعمل",
                location="Contabo Linux",
            ),
        ],
        checked_at="2026-07-14T06:00:00+00:00",
        footer="مراقبة آلية",
    )
    assert "التشخيص" in text
    assert "ماذا تفعل" in text
    assert "المكان" in text
    assert "Windows" in text
    assert "سليم حالياً" in text


def test_failure_key_stable():
    report = WatchdogReport(checks=[_fail()])
    assert "container_exited" in _failure_key(report)
