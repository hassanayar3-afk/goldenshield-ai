"""تحليل المشاعر الاجتماعية — Crypto Community."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import requests

COINGECKO_IDS = {
    "BTC/USDT": "bitcoin",
    "ETH/USDT": "ethereum",
    "BNB/USDT": "binancecoin",
}


class SocialBias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class SocialSentimentResult:
    bias: SocialBias
    community_score: float | None
    sentiment_votes_up: int | None
    sentiment_votes_down: int | None
    reason: str


def analyze_social_sentiment(symbol: str) -> SocialSentimentResult:
    """جلب بيانات مجتمع CoinGecko كبديل عملي لـ Social Sentiment."""
    coin_id = COINGECKO_IDS.get(symbol)
    if coin_id is None:
        return SocialSentimentResult(
            bias=SocialBias.NEUTRAL,
            community_score=None,
            sentiment_votes_up=None,
            sentiment_votes_down=None,
            reason=f"لا بيانات social لـ {symbol}",
        )

    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"

    try:
        response = requests.get(url, timeout=12, params={"localization": "false"})
        response.raise_for_status()
        payload = response.json()
        community = payload.get("community_data") or {}
        sentiment = payload.get("sentiment_votes_up_percentage")

        up = community.get("twitter_followers") or 0
        down = community.get("reddit_subscribers") or 0
        score = float(sentiment) if sentiment is not None else None

        if score is not None and score >= 65:
            bias = SocialBias.BULLISH
        elif score is not None and score <= 35:
            bias = SocialBias.BEARISH
        else:
            bias = SocialBias.NEUTRAL

        return SocialSentimentResult(
            bias=bias,
            community_score=score,
            sentiment_votes_up=int(up) if up else None,
            sentiment_votes_down=int(down) if down else None,
            reason=f"Social {symbol}: score={score} twitter={up} reddit={down}",
        )
    except Exception as exc:
        return SocialSentimentResult(
            bias=SocialBias.NEUTRAL,
            community_score=None,
            sentiment_votes_up=None,
            sentiment_votes_down=None,
            reason=f"تعذر جلب social sentiment: {exc}",
        )
