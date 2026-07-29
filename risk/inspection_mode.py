"""وضع التفتيش الوهمي — تحقق إضافي عند التفعيل الصريح."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class InspectionResult:
    active: bool
    reason: str


def check_inspection_mode() -> InspectionResult:
    enabled = os.getenv("INSPECTION_MODE", "").strip().lower() in {"1", "true", "yes"}

    if enabled:
        return InspectionResult(
            active=True,
            reason="وضع التفتيش — تحقق إضافي قبل التنفيذ",
        )

    return InspectionResult(active=False, reason="وضع إنتاج عادي")
