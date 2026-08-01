"""الذكاء المتقدم — ركائز Cognitive Hedge / Shadow Stress."""

from __future__ import annotations

__all__ = [
    "maybe_register_shadow_hypothesis",
    "resolve_due_shadow_hypotheses",
    "symbol_is_cooled",
    "record_losing_trade_blackbox",
    "get_component_multipliers",
]

from intelligence.adaptive_weights import get_component_multipliers
from intelligence.black_box_logger import record_losing_trade_blackbox
from intelligence.shadow_stress_engine import (
    maybe_register_shadow_hypothesis,
    resolve_due_shadow_hypotheses,
    symbol_is_cooled,
)
