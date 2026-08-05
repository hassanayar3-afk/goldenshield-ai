# -*- coding: utf-8 -*-
"""Micro-structure sensing — Iceberg / Delta تقريبي من دفتر الأوامر (طبقة مضافة)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MicroStructureSnapshot:
    ok: bool
    bid_wall: float = 0.0
    ask_wall: float = 0.0
    delta_proxy: float = 0.0
    iceberg_suspect: bool = False
    spoof_suspect: bool = False
    reason: str = ""


def analyze_orderbook_micro(
    orderbook: dict[str, Any] | None,
    *,
    wall_multiple: float = 3.0,
) -> MicroStructureSnapshot:
    """تحليل خفيف لجدران الطلبات ودلتا تقريبية بدون WebSocket إلزامي."""
    try:
        if not orderbook:
            return MicroStructureSnapshot(True, reason="لا دفتر — تخطي آمن")
        bids = orderbook.get("bids") or orderbook.get("bid") or []
        asks = orderbook.get("asks") or orderbook.get("ask") or []
        if not bids or not asks:
            return MicroStructureSnapshot(True, reason="دفتر فارغ — تخطي")

        def _sz(level: Any) -> float:
            try:
                if isinstance(level, (list, tuple)) and len(level) >= 2:
                    return float(level[1])
                if isinstance(level, dict):
                    return float(level.get("qty") or level.get("amount") or 0)
            except (TypeError, ValueError):
                return 0.0
            return 0.0

        bid_sizes = [_sz(x) for x in list(bids)[:20]]
        ask_sizes = [_sz(x) for x in list(asks)[:20]]
        bid_wall = max(bid_sizes) if bid_sizes else 0.0
        ask_wall = max(ask_sizes) if ask_sizes else 0.0
        avg_bid = (sum(bid_sizes) / len(bid_sizes)) if bid_sizes else 0.0
        avg_ask = (sum(ask_sizes) / len(ask_sizes)) if ask_sizes else 0.0
        delta = sum(bid_sizes) - sum(ask_sizes)
        iceberg = (
            (avg_bid > 0 and bid_wall >= wall_multiple * avg_bid)
            or (avg_ask > 0 and ask_wall >= wall_multiple * avg_ask)
        )
        # spoof تقريبي: جدار ضخم مع عدم توازن حاد
        spoof = iceberg and abs(delta) > (sum(bid_sizes) + sum(ask_sizes)) * 0.35
        return MicroStructureSnapshot(
            ok=True,
            bid_wall=bid_wall,
            ask_wall=ask_wall,
            delta_proxy=delta,
            iceberg_suspect=bool(iceberg),
            spoof_suspect=bool(spoof),
            reason="micro-ok",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("analyze_orderbook_micro: %s", exc)
        return MicroStructureSnapshot(True, reason=f"bypass: {exc}")
