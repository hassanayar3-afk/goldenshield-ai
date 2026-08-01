"""إعدادات الركائز المعرفية — defaults آمنة عبر env."""

from __future__ import annotations

import os


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def shadow_stress_enabled() -> bool:
    return _bool("SHADOW_STRESS_ENABLED", True)


def shadow_watch_minutes() -> int:
    return max(1, _int("SHADOW_WATCH_MINUTES", 15))


def shadow_min_percent() -> int:
    return max(75, _int("SHADOW_MIN_PERCENT", 90))


def trap_fail_streak() -> int:
    return max(1, _int("TRAP_FAIL_STREAK", 3))


def trap_cooldown_minutes() -> int:
    return max(1, _int("TRAP_COOLDOWN_MINUTES", 60))


def orderbook_imbalance_enabled() -> bool:
    return _bool("ORDERBOOK_IMBALANCE_GATE_ENABLED", True)


def orderbook_imbalance_min() -> float:
    """حد أدنى |imbalance| لصالح اتجاه الصفقة (0–1)."""
    return min(0.95, max(0.0, _float("ORDERBOOK_IMBALANCE_MIN", 0.15)))


def adaptive_weights_enabled() -> bool:
    return _bool("ADAPTIVE_WEIGHTS_ENABLED", True)


def adaptive_weight_max_delta() -> float:
    return min(0.5, max(0.05, _float("ADAPTIVE_WEIGHT_MAX_DELTA", 0.20)))


def momentum_preemptive_exit_enabled() -> bool:
    return _bool("MOMENTUM_PREEMPTIVE_EXIT_ENABLED", False)


def risk_committee_enabled() -> bool:
    return _bool("RISK_COMMITTEE_ENABLED", True)


def risk_committee_llm_enabled() -> bool:
    return _bool("RISK_COMMITTEE_LLM_ENABLED", False)


def risk_committee_fail_closed() -> bool:
    return _bool("RISK_COMMITTEE_FAIL_CLOSED", False)


def macro_flow_gate_enabled() -> bool:
    return _bool("MACRO_FLOW_GATE_ENABLED", True)
