"""منسّق القادة الثلاثة — Zero Cross-Contamination."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from engines.micro_momentum.engine import MicroMomentumEngine
from engines.smc_macro.engine import SMCMacroEngine
from gold_flash.core import GoldFlashEngine
from terminal.dispatcher import evaluate_dispatch
from terminal.flash_crash_switch import evaluate_btc_flash_crash

if TYPE_CHECKING:
    from execution.trade_executor import TradeExecutor

logger = logging.getLogger(__name__)

_smc = SMCMacroEngine()
_flash = GoldFlashEngine()
_micro = MicroMomentumEngine()


async def run_tri_commander_cycle(
    symbols: list[str],
    *,
    executor: TradeExecutor,
    check_symbol_legacy,
) -> list[dict | None]:
    """يشغّل القادة معزولين ثم ينفّذ عبر مسار main.check_symbol عند الموافقة."""
    crash = evaluate_btc_flash_crash()
    if crash.block_entries:
        logger.warning(crash.reason)
        return [None for _ in symbols]

    proposals = []
    for sym in symbols:
        for engine in (_micro, _flash, _smc):
            prop = engine.evaluate(sym)
            if prop is not None:
                proposals.append((sym, prop))
                break

    results_map: dict[str, dict | None] = {s: None for s in symbols}

    balance = executor.get_account_balance()
    positions = executor.position_manager.all()

    for sym, prop in proposals:
        disp = evaluate_dispatch(prop, open_positions=positions, balance=balance)
        if not disp.approved:
            logger.info("%s: %s", sym, disp.reason)
            results_map[sym] = {
                "symbol": sym,
                "price": prop.price,
                "score": prop.score,
                "signal": prop.signal,
                "reasons": prop.reasons + (disp.reason,),
                "premium": False,
                "passed": False,
            }
            continue
        entry = await check_symbol_legacy(
            sym,
            commander=prop.commander,
            risk_pct=disp.risk_pct,
            engine_proposal=prop,
        )
        if entry is not None:
            results_map[sym] = entry
            positions = executor.position_manager.all()

    return [results_map.get(s) for s in symbols]
