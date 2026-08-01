"""أوزان تكيفية خفيفة لمكوّنات التسجيل (±حد أقصى)."""

from __future__ import annotations

import logging
from typing import Any

from intelligence.cognitive_config import (
    adaptive_weight_max_delta,
    adaptive_weights_enabled,
)
from intelligence.shadow_store import ShadowStore

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "timeframe_alignment": 1.0,
    "smc": 1.0,
    "fvg": 1.0,
    "mean_reversion": 1.0,
    "volume": 1.0,
}


def get_component_multipliers() -> dict[str, float]:
    if not adaptive_weights_enabled():
        return dict(_DEFAULTS)
    try:
        stored = ShadowStore().get_weights()
        out = dict(_DEFAULTS)
        out.update(stored)
        return out
    except Exception as exc:  # noqa: BLE001
        logger.debug("get_component_multipliers: %s", exc)
        return dict(_DEFAULTS)


def apply_weight_multipliers(components: dict[str, int]) -> dict[str, int]:
    """يضرب نقاط المكوّنات ثم يعيد تقريبية صحيحة مع سقف بسيط."""
    mult = get_component_multipliers()
    out: dict[str, int] = {}
    for key, pts in components.items():
        m = float(mult.get(key, 1.0))
        out[key] = max(0, int(round(pts * m)))
    return out


def soften_component_after_loss(*, reason: str) -> dict[str, Any]:
    """يخفض وزن مكوّن مرتبط بسبب الخسارة ضمن الحد المسموح."""
    if not adaptive_weights_enabled():
        return {}
    try:
        key = "smc"
        low = reason.lower()
        if "volume" in low or "حجم" in reason:
            key = "volume"
        elif "fvg" in low:
            key = "fvg"
        elif "ارتداد" in reason or "reversion" in low:
            key = "mean_reversion"
        elif "إطار" in reason or "timeframe" in low:
            key = "timeframe_alignment"

        store = ShadowStore()
        current = store.get_weights().get(key, 1.0)
        delta = adaptive_weight_max_delta()
        new_w = max(1.0 - delta, min(1.0 + delta, current - 0.05))
        store.set_weight(key, new_w)
        return {key: round(new_w, 3)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("soften_component_after_loss: %s", exc)
        return {}


def reinforce_from_shadow_pass() -> None:
    """رفع طفيف لأوزان عامة بعد يوم ناجح للظل."""
    if not adaptive_weights_enabled():
        return
    try:
        store = ShadowStore()
        stats = store.count_recent_outcomes(hours=24)
        wins = int(stats.get("pass", 0))
        fails = int(stats.get("fail", 0))
        if wins <= fails or wins < 3:
            return
        for key in _DEFAULTS:
            cur = store.get_weights().get(key, 1.0)
            store.set_weight(key, min(1.0 + adaptive_weight_max_delta(), cur + 0.02))
    except Exception as exc:  # noqa: BLE001
        logger.debug("reinforce_from_shadow_pass: %s", exc)
