"""محرك المحاكاة العكسية — ظل موازٍ بدون تأخير دخول Demo."""

from __future__ import annotations

import logging
from typing import Any

from core.constants import score_to_percent
from intelligence.cognitive_config import (
    shadow_min_percent,
    shadow_stress_enabled,
    shadow_watch_minutes,
)
from intelligence.shadow_store import ShadowStore
from intelligence.trap_detector import evaluate_traps_after_fail

logger = logging.getLogger(__name__)


def _pattern_key(side: str, score: int) -> str:
    band = "auto90" if score_to_percent(score) >= 90 else "signal"
    return f"{side}:{band}"


def maybe_register_shadow_hypothesis(
    *,
    symbol: str,
    signal: str,
    score: int,
    price: float,
    store: ShadowStore | None = None,
) -> int | None:
    """يسجّل فرضية ظل عند ≥ عتبة الظل — لا يمنع التنفيذ."""
    try:
        if not shadow_stress_enabled():
            return None
        if score_to_percent(score) < shadow_min_percent():
            return None
        if signal not in {"BUY SIGNAL", "SELL SIGNAL"}:
            return None
        side = "buy" if signal == "BUY SIGNAL" else "sell"
        db = store or ShadowStore()
        hyp_id = db.insert_hypothesis(
            symbol=symbol,
            side=side,
            score=int(score),
            entry_price=float(price),
            pattern_key=_pattern_key(side, int(score)),
            watch_minutes=shadow_watch_minutes(),
            notes="parallel_shadow",
        )
        logger.info("shadow hypothesis #%s %s %s @ %.6f", hyp_id, symbol, side, price)
        return hyp_id
    except Exception as exc:  # noqa: BLE001
        logger.warning("maybe_register_shadow_hypothesis: %s", exc)
        return None


def resolve_due_shadow_hypotheses(
    prices: dict[str, float],
    *,
    store: ShadowStore | None = None,
    alerts=None,
) -> list[dict[str, Any]]:
    """يقيّم الفرضيات المنتهية: نجاح إن تحرك السعر مع الاتجاه."""
    out: list[dict[str, Any]] = []
    try:
        if not shadow_stress_enabled():
            return out
        db = store or ShadowStore()
        for hyp in db.due_hypotheses():
            symbol = str(hyp["symbol"])
            px = float(prices.get(symbol) or 0.0)
            if px <= 0:
                continue
            entry = float(hyp["entry_price"])
            side = str(hyp["side"])
            # نجاح ظلّي بسيط: تحرك ≥0.15% مع الاتجاه
            move = (px - entry) / entry if entry > 0 else 0.0
            if side == "buy":
                ok = move >= 0.0015
            else:
                ok = move <= -0.0015
            outcome = "pass" if ok else "fail"
            db.resolve_hypothesis(
                int(hyp["id"]),
                outcome=outcome,
                exit_price=px,
                notes=f"move={move:.5f}",
            )
            row = {**hyp, "outcome": outcome, "exit_price": px, "move": move}
            out.append(row)
            if outcome == "fail":
                evaluate_traps_after_fail(
                    symbol=symbol,
                    pattern_key=str(hyp.get("pattern_key") or ""),
                    store=db,
                    alerts=alerts,
                )
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("resolve_due_shadow_hypotheses: %s", exc)
        return out


def symbol_is_cooled(symbol: str, *, store: ShadowStore | None = None) -> tuple[bool, str]:
    try:
        if not shadow_stress_enabled():
            return False, ""
        db = store or ShadowStore()
        return db.is_cooled(symbol)
    except Exception as exc:  # noqa: BLE001
        logger.warning("symbol_is_cooled: %s", exc)
        return False, ""
