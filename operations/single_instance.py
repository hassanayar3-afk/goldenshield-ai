"""قفل تشغيل واحد عالمي + مسار رسمي فقط — يمنع نسختين تتنازعان تيليجرام."""

from __future__ import annotations

import atexit
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_LOCK_HANDLE = None
_LOCK_PATH: Path | None = None

# مسار رسمي ثابت على ويندوز الإنتاج (لا يعتمد على مجلد التشغيل الحالي)
_DEFAULT_OFFICIAL_ROOT = Path(r"C:\GoldenShield_Binance")
_GLOBAL_LOCK_NAME = "bot_instance.lock"


def official_bot_root() -> Path:
    raw = (os.getenv("GOLDENSHIELD_OFFICIAL_ROOT") or "").strip()
    if raw:
        return Path(raw)
    return _DEFAULT_OFFICIAL_ROOT


def global_lock_path() -> Path:
    """قفل واحد لكل الجهاز — حتى لو نُسخت الحزمة لمجلد Downloads."""
    override = (os.getenv("GOLDENSHIELD_INSTANCE_LOCK") or "").strip()
    if override:
        return Path(override)
    # ProgramData أولاً (مشترك)، ثم المجلد الرسمي
    program_data = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
    shared = program_data / "GoldenShield" / _GLOBAL_LOCK_NAME
    try:
        shared.parent.mkdir(parents=True, exist_ok=True)
        return shared
    except Exception:
        root = official_bot_root()
        path = root / "storage" / "runtime" / _GLOBAL_LOCK_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


def is_forbidden_launch_path(cwd: Path | None = None) -> tuple[bool, str]:
    """يمنع التشغيل من تحميلات تيليجرام أو مسارات مؤقتة."""
    try:
        here = (cwd or Path.cwd()).resolve()
        text = str(here).lower()
        bad_markers = (
            "telegram desktop",
            "\\downloads\\",
            "/downloads/",
            "\\temp\\",
            "\\appdata\\local\\temp",
        )
        for marker in bad_markers:
            if marker in text:
                return (
                    True,
                    f"مسار ممنوع للتشغيل: {here} — استخدم فقط {official_bot_root()}",
                )
        # إن وُجد مجلد رسمي، ارفض أي مسار آخر فقط عند تفعيل التعزيز (VPS)
        enforce = (os.getenv("GOLDENSHIELD_ENFORCE_OFFICIAL_ROOT", "false") or "false").strip().lower()
        if enforce in {"1", "true", "yes", "on"}:
            official = official_bot_root().resolve()
            if official.exists():
                try:
                    here.relative_to(official)
                except ValueError:
                    return (
                        True,
                        f"التشغيل مسموح فقط من {official} (الحالي: {here})",
                    )
        return False, ""
    except Exception as exc:  # noqa: BLE001
        logger.debug("is_forbidden_launch_path: %s", exc)
        return False, ""


def kill_other_main_py_processes() -> int:
    """يقتل أي main.py آخر غير هذه العملية — يضمن فرد واحد."""
    killed = 0
    my_pid = os.getpid()
    try:
        import subprocess

        # PowerShell عبر CIM — آمن على ويندوز VPS
        ps = r"""
$my = [int]$env:GS_MY_PID
Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -and ($_.CommandLine -match 'main\.py') -and (
    $_.Name -match 'python|py'
  ) -and ([int]$_.ProcessId -ne $my)
} | ForEach-Object {
  try {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
    Write-Output ("KILLED=" + $_.ProcessId)
  } catch {}
}
"""
        env = os.environ.copy()
        env["GS_MY_PID"] = str(my_pid)
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps,
            ],
            capture_output=True,
            text=True,
            timeout=45,
            env=env,
            check=False,
        )
        for line in (completed.stdout or "").splitlines():
            if line.startswith("KILLED="):
                killed += 1
                logger.warning("أُوقفت نسخة مكررة من البوت: %s", line)
    except Exception as exc:  # noqa: BLE001
        logger.warning("kill_other_main_py_processes: %s", exc)
    return killed


def acquire_single_instance_lock(lock_path: str | Path | None = None) -> bool:
    """قفل عالمي + رفض المسارات الممنوعة + إنهاء النسخ الأخرى."""
    global _LOCK_HANDLE, _LOCK_PATH

    forbidden, reason = is_forbidden_launch_path()
    if forbidden:
        logger.error(reason)
        print(f"🛑 {reason}")
        return False

    # نظّف النسخ الأخرى قبل القفل (خصوصاً Downloads)
    try:
        kill_other_main_py_processes()
    except Exception as exc:  # noqa: BLE001
        logger.warning("تنظيف النسخ المكررة: %s", exc)

    try:
        path = Path(lock_path) if lock_path else global_lock_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        _LOCK_PATH = path

        fh = open(path, "a+", encoding="utf-8")  # noqa: SIM115
        fh.seek(0)
        try:
            import msvcrt

            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        except ImportError:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            logger.error("بوت آخر يمسك القفل العالمي — أوقف النسخ المكررة أولاً")
            print("🛑 بوت آخر يعمل بالفعل (قفل عالمي).")
            return False

        fh.seek(0)
        fh.truncate()
        fh.write(f"{os.getpid()}\n{Path.cwd()}\n")
        fh.flush()
        _LOCK_HANDLE = fh
        atexit.register(release_single_instance_lock)
        logger.info("Single-instance lock OK: %s pid=%s", path, os.getpid())
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("acquire_single_instance_lock فشل: %s", exc)
        # في الإنتاج: الأفضل الفشل الآمن بدل السماح بنسخة ثانية
        enforce = (os.getenv("GOLDENSHIELD_LOCK_FAIL_CLOSED", "true") or "true").strip().lower()
        if enforce in {"1", "true", "yes", "on"}:
            return False
        return True


def release_single_instance_lock() -> None:
    global _LOCK_HANDLE, _LOCK_PATH
    try:
        if _LOCK_HANDLE is not None:
            try:
                import msvcrt

                _LOCK_HANDLE.seek(0)
                msvcrt.locking(_LOCK_HANDLE.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                try:
                    import fcntl

                    fcntl.flock(_LOCK_HANDLE.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
            try:
                _LOCK_HANDLE.close()
            except Exception:
                pass
        _LOCK_HANDLE = None
    except Exception:
        pass


def ensure_singleton_or_exit() -> None:
    """يستدعى من main — يخرج فوراً إن لم نكن الفرد الوحيد."""
    if not acquire_single_instance_lock():
        sys.exit(0)
