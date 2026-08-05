# -*- coding: utf-8 -*-
"""قاطع دائرة مؤسسي — نقض بعد سلسلة خسائر (افتراضي 3) لمنع التداول الانتقامي."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from config.project_rules import CIRCUIT_BREAKER_MAX_LOSSES

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CircuitBreakerResult:
    approved: bool
    reason: str
    veto: bool = False
    max_losses: int = CIRCUIT_BREAKER_MAX_LOSSES
    consecutive_losses: int = 0


def _max_losses() -> int:
    try:
        return int(
            os.getenv("CIRCUIT_BREAKER_MAX_LOSSES", str(CIRCUIT_BREAKER_MAX_LOSSES))
            or CIRCUIT_BREAKER_MAX_LOSSES
        )
    except (TypeError, ValueError):
        return CIRCUIT_BREAKER_MAX_LOSSES


def evaluate_circuit_breaker(*, consecutive_losses: int = 0) -> CircuitBreakerResult:
    """Veto إذا بلغت الخسائر المتتالية الحد المؤسسي."""
    try:
        limit = max(1, _max_losses())
        losses = int(consecutive_losses or 0)
        if losses >= limit:
            return CircuitBreakerResult(
                approved=False,
                reason=(
                    f"CIRCUIT_BREAKER Veto: {losses} خسائر متتالية "
                    f"(الحد {limit}) — منع التداول الانتقامي"
                ),
                veto=True,
                max_losses=limit,
                consecutive_losses=losses,
            )
        return CircuitBreakerResult(
            approved=True,
            reason=f"CB واضح ({losses}/{limit})",
            veto=False,
            max_losses=limit,
            consecutive_losses=losses,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("evaluate_circuit_breaker: %s", exc)
        return CircuitBreakerResult(True, f"CB bypass: {exc}", False)
