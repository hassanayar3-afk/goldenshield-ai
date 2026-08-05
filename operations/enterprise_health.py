# -*- coding: utf-8 -*-
"""صحة المؤسسة — تشخيص سريع لأزرار التيليجرام (إنعاش/فحص) دون المساس بـ DB."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def build_enterprise_health_report(*, open_positions: int | None = None) -> str:
    try:
        from config.project_rules import (
            ARCHITECTURE_MODE,
            PROJECT_NAME,
            PROJECT_RULES_VERSION,
            load_project_rules,
        )
        from core.enterprise_pipeline import PIPELINE_STAGES, describe_architecture

        rules = load_project_rules()
        root = Path(os.getcwd())
        db = root / "storage" / "db" / "goldenshield.db"
        log = root / "storage" / "logs" / "bot_stdout.log"
        lock = root / "storage" / "runtime" / "bot_instance.lock"
        stop = root / "storage" / "runtime" / "user_stopped.flag"
        lines = [
            f"🏛 {PROJECT_NAME}",
            f"المعمارية: {ARCHITECTURE_MODE}",
            f"الإصدار: {PROJECT_RULES_VERSION}",
            describe_architecture(),
            f"الهجين: تلقائي≥{rules.auto_soft_min_percent} / بث≥{rules.notify_min_percent}",
            f"CB خسائر: {rules.circuit_breaker_max_losses}",
            f"SSoT: {'ON' if rules.ssot_sync_enabled else 'OFF'}",
            f"مراكز (SSoT): {open_positions if open_positions is not None else '—'}",
            f"DB: {'OK' if db.is_file() else 'MISSING'} | log={'OK' if log.is_file() else '—'}",
            f"قفل مثيل: {'نعم' if lock.is_file() else 'لا'} | إيقاف مستخدم: {'نعم' if stop.is_file() else 'لا'}",
            "خط الأنابيب:",
            " → ".join(PIPELINE_STAGES),
            "",
            "المكتسبات محمية: إغلاق ثلاثي · تقارير زمنية · Smartphone UI · SSoT",
        ]
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        logger.warning("build_enterprise_health_report: %s", exc)
        return f"⚠️ تعذر بناء تقرير الصحة: {exc}"
