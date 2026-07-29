from dataclasses import dataclass


@dataclass(frozen=True)
class Ticker:
    symbol: str
    last: float
    bid: float | None
    ask: float | None
    spread: float | None
    spread_pct: float | None
    timestamp: int | None

    @classmethod
    def from_ccxt(cls, symbol: str, raw: dict) -> "Ticker":
        last = float(raw.get("last") or 0)
        bid = raw.get("bid")
        ask = raw.get("ask")
        bid_f = float(bid) if bid is not None else None
        ask_f = float(ask) if ask is not None else None

        spread = None
        spread_pct = None
        if bid_f is not None and ask_f is not None and ask_f > 0:
            spread = ask_f - bid_f
            spread_pct = (spread / ask_f) * 100

        timestamp = raw.get("timestamp")
        return cls(
            symbol=symbol,
            last=last,
            bid=bid_f,
            ask=ask_f,
            spread=spread,
            spread_pct=spread_pct,
            timestamp=int(timestamp) if timestamp is not None else None,
        )
