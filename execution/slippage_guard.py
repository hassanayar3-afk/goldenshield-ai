"""حارس الانزلاق قبل التنفيذ."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SlippageGuardResult:
    allowed: bool
    slippage_points: float
    reason: str


def check_slippage(
    *,
    requested_price: float,
    available_price: float,
    max_slippage_points: float,
) -> SlippageGuardResult:
    if requested_price <= 0 or available_price <= 0:
        return SlippageGuardResult(
            True,
            0.0,
            "لا تتوفر أسعار للتحقق من الانزلاق — تمرير افتراضي",
        )
    slip = abs(available_price - requested_price)
    if slip <= max_slippage_points:
        return SlippageGuardResult(
            True,
            slip,
            f"انزلاق مقبول: {slip:.4f}",
        )
    return SlippageGuardResult(
        False,
        slip,
        f"انزلاق مرتفع: {slip:.4f} > {max_slippage_points}",
    )
