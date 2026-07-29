"""بوابة التوافق — لا تنفيذ بدون consensus."""

from __future__ import annotations

from dataclasses import dataclass

from audit.shadow_executor import ShadowResult


@dataclass(frozen=True)
class ConsensusResult:
    approved: bool
    reason: str
    shadow: ShadowResult


def check_consensus(shadow: ShadowResult) -> ConsensusResult:
    if shadow.consensus:
        return ConsensusResult(
            approved=True,
            reason="توافق Shadow: فني ≥75% + سيولة",
            shadow=shadow,
        )

    failures = []
    if not shadow.technical.approved:
        failures.append(shadow.technical.reason)
    if not shadow.liquidity.approved:
        failures.append(shadow.liquidity.reason)

    return ConsensusResult(
        approved=False,
        reason=" | ".join(failures),
        shadow=shadow,
    )
