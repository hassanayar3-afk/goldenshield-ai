from dataclasses import dataclass


@dataclass(frozen=True)
class OrderBookLevel:
    price: float
    amount: float


@dataclass(frozen=True)
class OrderBook:
    symbol: str
    bids: tuple[OrderBookLevel, ...]
    asks: tuple[OrderBookLevel, ...]
    timestamp: int | None

    @classmethod
    def from_ccxt(cls, symbol: str, raw: dict, *, depth: int = 20) -> "OrderBook":
        bids = tuple(
            OrderBookLevel(price=float(price), amount=float(amount))
            for price, amount in raw.get("bids", [])[:depth]
        )
        asks = tuple(
            OrderBookLevel(price=float(price), amount=float(amount))
            for price, amount in raw.get("asks", [])[:depth]
        )
        timestamp = raw.get("timestamp")
        return cls(
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=int(timestamp) if timestamp is not None else None,
        )

    @property
    def bid_volume(self) -> float:
        return sum(level.amount for level in self.bids)

    @property
    def ask_volume(self) -> float:
        return sum(level.amount for level in self.asks)
