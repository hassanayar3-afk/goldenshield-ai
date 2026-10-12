"""منسّق GoldenShield Terminal — القادة الثلاثة بلا تلوث تحليلي."""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from engines.micro_momentum.engine import MicroMomentumEngine
from engines.smc_macro.engine import SMCMacroEngine
from execution.trade_executor import TradeExecutor
from gold_flash.core import GoldFlashEngine
from terminal.dispatcher import (
    CommanderProposalLike,
    DispatchDecision,
    DispatchStage,
    evaluate_dispatch,
)
from terminal.daily_reset import maybe_run_daily_reset
from terminal.flash_crash_switch import evaluate_btc_flash_crash
from terminal.module_breaker import is_module_halted
from terminal.scoring import confidence_percent

logger = logging.getLogger(__name__)

CheckSymbolCallable = Callable[..., Awaitable[dict[str, Any] | None]]

ENGINE_ORDER: tuple[str, ...] = (
    "micro_momentum",
    "gold_flash",
    "smc_macro",
)


@dataclass
class OrchestratorCycleStats:
    symbols_total: int
    proposals: int
    dispatched: int
    rejected: int
    executed_entries: int
    flash_crash_blocked: bool


@dataclass
class TriCommanderOrchestrator:
    micro_engine: MicroMomentumEngine
    flash_engine: GoldFlashEngine
    smc_engine: SMCMacroEngine

    @classmethod
    def create_default(cls) -> TriCommanderOrchestrator:
        return cls(
            micro_engine=MicroMomentumEngine(),
            flash_engine=GoldFlashEngine(),
            smc_engine=SMCMacroEngine(),
        )

    def _engine_evaluators(self) -> tuple[tuple[str, Any], ...]:
        return (
            ("micro_momentum", self.micro_engine),
            ("gold_flash", self.flash_engine),
            ("smc_macro", self.smc_engine),
        )

    def _evaluate_symbol_isolated(self, symbol: str) -> CommanderProposalLike | None:
        for commander_id, engine in self._engine_evaluators():
            if is_module_halted(commander_id):
                logger.debug("commander halted: %s", commander_id)
                continue
            try:
                proposal = engine.evaluate(symbol)
            except Exception as exc:  # noqa: BLE001
                logger.warning("engine %s failed on %s: %s", commander_id, symbol, exc)
                continue
            if proposal is not None:
                if str(getattr(proposal, "commander", "")) != commander_id:
                    logger.warning(
                        "commander mismatch %s vs %s — skip",
                        getattr(proposal, "commander", ""),
                        commander_id,
                    )
                    continue
                return proposal
        return None

    def collect_proposals(
        self,
        symbols: list[str],
    ) -> list[tuple[str, CommanderProposalLike]]:
        collected: list[tuple[str, CommanderProposalLike]] = []
        for symbol in symbols:
            proposal = self._evaluate_symbol_isolated(symbol)
            if proposal is not None:
                collected.append((symbol, proposal))
        collected.sort(
            key=lambda item: confidence_percent(item[1].score),
            reverse=True,
        )
        return collected

    @staticmethod
    def _rejection_entry(
        symbol: str,
        proposal: CommanderProposalLike,
        decision: DispatchDecision,
    ) -> dict[str, Any]:
        reasons = tuple(proposal.reasons) + (decision.reason,)
        return {
            "symbol": symbol,
            "price": float(proposal.price),
            "score": int(proposal.score),
            "signal": str(proposal.signal),
            "reasons": reasons,
            "premium": False,
            "passed": False,
            "commander": str(proposal.commander),
            "dispatch_stage": decision.stage.value,
        }

    @staticmethod
    def _flash_crash_wait_entry(symbol: str, reason: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "price": 0.0,
            "score": 0,
            "signal": "WAIT",
            "reasons": (reason,),
            "premium": False,
            "passed": False,
            "commander": "",
            "dispatch_stage": "flash_crash",
        }

    async def run_cycle(
        self,
        symbols: list[str],
        *,
        executor: TradeExecutor,
        check_symbol_legacy: CheckSymbolCallable,
    ) -> tuple[list[dict[str, Any] | None], OrchestratorCycleStats]:
        results_map: dict[str, dict[str, Any] | None] = {s: None for s in symbols}
        stats = OrchestratorCycleStats(
            symbols_total=len(symbols),
            proposals=0,
            dispatched=0,
            rejected=0,
            executed_entries=0,
            flash_crash_blocked=False,
        )

        try:
            maybe_run_daily_reset()
        except Exception as exc:  # noqa: BLE001
            logger.debug("daily_reset: %s", exc)

        crash = evaluate_btc_flash_crash()
        if crash.block_entries:
            stats.flash_crash_blocked = True
            logger.warning("Flash Crash Switch: %s", crash.reason)
            for symbol in symbols:
                results_map[symbol] = self._flash_crash_wait_entry(symbol, crash.reason)
            return [results_map.get(s) for s in symbols], stats

        proposals = self.collect_proposals(symbols)
        stats.proposals = len(proposals)

        balance = float(executor.get_account_balance())
        positions = list(executor.position_manager.all())

        for symbol, proposal in proposals:
            decision = evaluate_dispatch(
                proposal,
                open_positions=positions,
                balance=balance,
            )
            if not decision.approved:
                stats.rejected += 1
                results_map[symbol] = self._rejection_entry(symbol, proposal, decision)
                logger.info(
                    "%s [%s] rejected at %s: %s",
                    symbol,
                    proposal.commander,
                    decision.stage.value,
                    decision.reason,
                )
                continue

            stats.dispatched += 1
            try:
                entry = await check_symbol_legacy(
                    symbol,
                    commander=str(proposal.commander),
                    risk_pct=float(decision.risk_pct),
                    engine_proposal=proposal,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("check_symbol failed %s: %s", symbol, exc)
                entry = self._rejection_entry(
                    symbol,
                    proposal,
                    DispatchDecision(
                        False,
                        f"execution bridge error: {exc}",
                        DispatchStage.EXECUTION_BRIDGE,
                        risk_pct=decision.risk_pct,
                        confidence_pct=decision.confidence_pct,
                    ),
                )
                stats.rejected += 1

            if entry is not None:
                results_map[symbol] = entry
                if bool(entry.get("passed")) or bool(entry.get("premium")):
                    stats.executed_entries += 1
                positions = list(executor.position_manager.all())
                balance = float(executor.get_account_balance())

        return [results_map.get(s) for s in symbols], stats


_default_orchestrator: TriCommanderOrchestrator | None = None


def get_orchestrator() -> TriCommanderOrchestrator:
    global _default_orchestrator
    if _default_orchestrator is None:
        _default_orchestrator = TriCommanderOrchestrator.create_default()
    return _default_orchestrator


def tri_commander_enabled() -> bool:
    raw = (os.getenv("TRI_COMMANDER_MODE", "true") or "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


async def run_tri_commander_cycle(
    symbols: list[str],
    *,
    executor: TradeExecutor,
    check_symbol_legacy: CheckSymbolCallable,
) -> list[dict[str, Any] | None]:
    orchestrator = get_orchestrator()
    entries, stats = await orchestrator.run_cycle(
        symbols,
        executor=executor,
        check_symbol_legacy=check_symbol_legacy,
    )
    if stats.proposals or stats.rejected or stats.executed_entries:
        logger.info(
            "TriCommander cycle: proposals=%s dispatched=%s rejected=%s executed=%s crash=%s",
            stats.proposals,
            stats.dispatched,
            stats.rejected,
            stats.executed_entries,
            stats.flash_crash_blocked,
        )
    return entries
