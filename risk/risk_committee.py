"""لجنة مخاطر لحظية — قواعد افتراضياً + LLM اختياري."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from intelligence.cognitive_config import (
    risk_committee_enabled,
    risk_committee_fail_closed,
    risk_committee_llm_enabled,
)
from intelligence.shadow_stress_engine import symbol_is_cooled
from risk.orderbook_imbalance_gate import evaluate_orderbook_imbalance

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CommitteeDecision:
    approved: bool
    reason: str
    source: str = "rules"


def evaluate_risk_committee(
    *,
    symbol: str,
    side: str,
    score: int,
    signal: str,
    reasons: tuple[str, ...] | list[str] = (),
) -> CommitteeDecision:
    try:
        if not risk_committee_enabled():
            return CommitteeDecision(True, "committee off", "off")

        cooled, cool_reason = symbol_is_cooled(symbol)
        if cooled:
            return CommitteeDecision(False, f"زوج مبرَّد: {cool_reason}", "rules")

        ob = evaluate_orderbook_imbalance(symbol, side=side)
        if not ob.approved:
            return CommitteeDecision(False, ob.reason, "orderbook")

        # شك بسيط من أسباب التحليل
        joined = " ".join(str(r) for r in reasons).lower()
        suspicion_keys = ("manipul", "تلاعب", "spoof", "فخ", "anomaly", "شذوذ")
        if any(k in joined for k in suspicion_keys):
            return CommitteeDecision(
                False,
                "لجنة المخاطر: شك في نوعية الحركة (تلاعب/شذوذ)",
                "rules",
            )

        if risk_committee_llm_enabled():
            llm = _llm_vote(symbol=symbol, side=side, score=score, signal=signal)
            if llm is not None:
                return llm

        return CommitteeDecision(True, "لجنة المخاطر: موافقة قواعدية", "rules")
    except Exception as exc:  # noqa: BLE001
        logger.warning("evaluate_risk_committee: %s", exc)
        if risk_committee_fail_closed():
            return CommitteeDecision(False, f"committee error fail-closed: {exc}", "error")
        return CommitteeDecision(True, f"committee error pass: {exc}", "error")


def _llm_vote(
    *,
    symbol: str,
    side: str,
    score: int,
    signal: str,
) -> CommitteeDecision | None:
    """اختياري: إن وُجد مفتاح OpenAI. الفشل لا يكسر الحلقة."""
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("RISK_COMMITTEE_LLM_API_KEY")
    if not api_key:
        return None
    try:
        import json
        import urllib.request

        prompt = (
            "You are a crypto risk committee. Reply JSON only "
            '{"approved":true|false,"reason":"..."}. '
            f"Symbol={symbol} side={side} score={score}/10 signal={signal}. "
            "Reject only if clear manipulation or poor quality move."
        )
        body = json.dumps(
            {
                "model": os.getenv("RISK_COMMITTEE_LLM_MODEL", "gpt-4o-mini"),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=12) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
        text = (
            payload.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "{}")
        )
        # استخراج JSON بسيط
        start = text.find("{")
        end = text.rfind("}")
        data = json.loads(text[start : end + 1] if start >= 0 and end > start else "{}")
        approved = bool(data.get("approved", True))
        reason = str(data.get("reason") or "llm vote")
        return CommitteeDecision(approved, reason, "llm")
    except Exception as exc:  # noqa: BLE001
        logger.warning("risk committee LLM: %s", exc)
        return None
