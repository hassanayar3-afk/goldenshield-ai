#!/usr/bin/env python3
"""E2E Smoke — دورة Tri-Commander واحدة (محلي، paper، بدون Binance حي)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("GOLDENSHIELD_OFFICIAL_ROOT", str(ROOT))
os.environ.setdefault("ENV", "dev")
os.environ.setdefault("EXECUTION_MODE", "paper")
os.environ.setdefault("TRI_COMMANDER_MODE", "true")
os.environ.setdefault("BINANCE_DEMO_TRADING", "false")
os.environ.setdefault("TELEGRAM_MUTE_ALL", "true")

# تحميل config/tri_commander_smoke.env
_smoke_env = ROOT / "config" / "tri_commander_smoke.env"
if _smoke_env.is_file():
    for line in _smoke_env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and key not in os.environ:
            os.environ[key] = value
if not os.environ.get("GOLDENSHIELD_OFFICIAL_ROOT"):
    os.environ["GOLDENSHIELD_OFFICIAL_ROOT"] = str(ROOT)


@dataclass(frozen=True)
class _FakeProposal:
    commander: str
    symbol: str
    side: str
    price: float
    score: int
    signal: str
    reasons: tuple[str, ...]
    passed: bool = True


def _fake_proposal(symbol: str, commander: str, score: int = 9) -> _FakeProposal:
    return _FakeProposal(
        commander=commander,
        symbol=symbol,
        side="buy",
        price=100.0,
        score=score,
        signal="BUY SIGNAL",
        reasons=(f"smoke:{commander}",),
        passed=True,
    )


async def _legacy_check(symbol: str, **kwargs) -> dict:
    commander = str(kwargs.get("commander") or "smoke")
    return {
        "symbol": symbol,
        "price": 100.0,
        "score": 9,
        "signal": "BUY SIGNAL",
        "reasons": (f"legacy_ok:{commander}",),
        "premium": True,
        "passed": True,
        "commander": commander,
    }


async def run_smoke() -> dict:
    from config.settings import load_settings

    load_settings("dev", reload=True)

    from execution.trade_executor import TradeExecutor
    from risk.risk_orchestrator import RiskOrchestrator
    from terminal.flash_crash_switch import FlashCrashDecision
    from terminal.orchestrator import run_tri_commander_cycle

    risk = RiskOrchestrator()
    risk.initialize(10_000.0)
    executor = TradeExecutor(risk_orchestrator=risk)

    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

    def _micro(self, symbol: str):
        return _fake_proposal(symbol, "micro_momentum", 9)

    def _flash(self, symbol: str):
        return None

    def _smc(self, symbol: str):
        return None

    with patch(
        "engines.micro_momentum.engine.MicroMomentumEngine.evaluate", _micro
    ), patch("gold_flash.core.GoldFlashEngine.evaluate", _flash), patch(
        "engines.smc_macro.engine.SMCMacroEngine.evaluate", _smc
    ), patch(
        "terminal.flash_crash_switch.evaluate_btc_flash_crash",
        lambda: FlashCrashDecision(False, "smoke_ok"),
    ):
        entries = await run_tri_commander_cycle(
            symbols,
            executor=executor,
            check_symbol_legacy=_legacy_check,
        )

    report = {
        "symbols": symbols,
        "entries": [e for e in entries if e],
        "entry_count": sum(1 for e in entries if e),
        "passed_count": sum(1 for e in entries if e and e.get("passed")),
    }
    return report


def main() -> int:
    try:
        report = asyncio.run(run_smoke())
        out_path = ROOT / "storage" / "runtime" / "tri_commander_smoke.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if report["passed_count"] < 1:
            print("TRI_SMOKE_FAIL: no passed entries", report, file=sys.stderr)
            return 1
        print(
            f"TRI_SMOKE_OK entries={report['entry_count']} passed={report['passed_count']} "
            f"artifact={out_path}"
        )
        return 0
    except Exception as exc:
        print(f"TRI_SMOKE_FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
