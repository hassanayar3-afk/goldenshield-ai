from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import requests

from config.settings import get_settings

FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1"


class SentimentBias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class SentimentResult:
    bias: SentimentBias
    fear_greed_index: int | None
    classification: str | None
    is_extreme: bool
    reason: str


def analyze_sentiment() -> SentimentResult:
    settings = get_settings()

    try:
        response = requests.get(FEAR_GREED_URL, timeout=10)
        response.raise_for_status()
        payload = response.json()
        entry = payload.get("data", [{}])[0]
        index = int(entry.get("value", 50))
        classification = str(entry.get("value_classification", "Neutral"))
    except Exception as exc:
        return SentimentResult(
            bias=SentimentBias.NEUTRAL,
            fear_greed_index=None,
            classification=None,
            is_extreme=False,
            reason=f"تعذر جلب Fear & Greed: {exc}",
        )

    if index <= settings.fear_greed_extreme_low:
        return SentimentResult(
            bias=SentimentBias.BULLISH,
            fear_greed_index=index,
            classification=classification,
            is_extreme=True,
            reason=f"خوف مفرط ({index}) — فرصة ارتداد",
        )

    if index >= settings.fear_greed_extreme_high:
        return SentimentResult(
            bias=SentimentBias.BEARISH,
            fear_greed_index=index,
            classification=classification,
            is_extreme=True,
            reason=f"طمع مفرط ({index}) — حذر",
        )

    if index >= 55:
        bias = SentimentBias.BULLISH
    elif index <= 45:
        bias = SentimentBias.BEARISH
    else:
        bias = SentimentBias.NEUTRAL

    return SentimentResult(
        bias=bias,
        fear_greed_index=index,
        classification=classification,
        is_extreme=False,
        reason=f"Fear & Greed = {index} ({classification})",
    )
