"""فلتر الإشارات — فقط صفقات جاهزة للدخول (تلقائي أو يدوي)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.constants import is_auto_entry_allowed, meets_signal_minimum, score_to_percent

if TYPE_CHECKING:
    from audit.consensus_gate import ConsensusResult
    from core.analyzer import AnalysisResult
    from risk.risk_orchestrator import RiskApproval

_ENTRY_SIGNALS = frozenset({"BUY SIGNAL", "SELL SIGNAL"})


def is_notifiable_trade_signal(result: AnalysisResult | object) -> bool:
    """تُرسل لتليجرام فقط إذا شراء/بيع ≥75 — لا WAIT ولا انتظار."""
    if getattr(result, "halted", False):
        return False
    signal = str(getattr(result, "signal", ""))
    if signal not in _ENTRY_SIGNALS:
        return False
    score = getattr(result, "score", 0)
    passed = bool(getattr(result, "passed", False))
    return passed and meets_signal_minimum(score)


def is_notifiable_entry(entry: dict) -> bool:
    """نفس القاعدة لقائمة الدورة — فرص جاهزة للدخول فقط."""
    signal = str(entry.get("signal", ""))
    if signal not in _ENTRY_SIGNALS:
        return False
    score = int(entry.get("score", 0) or 0)
    if entry.get("passed") is False:
        return False
    return meets_signal_minimum(score)


def entry_action_label(score: int | float, open_positions: int = 0) -> str:
    """وسم طريقة الدخول: تلقائي (≥95) أو يدوي."""
    from config.settings import get_settings
    from core.constants import is_golden_opportunity

    threshold = int(getattr(get_settings(), "auto_entry_min_percent", 95) or 95)
    auto_ok, _ = is_auto_entry_allowed(score, open_positions, soft_min=threshold)
    pct = score_to_percent(score)
    if auto_ok and is_golden_opportunity(score):
        return f"ذهبي تلقائي ⚡ ({pct}/100)"
    if auto_ok:
        return f"تلقائي ⚡ ({pct}/100)"
    return f"يدوي 🖐 ({pct}/100)"

def annotate_entry_actions(
    entries: list[dict],
    *,
    open_positions: int = 0,
) -> list[dict]:
    """نسخ الفرص المؤهلة مع وسم الدخول — بدون WAIT."""
    out: list[dict] = []
    for entry in entries:
        if not is_notifiable_entry(entry):
            continue
        row = dict(entry)
        row["entry_action"] = entry_action_label(
            int(entry.get("score", 0) or 0),
            open_positions,
        )
        out.append(row)
    return sorted(out, key=lambda e: int(e.get("score", 0)))


def is_premium_trade_signal(
    result: AnalysisResult,
    *,
    consensus: ConsensusResult | None = None,
    risk_approval: RiskApproval | None = None,
) -> bool:
    """مؤهل كامل = شراء/بيع ≥75 + Shadow + مخاطر."""
    if not is_notifiable_trade_signal(result):
        return False
    if consensus is not None and not consensus.approved:
        return False
    if risk_approval is not None and not risk_approval.approved:
        return False
    return True
