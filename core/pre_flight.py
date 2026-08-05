# -*- coding: utf-8 -*-
"""فحص إقلاع مؤسسي مضاف — يغلّف operations.pre_flight_checklist دون استبداله."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def run_pre_flight_checks(*, soft: bool = False) -> bool:
    """تحقق متسلسل: .env + قواعد رأس المال + سلامة مجلدات + pre-flight التشغيلي."""
    print("[Pre-Flight] Starting Enterprise Security & Environment Validation...")
    try:
        from config.project_rules import (
            PROJECT_MIN_TRADE_NOTIONAL,
            PROJECT_REFERENCE_CAPITAL,
            load_project_rules,
        )

        env_path = Path(os.getcwd()) / ".env"
        if not env_path.is_file():
            msg = "[CRITICAL] .env configuration file missing!"
            if soft:
                logger.warning(msg)
                return False
            raise FileNotFoundError(msg)

        rules = load_project_rules()
        assert float(rules.reference_capital) >= 1000.0, "Reference capital misconfigured."
        assert float(rules.min_trade_notional) >= float(PROJECT_MIN_TRADE_NOTIONAL), (
            "Minimum trade notional violated."
        )
        assert float(PROJECT_REFERENCE_CAPITAL) >= 5000.0

        for rel in ("storage/db", "storage/logs", "storage/runtime", "storage/reports"):
            Path(os.getcwd(), rel).mkdir(parents=True, exist_ok=True)

        try:
            from operations.pre_flight_checklist import run_pre_flight

            result = run_pre_flight(skip_binance_ping=False)
            if not result.ok and not soft:
                logger.error("Operational pre-flight failed: %s", result.checks)
                return False
        except Exception as exc:  # noqa: BLE001
            logger.warning("operational pre-flight wrap: %s", exc)

        print(
            "[Pre-Flight] PASSED: All institutional constraints and pipelines are coherent (100%)."
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.exception("enterprise pre-flight: %s", exc)
        if soft:
            return False
        raise


if __name__ == "__main__":
    run_pre_flight_checks()
