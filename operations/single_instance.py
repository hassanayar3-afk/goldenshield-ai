"""قفل تشغيل واحد — يمنع تعدد main.py الذي يخرّب داشبورد تيليجرام."""

from __future__ import annotations

import atexit
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_LOCK_HANDLE = None
_LOCK_PATH: Path | None = None


def acquire_single_instance_lock(lock_path: str | Path | None = None) -> bool:
    """يعيد False إذا كان بوت آخر يعمل."""
    global _LOCK_HANDLE, _LOCK_PATH
    try:
        path = Path(lock_path or "storage/runtime/bot_instance.lock")
        path.parent.mkdir(parents=True, exist_ok=True)
        _LOCK_PATH = path

        # Windows: msvcrt locking على الملف
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
            logger.error("بوت آخر يعمل بالفعل — أوقف النسخ المكررة أولاً")
            return False

        fh.seek(0)
        fh.truncate()
        fh.write(str(os.getpid()))
        fh.flush()
        _LOCK_HANDLE = fh
        atexit.register(release_single_instance_lock)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("acquire_single_instance_lock: %s", exc)
        return True  # لا نوقف التشغيل بسبب فشل القفل التقني


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
