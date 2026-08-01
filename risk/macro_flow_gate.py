"""بوابة ماكرو/تدفقات اختيارية — لا توقف البوت عند فشل المصدر."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from intelligence.cognitive_config import macro_flow_gate_enabled

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MacroFlowResult:
    approved: bool
    reason: str


def evaluate_macro_flow_gate(*, side: str = "buy", symbol: str | None = None) -> MacroFlowResult:
    """تعزيز Fear&Greed + مناطق الحيتان — رفض ناعم عند تطرف معاكس للاتجاه."""
    try:
        if not macro_flow_gate_enabled():
            return MacroFlowResult(True, "macro flow gate off")

        from core.sentiment.sentiment_analyzer import analyze_sentiment

        fg = analyze_sentiment()
        value = int(fg.fear_greed_index if fg.fear_greed_index is not None else 50)
        side_l = side.lower()
        if side_l == "buy" and value >= 85:
            return MacroFlowResult(
                False,
                f"Fear&Greed={value} تطرف طمع — تجنب شراء جديد",
            )
        if side_l == "sell" and value <= 15:
            return MacroFlowResult(
                False,
                f"Fear&Greed={value} تطرف خوف — تجنب بيع جديد",
            )

        notes = [f"Fear&Greed={value}"]
        if symbol:
            try:
                from core.liquidity.whale_tracker import track_whales

                whales = track_whales(symbol)
                # رفض ناعم فقط عند مقاومة حيتان قوية ضد الشراء / دعم ضد البيع
                if side_l == "buy" and whales.has_whale_resistance and not whales.has_whale_support:
                    return MacroFlowResult(
                        False,
                        f"مناطق حيتان: مقاومة بدون دعم — {whales.reason}",
                    )
                if side_l == "sell" and whales.has_whale_support and not whales.has_whale_resistance:
                    return MacroFlowResult(
                        False,
                        f"مناطق حيتان: دعم بدون مقاومة — {whales.reason}",
                    )
                notes.append(whales.reason)
            except Exception as whale_exc:  # noqa: BLE001
                logger.debug("macro whale layer: %s", whale_exc)

        return MacroFlowResult(True, " | ".join(notes) + " ضمن النطاق")
    except Exception as exc:  # noqa: BLE001
        logger.debug("evaluate_macro_flow_gate: %s", exc)
        return MacroFlowResult(True, "macro flow unavailable — pass")
