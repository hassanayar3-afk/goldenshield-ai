"""إغلاق طارئ عند انقطاع Heartbeat > 30 ثانية."""

from __future__ import annotations

from dataclasses import dataclass

from data.connection_monitor import ConnectionMonitor


@dataclass(frozen=True)
class HeartbeatGuardResult:
    safe: bool
    should_emergency_flat: bool
    reason: str


def check_heartbeat_guard(monitor: ConnectionMonitor) -> HeartbeatGuardResult:
    if monitor.is_disconnected():
        elapsed = monitor.seconds_since_last_success()
        seconds = f"{elapsed:.0f}" if elapsed is not None else "?"
        return HeartbeatGuardResult(
            safe=False,
            should_emergency_flat=True,
            reason=f"انقطاع Heartbeat > {monitor.timeout_seconds}s ({seconds}s)",
        )

    return HeartbeatGuardResult(
        safe=True,
        should_emergency_flat=False,
        reason="Heartbeat سليم",
    )
