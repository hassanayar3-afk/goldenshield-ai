"""مراقبة البنية — تنبيهات تشخيصية 24/7 على تيليجرام عند أي خلل."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from operations.message_templates import format_infrastructure_alert
from operations.telegram_bot import TelegramBot

STATE_PATH = Path("storage/logs/infrastructure_watchdog_state.json")


@dataclass(frozen=True)
class CheckResult:
    code: str
    name: str
    ok: bool
    detail: str
    diagnosis: str = ""
    action: str = ""
    location: str = ""


@dataclass
class WatchdogReport:
    checks: list[CheckResult] = field(default_factory=list)
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    @property
    def failures(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.ok]


def _run(cmd: list[str], *, timeout: int = 30) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out.strip()
    except subprocess.TimeoutExpired:
        return 1, "انتهت المهلة"
    except FileNotFoundError:
        return 1, "الأمر غير موجود"
    except Exception as exc:
        return 1, str(exc)


def _tcp_open(host: str, port: int, timeout: float = 5.0) -> tuple[bool, str]:
    if not host:
        return True, "غير مُعدّ"
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"منفذ {port} مفتوح على {host}"
    except OSError as exc:
        return False, f"{host}:{port} — {exc}"


def check_container_running(container: str) -> CheckResult:
    loc = "سيرفر Contabo Linux (Docker)"
    code, out = _run(
        ["docker", "inspect", "-f", "{{.State.Status}} {{.State.ExitCode}} {{.State.Error}}", container],
        timeout=20,
    )
    status_line = out.splitlines()[-1].strip() if out else ""
    parts = status_line.split(maxsplit=2)
    status = parts[0] if parts else ""
    exit_code = parts[1] if len(parts) > 1 else ""
    err = parts[2] if len(parts) > 2 else ""

    if code == 0 and status == "running":
        return CheckResult(
            "container_running",
            "حاوية البوت (Docker)",
            True,
            f"{container} تعمل",
            location=loc,
        )
    if code != 0 and ("No such object" in out or "No such container" in out):
        return CheckResult(
            "container_missing",
            "حاوية البوت (Docker)",
            False,
            f"{container} غير موجودة",
            diagnosis=(
                "الحاوية محذوفة أو لم تُنشأ بعد. التداول الورقي على Contabo متوقف كاملاً."
            ),
            action=(
                "ادخل Contabo ثم:\n"
                "cd /opt/goldenshield\n"
                "docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build"
            ),
            location=loc,
        )
    if status == "exited":
        return CheckResult(
            "container_exited",
            "حاوية البوت (Docker)",
            False,
            f"{container} توقفت (exit={exit_code})",
            diagnosis=(
                f"البوت انهار أو أُغلق. رمز الخروج: {exit_code or '?'}. "
                f"{('خطأ: ' + err) if err and err != '<no value>' else 'راجع سجل الحاوية.'}"
            ),
            action=(
                f"على Contabo نفّذ:\n"
                f"docker start {container}\n"
                f"docker logs --tail 50 {container}"
            ),
            location=loc,
        )
    if status == "restarting":
        return CheckResult(
            "container_restarting",
            "حاوية البوت (Docker)",
            False,
            f"{container} يعيد التشغيل باستمرار",
            diagnosis="الحاوية في حلقة إعادة تشغيل — غالباً خطأ إعداد أو Pre-Flight يفشل.",
            action=f"docker logs --tail 80 {container} ثم أصلح السبب من السجل.",
            location=loc,
        )
    return CheckResult(
        "container_bad_state",
        "حاوية البوت (Docker)",
        False,
        f"{container} — الحالة: {status or out or 'غير معروف'}",
        diagnosis="حالة Docker غير طبيعية للبوت الورقي.",
        action=f"docker ps -a && docker start {container}",
        location=loc,
    )


def check_container_health(container: str) -> CheckResult:
    loc = "سيرفر Contabo — Docker Healthcheck"
    code, out = _run(
        [
            "docker",
            "inspect",
            "-f",
            "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
            container,
        ],
        timeout=20,
    )
    health = out.splitlines()[-1].strip() if out else ""
    if code != 0:
        return CheckResult(
            "health_inspect_fail",
            "صحة الحاوية",
            False,
            out or "فشل الفحص",
            diagnosis="تعذّر قراءة حالة صحة الحاوية.",
            action="تحقق أن Docker يعمل: systemctl status docker",
            location=loc,
        )
    if health in {"healthy", "none"}:
        return CheckResult("health_ok", "صحة الحاوية", True, health, location=loc)
    if health == "starting":
        return CheckResult("health_starting", "صحة الحاوية", True, "قيد الإقلاع", location=loc)
    return CheckResult(
        "health_unhealthy",
        "صحة الحاوية",
        False,
        f"الحالة: {health}",
        diagnosis=(
            "الحاوية تعمل لكن فشل فحص الصحة الداخلي "
            "(إعدادات / اتصال Binance / مجلد قاعدة البيانات)."
        ),
        action=(
            f"docker exec {container} python deployment/health_check.py\n"
            f"docker logs --tail 40 {container}"
        ),
        location=loc,
    )


def check_in_container_health_script(container: str) -> CheckResult:
    loc = "داخل حاوية goldenshield-bot"
    code, out = _run(
        ["docker", "exec", container, "python", "deployment/health_check.py"],
        timeout=40,
    )
    if code == 0 and out.startswith("OK"):
        return CheckResult(
            "app_health_ok",
            "فحص البوت الداخلي",
            True,
            out,
            location=loc,
        )

    low = (out or "").lower()
    if "settings" in low or "SETTINGS_FAIL" in out:
        diagnosis = "فشل تحميل الإعدادات (.env أو ملفات YAML)."
        action = "راجع /opt/goldenshield/.env وملفات config/ على Contabo."
    elif "BINANCE" in out or "binance" in low:
        diagnosis = "فشل الاتصال بـ Binance (مصدر بيانات الأسعار). بدونها لا تحليل ولا إشارات."
        action = "تحقق من شبكة السيرفر أو حظر IP من Binance. جرّب ping من داخل الحاوية."
    elif "DB_DIR" in out:
        diagnosis = "مجلد قاعدة البيانات مفقود أو غير قابل للكتابة."
        action = "mkdir -p /opt/goldenshield/storage/db && docker restart goldenshield-bot"
    else:
        diagnosis = f"فشل فحص الصحة الداخلي: {out or 'بدون تفاصيل'}."
        action = f"docker exec {container} python deployment/health_check.py"

    return CheckResult(
        "app_health_fail",
        "فحص البوت الداخلي",
        False,
        out or "فشل health_check",
        diagnosis=diagnosis,
        action=action,
        location=loc,
    )


def check_recent_activity(container: str, stale_minutes: int) -> CheckResult:
    loc = "سجل البوت داخل Contabo"
    code, out = _run(
        ["docker", "logs", "--since", f"{stale_minutes}m", "--tail", "200", container],
        timeout=45,
    )
    if code != 0:
        return CheckResult(
            "logs_unread",
            "نشاط البوت",
            False,
            out or "تعذّر قراءة السجلات",
            diagnosis="لا يمكن قراءة سجل الحاوية — ربما Docker أو الصلاحيات.",
            action=f"docker logs --tail 50 {container}",
            location=loc,
        )
    markers = ("تحديث الدورة", "Pre-Flight", "GoldenShield AI")
    if any(m in out for m in markers):
        return CheckResult(
            "activity_ok",
            "نشاط البوت",
            True,
            f"نشط خلال آخر {stale_minutes} دقيقة",
            location=loc,
        )

    hung = any(x in out for x in ("Traceback", "ERROR", "فشل Pre-Flight", "Kill Switch"))
    diagnosis = (
        f"الحاوية تعمل لكن لا يوجد تحديث دورة منذ {stale_minutes} دقيقة — "
        "قد يكون البوت متجمداً أو معلّقاً على شبكة/انتظار."
    )
    if hung:
        diagnosis += " وُجدت أخطاء في السجل مؤخراً."
    return CheckResult(
        "activity_stale",
        "نشاط البوت",
        False,
        f"لا دورة جديدة منذ {stale_minutes} دقيقة",
        diagnosis=diagnosis,
        action=(
            f"docker logs --tail 80 {container}\n"
            f"docker restart {container}"
        ),
        location=loc,
    )


def check_windows_server(host: str, port: int) -> CheckResult:
    loc = f"سيرفر Windows للتداول الحقيقي ({host})"
    ok, detail = _tcp_open(host, port)
    if ok:
        return CheckResult(
            "windows_rdp_ok",
            "سيرفر Windows (MT5)",
            True,
            detail,
            diagnosis="منفذ Remote Desktop يستجيب — السيرفر يبدو شغّالاً.",
            action="تأكد داخل السيرفر أن MT5 و00_START.bat مفتوحان.",
            location=loc,
        )
    return CheckResult(
        "windows_unreachable",
        "سيرفر Windows (MT5)",
        False,
        detail,
        diagnosis=(
            "لا وصول لسيرفر Windows من المراقبة. غالباً: السيرفر مطفأ، أو RDP مغلق، "
            "أو جدار ناري يمنع المنفذ. بدون هذا السيرفر لا يعمل التداول الحقيقي عبر XM/MT5."
        ),
        action=(
            "1) افتح Windows Contabo من لوحة Contabo إن لزم\n"
            "2) ادخل RDP وتأكد أن الجهاز يعمل\n"
            "3) افتح MetaTrader 5 وسجّل دخول XM\n"
            "4) شغّل 00_START.bat واترك النافذة مفتوحة\n"
            "5) عند الخروج: Disconnect وليس Log off"
        ),
        location=loc,
    )


def run_infrastructure_checks() -> WatchdogReport:
    container = os.getenv("WATCHDOG_CONTAINER", "goldenshield-bot")
    win_host = os.getenv("WATCHDOG_WINDOWS_HOST", "169.58.15.36").strip()
    win_port = int(os.getenv("WATCHDOG_WINDOWS_PORT", "3389"))
    stale_min = int(os.getenv("WATCHDOG_STALE_MINUTES", "15"))
    check_windows = os.getenv("WATCHDOG_CHECK_WINDOWS", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    report = WatchdogReport()
    report.checks.append(check_container_running(container))

    running = report.checks[-1].ok
    if running:
        report.checks.append(check_container_health(container))
        report.checks.append(check_in_container_health_script(container))
        report.checks.append(check_recent_activity(container, stale_min))

    if check_windows and win_host:
        report.checks.append(check_windows_server(win_host, win_port))

    return report


def _load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _failure_key(report: WatchdogReport) -> str:
    if report.ok:
        return "ok"
    return "|".join(f"{c.code}:{c.detail}" for c in report.failures)


def should_notify(report: WatchdogReport, *, remind_hours: int) -> tuple[bool, str]:
    state = _load_state()
    now = time.time()
    key = _failure_key(report)
    prev_key = state.get("failure_key", "ok")
    last_alert = float(state.get("last_alert_ts", 0))
    remind_seconds = max(remind_hours, 1) * 3600

    if report.ok:
        if prev_key != "ok":
            return True, "recovery"
        return False, "ok"

    if prev_key != key:
        return True, "new_failure"

    if now - last_alert >= remind_seconds:
        return True, "reminder"

    return False, "unchanged"


def _persist_check_state(report: WatchdogReport) -> None:
    state = _load_state()
    state["failure_key"] = _failure_key(report)
    state["last_check_at"] = datetime.now(timezone.utc).isoformat()
    _save_state(state)


def _build_summary(report: WatchdogReport) -> str:
    fails = report.failures
    if not fails:
        return "كل المكوّنات سليمة."
    if len(fails) == 1:
        f = fails[0]
        return f"الخلل في: {f.name} — {f.location or 'موقع غير محدد'}."
    names = " + ".join(f.name for f in fails)
    return f"يوجد {len(fails)} أعطال معاً: {names}."


def send_infrastructure_alert(
    report: WatchdogReport,
    *,
    reason: str,
    telegram: TelegramBot | None = None,
) -> bool:
    bot = telegram or TelegramBot(
        chat_id=os.getenv("WATCHDOG_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
    )
    if not bot.configured:
        print("WATCHDOG: Telegram غير مُعدّ")
        return False

    if reason == "recovery":
        title = "عودة الخدمة ✅ — تم إصلاح الخلل"
        level = "info"
        footer = "المراقبة الآلية: كل الفحوصات ناجحة الآن."
    elif reason == "reminder":
        title = "تذكير: الخلل ما زال قائماً ⚠️"
        level = "emergency"
        footer = "هذه رسالة آلية كل عدة ساعات حتى يُحل الخلل — لا تحتاج مساعدتي."
    else:
        title = "تشخيص خلل في النظام 🚨"
        level = "emergency"
        footer = (
            "مراقبة آلية 24/7 — تصل فور اكتشاف المشكلة بدون تدخل بشري. "
            "اتبع «ماذا تفعل» أدناه."
        )

    text = format_infrastructure_alert(
        level=level,
        title=title,
        summary=_build_summary(report),
        checks=report.checks,
        checked_at=report.checked_at,
        footer=footer,
    )

    sent = bot.send_message(text) is not None
    if sent:
        state = _load_state()
        state["failure_key"] = _failure_key(report)
        state["last_alert_ts"] = time.time()
        state["last_alert_at"] = datetime.now(timezone.utc).isoformat()
        _save_state(state)
    return sent


def main() -> int:
    enabled = os.getenv("WATCHDOG_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    if not enabled:
        print("WATCHDOG_DISABLED")
        return 0

    remind_hours = int(os.getenv("WATCHDOG_REMIND_HOURS", "6"))
    report = run_infrastructure_checks()

    for check in report.checks:
        icon = "✅" if check.ok else "❌"
        print(f"{icon} {check.name}: {check.detail}")
        if not check.ok and check.diagnosis:
            print(f"   تشخيص: {check.diagnosis}")

    notify, reason = should_notify(report, remind_hours=remind_hours)
    if notify:
        send_infrastructure_alert(report, reason=reason)
        print(f"ALERT_SENT reason={reason}")
    else:
        _persist_check_state(report)
        print(f"NO_ALERT reason={reason}")

    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
