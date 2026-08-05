# -*- coding: utf-8 -*-
"""Autonomous Enterprise Trading Architecture — خط الأنابيب المؤسسي المتسلسل.

يربط الإدارات الموجودة دون استبدال منطقها. كل مرحلة تُرجع موافقة أو نقضاً (Veto).
السلسلة الحصرية:
  Sensing → Hierarchical SMC/ICT → Whale/Trap → Noise → Audit/CB/Veto →
  Hybrid Exec (≥90 auto / ≥70 broadcast) → Risk/ATR/Sizing → Field/SSoT/Telegram
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from config.project_rules import (
    ARCHITECTURE_MODE,
    CIRCUIT_BREAKER_MAX_LOSSES,
    ENTERPRISE_TIMEFRAMES,
    PROJECT_NAME,
    hybrid_entry_label,
    is_hybrid_auto_score,
    is_hybrid_manual_broadcast_score,
    load_project_rules,
)

logger = logging.getLogger(__name__)

PIPELINE_STAGES: tuple[str, ...] = (
    "sensing",
    "hierarchical_smc_ict",
    "whale_trap_hunting",
    "noise_filter",
    "audit_circuit_veto",
    "hybrid_execution_gate",
    "risk_sizing",
    "field_ssot_telegram",
)


@dataclass(frozen=True)
class PipelineStageResult:
    stage: str
    approved: bool
    reason: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineVerdict:
    approved: bool
    vetoed: bool
    stage: str
    reason: str
    stages: tuple[PipelineStageResult, ...] = ()
    entry_mode: str = "none"  # auto | manual_broadcast | none


def describe_architecture() -> str:
    rules = load_project_rules()
    return (
        f"{PROJECT_NAME} | {ARCHITECTURE_MODE}\n"
        f"Capital={rules.reference_capital:.0f}$ min_trade={rules.min_trade_notional:.0f}$ "
        f"CB_max_losses={CIRCUIT_BREAKER_MAX_LOSSES} frames={','.join(ENTERPRISE_TIMEFRAMES)}"
    )


def _stage(name: str, approved: bool, reason: str = "", **detail: Any) -> PipelineStageResult:
    return PipelineStageResult(stage=name, approved=approved, reason=reason, detail=detail)


def run_pre_execution_pipeline(
    *,
    symbol: str,
    signal: str,
    score: int | float,
    price: float,
    reasons: tuple[str, ...] | list[str] | None = None,
    consecutive_losses: int = 0,
    consensus_approved: bool = True,
    risk_approved: bool = True,
    halted: bool = False,
    for_auto_open: bool = True,
) -> PipelineVerdict:
    """بوابة متسلسلة قبل التنفيذ التلقائي — طبقات مضافة فوق التحليل الحالي."""
    stages: list[PipelineStageResult] = []
    reasons_t = tuple(reasons or ())

    # 1) Sensing
    if price <= 0 or halted:
        s = _stage("sensing", False, "لا بيانات سعر أو السوق متوقف", price=price)
        stages.append(s)
        return PipelineVerdict(False, True, s.stage, s.reason, tuple(stages))
    stages.append(_stage("sensing", True, "نبض سعري صالح", price=price))

    # 2) Hierarchical SMC/ICT (يعتمد أسباب المحلل + أطر المؤسسة)
    tech_ok = signal in {"BUY SIGNAL", "SELL SIGNAL"}
    stages.append(
        _stage(
            "hierarchical_smc_ict",
            tech_ok,
            "إشارة فنية هرمية" if tech_ok else "لا إعداد SMC/ICT مكتمل",
            frames=ENTERPRISE_TIMEFRAMES,
            reasons_n=len(reasons_t),
        )
    )
    if not tech_ok:
        return PipelineVerdict(False, False, "hierarchical_smc_ict", stages[-1].reason, tuple(stages))

    # 3) Whale / Trap hunting
    try:
        from core.trap_hunting import evaluate_trap_hunt

        trap = evaluate_trap_hunt(symbol=symbol, signal=signal, reasons=reasons_t)
        stages.append(
            _stage("whale_trap_hunting", trap.approved, trap.reason, trap_type=trap.trap_type)
        )
        if not trap.approved:
            return PipelineVerdict(False, True, "whale_trap_hunting", trap.reason, tuple(stages), "none")
    except Exception as exc:  # noqa: BLE001
        logger.warning("trap hunting layer: %s", exc)
        stages.append(_stage("whale_trap_hunting", True, f"تخطي آمن: {exc}"))

    # 4) Noise filter (تذبذب / جودة ضعيفة من الأسباب)
    noise_hits = [
        r
        for r in reasons_t
        if any(k in str(r).lower() for k in ("noise", "spread", "chop", "ضوضاء", "تذبذب", "اتساع"))
    ]
    noise_ok = len(noise_hits) == 0
    stages.append(
        _stage(
            "noise_filter",
            noise_ok,
            "ضوضاء مرتفعة" if not noise_ok else "فلتر ضوضاء نظيف",
            hits=noise_hits[:3],
        )
    )
    if not noise_ok:
        return PipelineVerdict(False, True, "noise_filter", stages[-1].reason, tuple(stages))

    # 5) Audit + Circuit Breaker + Veto
    try:
        from risk.enterprise_circuit_breaker import evaluate_circuit_breaker

        cb = evaluate_circuit_breaker(consecutive_losses=consecutive_losses)
        audit_ok = bool(consensus_approved) and bool(risk_approved) and bool(cb.approved)
        reason = (
            cb.reason
            if not cb.approved
            else (
                "نقض ظل" if not consensus_approved else ("نقض مخاطر" if not risk_approved else "تدقيق+CB موافق")
            )
        )
        stages.append(
            _stage(
                "audit_circuit_veto",
                audit_ok,
                reason,
                veto=not audit_ok,
                consecutive_losses=consecutive_losses,
            )
        )
        if not audit_ok:
            return PipelineVerdict(False, True, "audit_circuit_veto", reason, tuple(stages))
    except Exception as exc:  # noqa: BLE001
        logger.warning("circuit breaker layer: %s", exc)
        if not (consensus_approved and risk_approved):
            s = _stage("audit_circuit_veto", False, "نقض تدقيق/مخاطر")
            stages.append(s)
            return PipelineVerdict(False, True, s.stage, s.reason, tuple(stages))
        stages.append(_stage("audit_circuit_veto", True, f"CB تخطي آمن: {exc}"))

    # 6) Hybrid execution gate
    label = hybrid_entry_label(score)
    if for_auto_open:
        auto_ok = is_hybrid_auto_score(score)
        stages.append(
            _stage(
                "hybrid_execution_gate",
                auto_ok,
                label if auto_ok else f"التلقائي يتطلب ≥90٪ — {label}",
                mode="auto" if auto_ok else "blocked",
            )
        )
        if not auto_ok:
            mode = "manual_broadcast" if is_hybrid_manual_broadcast_score(score) else "none"
            return PipelineVerdict(False, False, "hybrid_execution_gate", stages[-1].reason, tuple(stages), mode)
        entry_mode = "auto"
    else:
        man_ok = is_hybrid_manual_broadcast_score(score) or is_hybrid_auto_score(score)
        stages.append(_stage("hybrid_execution_gate", man_ok, label, mode="manual"))
        entry_mode = "manual_broadcast" if man_ok else "none"
        if not man_ok:
            return PipelineVerdict(False, False, "hybrid_execution_gate", label, tuple(stages), entry_mode)

    # 7) Risk sizing marker (الحساب الفعلي في project_rules / executor)
    rules = load_project_rules()
    stages.append(
        _stage(
            "risk_sizing",
            True,
            f"مرجع {rules.reference_capital:.0f}$ / حد {rules.min_trade_notional:.0f}$",
        )
    )

    # 8) Field / SSoT / Telegram marker
    stages.append(
        _stage(
            "field_ssot_telegram",
            True,
            "ميدان التنفيذ + SSoT + تيليجرام بعد الفتح",
        )
    )

    return PipelineVerdict(
        True,
        False,
        "field_ssot_telegram",
        "PIPELINE_OK",
        tuple(stages),
        entry_mode,
    )
