"""فلتر الإشارات — النظام الهجين: تلقائي 9–10 | يدوي 7–8 عبر تيليجرام."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.constants import (
    SIGNAL_NOTIFY_MIN_PERCENT,
    is_auto_entry_allowed,
    meets_telegram_notify_minimum,
    score_to_percent,
)

if TYPE_CHECKING:
    from audit.consensus_gate import ConsensusResult
    from core.analyzer import AnalysisResult
    from risk.risk_orchestrator import RiskApproval

_ENTRY_SIGNALS = frozenset({"BUY SIGNAL", "SELL SIGNAL"})


def _telegram_notify_min_percent() -> int:
    try:
        from config.project_rules import load_project_rules

        rules = load_project_rules()
        return int(rules.notify_min_percent or SIGNAL_NOTIFY_MIN_PERCENT)
    except Exception:
        try:
            from config.settings import get_settings

            return int(
                getattr(get_settings(), "telegram_signal_min_percent", SIGNAL_NOTIFY_MIN_PERCENT)
                or SIGNAL_NOTIFY_MIN_PERCENT
            )
        except Exception:
            return int(SIGNAL_NOTIFY_MIN_PERCENT)


def is_notifiable_trade_signal(result: AnalysisResult | object) -> bool:
    """تُرسل لتليجرام: شراء/بيع بدرجة ≥7 (هجين) — لا WAIT."""
    if getattr(result, "halted", False):
        return False
    signal = str(getattr(result, "signal", ""))
    if signal not in _ENTRY_SIGNALS:
        return False
    score = getattr(result, "score", 0)
    try:
        from config.project_rules import is_hybrid_notifiable_score, load_project_rules

        if load_project_rules().hybrid_mode:
            return is_hybrid_notifiable_score(score)
    except Exception:
        pass
    passed = bool(getattr(result, "passed", False))
    return passed and meets_telegram_notify_minimum(
        score, min_percent=_telegram_notify_min_percent()
    )


def is_notifiable_entry(entry: dict) -> bool:
    """نفس القاعدة لقائمة الدورة — فرص جاهزة للإرسال فقط."""
    signal = str(entry.get("signal", ""))
    if signal not in _ENTRY_SIGNALS:
        return False
    score = int(entry.get("score", 0) or 0)
    try:
        from config.project_rules import is_hybrid_notifiable_score, load_project_rules

        if load_project_rules().hybrid_mode:
            return is_hybrid_notifiable_score(score)
    except Exception:
        pass
    if entry.get("passed") is False:
        return False
    return meets_telegram_notify_minimum(
        score, min_percent=_telegram_notify_min_percent()
    )


def entry_action_label(score: int | float, open_positions: int = 0) -> str:
    """وسم طريقة الدخول — هجين: تلقائي 9–10 / يدوي 7–8."""
    try:
        from config.project_rules import hybrid_entry_label, load_project_rules

        if load_project_rules().hybrid_mode:
            return hybrid_entry_label(score)
    except Exception:
        pass

    from config.settings import get_settings
    from core.constants import is_golden_opportunity

    threshold = int(getattr(get_settings(), "auto_entry_min_percent", 90) or 90)
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
    """مؤهل كامل = شراء/بيع ≥ عتبة الإرسال + Shadow + مخاطر."""
    if not is_notifiable_trade_signal(result):
        return False
    if consensus is not None and not consensus.approved:
        return False
    if risk_approval is not None and not risk_approval.approved:
        return False
    return True
