"""تنظيف إقلاع آمن — لا يمس DB/التقارير/.env/الصفقات."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def run_startup_cleanup(*, official_root: str | Path | None = None) -> list[str]:
    """يمسح أقفال عالقة وملفات tmp فقط. يُرجع قائمة بما نُظّف."""
    cleaned: list[str] = []
    try:
        root = Path(
            official_root
            or os.getenv("GOLDENSHIELD_OFFICIAL_ROOT")
            or Path.cwd()
        )
        runtime = root / "storage" / "runtime"
        runtime.mkdir(parents=True, exist_ok=True)

        # أقفال تشغيلية فقط
        for lock_name in ("bot_instance.lock",):
            lock_path = runtime / lock_name
            if lock_path.is_file():
                try:
                    # إن كان القفل قديماً جداً (>2 ساعة) نعتبره عالقاً
                    age = time.time() - lock_path.stat().st_mtime
                    if age > 7200:
                        lock_path.unlink(missing_ok=True)
                        cleaned.append(str(lock_path))
                except Exception as exc:  # noqa: BLE001
                    logger.debug("startup lock cleanup: %s", exc)

        # ProgramData lock إن وُجد وقديم
        pd_lock = Path(r"C:\ProgramData\GoldenShield\bot_instance.lock")
        try:
            if pd_lock.is_file():
                age = time.time() - pd_lock.stat().st_mtime
                if age > 7200:
                    pd_lock.unlink(missing_ok=True)
                    cleaned.append(str(pd_lock))
        except Exception:
            pass

        # ملفات مؤقتة فقط
        for pattern in ("*.tmp", "*.temp", "*~"):
            for path in runtime.glob(pattern):
                try:
                    if path.is_file():
                        path.unlink(missing_ok=True)
                        cleaned.append(str(path))
                except Exception as exc:  # noqa: BLE001
                    logger.debug("startup tmp cleanup: %s", exc)

        if cleaned:
            logger.info("startup_cleanup removed %s items", len(cleaned))
    except Exception as exc:  # noqa: BLE001
        logger.warning("startup_cleanup failed: %s", exc)
    return cleaned
