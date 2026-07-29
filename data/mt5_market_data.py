"""بيانات السوق من MT5 — للفوركس والرموز غير المتوفرة على Binance."""

from __future__ import annotations

from data.models.candle import Candle
from data.models.ticker import Ticker

_TF_MAP = {
    "15m": "M15",
    "1h": "H1",
    "4h": "H4",
    "1d": "D1",
}


def fetch_mt5_ohlcv(symbol_id: str, timeframe: str, *, limit: int) -> list[Candle]:
    from execution.mt5_bridge import get_mt5_bridge

    bridge = get_mt5_bridge()
    mt5 = bridge.ensure_connected()
    resolved = bridge.resolve_symbol(symbol_id)
    tf_name = _TF_MAP.get(timeframe)
    if tf_name is None:
        raise ValueError(f"إطار MT5 غير مدعوم: {timeframe}")
    tf = getattr(mt5, f"TIMEFRAME_{tf_name}")
    rates = mt5.copy_rates_from_pos(resolved, tf, 0, limit)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"لا بيانات MT5 لـ {resolved} ({timeframe})")
    candles: list[Candle] = []
    for row in rates:
        candles.append(
            Candle(
                timestamp=int(row["time"]) * 1000,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["tick_volume"]),
            )
        )
    return candles


def fetch_mt5_ticker(symbol_id: str) -> Ticker:
    from execution.mt5_bridge import get_mt5_bridge

    bridge = get_mt5_bridge()
    mt5 = bridge.ensure_connected()
    resolved = bridge.resolve_symbol(symbol_id)
    tick = mt5.symbol_info_tick(resolved)
    if tick is None:
        raise RuntimeError(f"لا سعر MT5 لـ {resolved}")
    bid = float(tick.bid)
    ask = float(tick.ask)
    last = (bid + ask) / 2 if bid and ask else float(tick.last or ask or bid)
    return Ticker(
        symbol=symbol_id,
        last=last,
        bid=bid,
        ask=ask,
        spread=abs(ask - bid) if bid and ask else 0.0,
        spread_pct=((abs(ask - bid) / ask) * 100.0) if bid and ask and ask > 0 else 0.0,
        timestamp=None,
    )
