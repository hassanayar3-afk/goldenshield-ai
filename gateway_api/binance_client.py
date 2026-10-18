"""
Binance REST abstraction: jittered exponential backoff, circuit breaker,
Min Notional / spread guards, paper execution with optional live market reads.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import aiohttp

from data_highway.logging_config import setup_logger

logger = setup_logger("saqr.binance")


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _resolve_paper_trading() -> bool:
    """Local simulated fills only when PAPER_TRADING=true or EXECUTION_MODE=paper."""
    if _env_bool("PAPER_TRADING", False):
        return True
    mode = os.getenv("EXECUTION_MODE", "paper").strip().lower()
    return mode == "paper"


def _resolve_market_rest_url(base_url: str) -> str:
    explicit = os.getenv("BINANCE_MARKET_REST_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    base = base_url.rstrip("/")
    low = base.lower()
    if "testnet.binancefuture.com" in low or "fapi" in low or "binancefuture" in low:
        if "testnet" in low:
            return "https://testnet.binancefuture.com"
        return "https://fapi.binance.com"
    return os.getenv("BINANCE_MARKET_REST_URL", "https://api.binance.com").strip() or "https://api.binance.com"


@dataclass
class SymbolRules:
    min_notional: float = 5.0
    min_qty: float = 0.001
    step_size: float = 0.001
    tick_size: float = 0.01


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    failures: int = 0
    opened_at: Optional[float] = None

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        if time.monotonic() - self.opened_at >= self.recovery_timeout:
            self.opened_at = None
            self.failures = 0
            return True
        return False

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = time.monotonic()
            logger.warning("Binance circuit breaker OPEN (%s failures)", self.failures)


@dataclass
class BinanceClient:
    api_key: str = field(default_factory=lambda: os.getenv("BINANCE_API_KEY", ""))
    api_secret: str = field(default_factory=lambda: os.getenv("BINANCE_API_SECRET", ""))
    base_url: str = field(
        default_factory=lambda: os.getenv("BINANCE_BASE_URL", "https://testnet.binancefuture.com")
    )
    market_rest_url: str = field(
        default_factory=lambda: _resolve_market_rest_url(
            os.getenv("BINANCE_BASE_URL", "https://testnet.binancefuture.com")
        )
    )
    user_ws_base: str = field(
        default_factory=lambda: os.getenv("BINANCE_USER_WS_BASE", "wss://fstream.binance.com/ws").rstrip("/")
    )
    execution_mode: str = field(
        default_factory=lambda: os.getenv("EXECUTION_MODE", "paper").strip().lower()
    )
    paper_trading: bool = field(default_factory=_resolve_paper_trading)
    max_retries: int = 5
    base_backoff: float = 0.5
    _session: Optional[aiohttp.ClientSession] = field(default=None, init=False, repr=False)
    _breaker: CircuitBreaker = field(default_factory=CircuitBreaker, init=False)
    _rules_cache: Dict[str, SymbolRules] = field(default_factory=dict, init=False)

    @property
    def is_futures(self) -> bool:
        u = self.base_url.lower()
        return "fapi" in u or "binancefuture" in u or "fstream" in self.user_ws_base.lower()

    def _market_path(self, spot_path: str, futures_path: str) -> str:
        return futures_path if self.is_futures else spot_path

    def _api_path(self, spot: str, futures: str) -> str:
        return futures if self.is_futures else spot

    async def start(self) -> None:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _sleep_backoff(self, attempt: int) -> None:
        jitter = random.uniform(0, self.base_backoff)
        delay = min(self.base_backoff * (2**attempt) + jitter, 30.0)
        await asyncio.sleep(delay)

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        params = dict(params)
        params.setdefault("timestamp", int(time.time() * 1000))
        query = urlencode(params, True)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    async def _request_url(
        self,
        base: str,
        method: str,
        path: str,
        *,
        signed: bool = False,
        params: Optional[Dict[str, Any]] = None,
        use_breaker: bool = True,
        max_retries: Optional[int] = None,
    ) -> Any:
        if use_breaker and not self._breaker.allow():
            raise RuntimeError("Binance circuit breaker is open")

        await self.start()
        assert self._session is not None
        params = params or {}
        headers = {"X-MBX-APIKEY": self.api_key} if signed else {}
        attempts = max_retries if max_retries is not None else self.max_retries

        last_error: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                req_params = self._sign(params) if signed else params
                url = f"{base.rstrip('/')}{path}"
                async with self._session.request(
                    method, url, params=req_params, headers=headers
                ) as resp:
                    body = await resp.json(content_type=None)
                    if resp.status >= 400:
                        logger.error(
                            "Binance rejected %s %s%s — HTTP %s: %s",
                            method,
                            base.rstrip("/"),
                            path,
                            resp.status,
                            body,
                        )
                        raise RuntimeError(f"HTTP {resp.status}: {body}")
                if use_breaker:
                    self._breaker.record_success()
                return body
            except Exception as exc:
                last_error = exc
                if use_breaker:
                    self._breaker.record_failure()
                logger.warning(
                    "Binance request failed (%s %s) attempt %s/%s: %s",
                    method,
                    path,
                    attempt + 1,
                    attempts,
                    exc,
                )
                if "HTTP 451" in str(exc):
                    break
                await self._sleep_backoff(attempt)

        raise RuntimeError(f"Binance request exhausted retries: {last_error}")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        signed: bool = False,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        return await self._request_url(
            self.base_url,
            method,
            path,
            signed=signed,
            params=params,
            use_breaker=True,
        )

    async def _market_request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Public market REST (live candles/book), independent of paper execution."""
        return await self._request_url(
            self.market_rest_url,
            method,
            path,
            signed=False,
            params=params,
            use_breaker=False,
            max_retries=2,
        )

    async def ping(self) -> bool:
        if self.paper_trading:
            return True
        try:
            await self._request("GET", self._api_path("/api/v3/ping", "/fapi/v1/ping"))
            logger.info(
                "Binance connected mode=%s futures=%s base=%s",
                self.execution_mode,
                self.is_futures,
                self.base_url,
            )
            return True
        except Exception as exc:
            logger.error("Binance ping failed (mode=%s): %s", self.execution_mode, exc)
            return False

    def _parse_rules(self, symbol_info: Dict[str, Any]) -> SymbolRules:
        rules = SymbolRules()
        for f in symbol_info.get("filters", []):
            ftype = f.get("filterType")
            if ftype in ("MIN_NOTIONAL", "NOTIONAL"):
                rules.min_notional = float(f.get("minNotional", f.get("notional", rules.min_notional)))
            elif ftype == "LOT_SIZE":
                rules.min_qty = float(f.get("minQty", rules.min_qty))
                rules.step_size = float(f.get("stepSize", rules.step_size))
            elif ftype == "PRICE_FILTER":
                rules.tick_size = float(f.get("tickSize", rules.tick_size))
        return rules

    async def get_symbol_rules(self, symbol: str) -> SymbolRules:
        symbol = symbol.upper()
        if symbol in self._rules_cache:
            return self._rules_cache[symbol]
        try:
            path = self._market_path("/api/v3/exchangeInfo", "/fapi/v1/exchangeInfo")
            info = await self._market_request("GET", path, params={"symbol": symbol})
            symbols = info.get("symbols") or []
            if symbols:
                rules = self._parse_rules(symbols[0])
                self._rules_cache[symbol] = rules
                return rules
        except Exception as exc:
            logger.warning("Live exchangeInfo failed for %s: %s — using defaults", symbol, exc)
        rules = SymbolRules()
        self._rules_cache[symbol] = rules
        return rules

    async def fetch_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 200,
    ) -> List[List[Any]]:
        """Public klines for stream warm-up (spot or futures REST from env)."""
        try:
            path = self._market_path("/api/v3/klines", "/fapi/v1/klines")
            data = await self._market_request(
                "GET",
                path,
                params={"symbol": symbol.upper(), "interval": interval, "limit": limit},
            )
            return list(data) if isinstance(data, list) else []
        except Exception as exc:
            logger.warning("fetch_klines failed %s %s: %s", symbol, interval, exc)
            return []

    async def fetch_book_ticker(self, symbol: str) -> Dict[str, float]:
        try:
            path = self._market_path("/api/v3/ticker/bookTicker", "/fapi/v1/ticker/bookTicker")
            data = await self._market_request(
                "GET",
                path,
                params={"symbol": symbol.upper()},
            )
            return {
                "bid": float(data.get("bidPrice", 0)),
                "ask": float(data.get("askPrice", 0)),
                "bid_qty": float(data.get("bidQty", 0)),
                "ask_qty": float(data.get("askQty", 0)),
            }
        except Exception as exc:
            logger.warning("bookTicker unavailable for %s: %s", symbol, exc)
            return {"bid": 0.0, "ask": 0.0, "bid_qty": 0.0, "ask_qty": 0.0}

    @staticmethod
    def spread_bps(bid: float, ask: float) -> float:
        if bid <= 0 or ask <= 0:
            return 9999.0
        mid = (bid + ask) / 2.0
        return ((ask - bid) / mid) * 10_000.0

    def _quantize_qty(self, qty: float, step: float) -> float:
        if step <= 0:
            return qty
        precision = max(0, len(str(step).split(".")[-1].rstrip("0")))
        steps = int(qty / step)
        return round(steps * step, precision)

    async def validate_order(
        self,
        symbol: str,
        quantity: float,
        price: float,
        *,
        spread_bps_override: Optional[float] = None,
    ) -> Tuple[bool, str, float]:
        """
        Returns (allowed, reason, adjusted_qty).
        """
        rules = await self.get_symbol_rules(symbol)
        qty = max(quantity, rules.min_qty)
        qty = self._quantize_qty(qty, rules.step_size)
        notional = qty * price
        if notional < rules.min_notional:
            return False, f"min_notional<{rules.min_notional}", qty

        max_spread = float(os.getenv("MAX_SPREAD_BPS", "15"))
        spread = spread_bps_override
        if spread is None:
            book = await self.fetch_book_ticker(symbol)
            spread = self.spread_bps(book["bid"], book["ask"])
        if spread > max_spread:
            return False, f"spread_bps={spread:.2f}>{max_spread}", qty

        return True, "ok", qty

    async def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
    ) -> Dict[str, Any]:
        if self.paper_trading:
            return {
                "symbol": symbol,
                "orderId": int(time.time()),
                "clientOrderId": f"paper_{uuid.uuid4().hex[:12]}",
                "status": "FILLED",
                "side": side,
                "type": "MARKET",
                "executedQty": str(quantity),
                "paper": True,
            }
        params = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": f"{quantity:.8f}".rstrip("0").rstrip("."),
        }
        return await self._request(
            "POST",
            self._api_path("/api/v3/order", "/fapi/v1/order"),
            signed=True,
            params=params,
        )

    async def place_market_guarded(
        self,
        symbol: str,
        side: str,
        quantity: float,
        reference_price: float,
        *,
        spread_bps_override: Optional[float] = None,
        stream: Optional[Any] = None,
        skip_advanced_guard: bool = False,
    ) -> Optional[Dict[str, Any]]:
        if stream is not None and not skip_advanced_guard:
            from risk_sentinel.spread_guard import advanced_pre_trade_check

            allowed, reason, qty = await advanced_pre_trade_check(
                self,
                stream,
                symbol,
                quantity,
                reference_price,
                spread_bps_override=spread_bps_override,
            )
        else:
            allowed, reason, qty = await self.validate_order(
                symbol,
                quantity,
                reference_price,
                spread_bps_override=spread_bps_override,
            )
        if not allowed:
            logger.info("Order blocked %s %s: %s", side, symbol, reason)
            return None
        return await self.place_market_order(symbol, side, qty)

    async def place_stop_market(
        self,
        symbol: str,
        side: str,
        stop_price: float,
        quantity: float,
        *,
        reference_price: float,
        spread_bps_override: Optional[float] = None,
        stream: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        if stream is not None:
            from risk_sentinel.spread_guard import advanced_pre_trade_check

            allowed, reason, qty = await advanced_pre_trade_check(
                self,
                stream,
                symbol,
                quantity,
                reference_price,
                spread_bps_override=spread_bps_override,
            )
        else:
            allowed, reason, qty = await self.validate_order(
                symbol,
                quantity,
                reference_price,
                spread_bps_override=spread_bps_override,
            )
        if not allowed:
            logger.info("STOP_MARKET blocked %s: %s", symbol, reason)
            return None

        client_id = f"saqr_stop_{uuid.uuid4().hex[:16]}"
        if self.paper_trading:
            return {
                "symbol": symbol,
                "clientOrderId": client_id,
                "type": "STOP_MARKET",
                "status": "NEW",
                "stopPrice": str(stop_price),
                "paper": True,
            }
        params = {
            "symbol": symbol,
            "side": side,
            "type": "STOP_MARKET",
            "stopPrice": f"{stop_price:.8f}".rstrip("0").rstrip("."),
            "quantity": f"{qty:.8f}".rstrip("0").rstrip("."),
            "newClientOrderId": client_id,
        }
        return await self._request(
            "POST",
            self._api_path("/api/v3/order", "/fapi/v1/order"),
            signed=True,
            params=params,
        )

    async def place_ioc_limit(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        *,
        spread_bps_override: Optional[float] = None,
        stream: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        if stream is not None:
            from risk_sentinel.spread_guard import advanced_pre_trade_check

            allowed, reason, qty = await advanced_pre_trade_check(
                self,
                stream,
                symbol,
                quantity,
                price,
                spread_bps_override=spread_bps_override,
            )
        else:
            allowed, reason, qty = await self.validate_order(
                symbol,
                quantity,
                price,
                spread_bps_override=spread_bps_override,
            )
        if not allowed:
            logger.info("IOC blocked %s %s: %s", side, symbol, reason)
            return None

        if self.paper_trading:
            return {
                "symbol": symbol,
                "status": "FILLED",
                "type": "LIMIT",
                "timeInForce": "IOC",
                "executedQty": str(qty),
                "paper": True,
            }
        params = {
            "symbol": symbol,
            "side": side,
            "type": "LIMIT",
            "timeInForce": "IOC",
            "quantity": f"{qty:.8f}".rstrip("0").rstrip("."),
            "price": f"{price:.8f}".rstrip("0").rstrip("."),
        }
        return await self._request(
            "POST",
            self._api_path("/api/v3/order", "/fapi/v1/order"),
            signed=True,
            params=params,
        )

    async def exchange_info(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol.upper()
        try:
            return await self._market_request("GET", "/api/v3/exchangeInfo", params=params or None)
        except Exception:
            filters = [
                {"filterType": "MIN_NOTIONAL", "minNotional": "5"},
                {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001"},
            ]
            return {
                "symbols": [
                    {
                        "symbol": symbol or "BTCUSDT",
                        "status": "TRADING",
                        "filters": filters,
                    }
                ]
            }

    async def account_balances(self) -> List[Dict[str, Any]]:
        if self.paper_trading:
            return [
                {"asset": "USDT", "free": "10000", "locked": "0"},
                {"asset": "BTC", "free": "0.05", "locked": "0"},
            ]
        path = self._api_path("/api/v3/account", "/fapi/v2/account")
        data = await self._request("GET", path, signed=True)
        if self.is_futures:
            assets = data.get("assets") or []
            return [
                {
                    "asset": a.get("asset"),
                    "free": a.get("availableBalance", "0"),
                    "locked": a.get("initialMargin", "0"),
                }
                for a in assets
            ]
        return list(data.get("balances", []))

    async def open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.paper_trading:
            return []
        params: Dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        path = self._api_path("/api/v3/openOrders", "/fapi/v1/openOrders")
        return await self._request("GET", path, signed=True, params=params)

    async def _listen_key_request(
        self,
        method: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """User data stream REST endpoints require API key header without signature."""
        await self.start()
        assert self._session is not None
        headers = {"X-MBX-APIKEY": self.api_key}
        listen_path = self._api_path("/api/v3/userDataStream", "/fapi/v1/listenKey")
        url = f"{self.base_url.rstrip('/')}{listen_path}"
        async with self._session.request(method, url, params=params or {}, headers=headers) as resp:
            body = await resp.json(content_type=None)
            if resp.status >= 400:
                raise RuntimeError(f"HTTP {resp.status}: {body}")
        return body

    async def create_listen_key(self) -> str:
        if self.paper_trading or not self.api_key:
            return f"paper_listen_{uuid.uuid4().hex[:24]}"
        data = await self._listen_key_request("POST")
        key = str(data.get("listenKey", ""))
        if not key:
            raise RuntimeError("Binance did not return listenKey")
        return key

    async def keepalive_listen_key(self, listen_key: str) -> None:
        if self.paper_trading or listen_key.startswith("paper_listen_"):
            return
        await self._listen_key_request("PUT", params={"listenKey": listen_key})

    async def close_listen_key(self, listen_key: str) -> None:
        if self.paper_trading or listen_key.startswith("paper_listen_"):
            return
        await self._listen_key_request("DELETE", params={"listenKey": listen_key})

    def user_stream_url(self, listen_key: str) -> str:
        base = self.user_ws_base.rstrip("/")
        if base.endswith("/ws"):
            return f"{base}/{listen_key}"
        return f"{base}/ws/{listen_key}"

    async def query_order(self, symbol: str, client_order_id: str) -> Dict[str, Any]:
        if self.paper_trading:
            return {
                "symbol": symbol,
                "clientOrderId": client_order_id,
                "status": "NEW",
                "paper": True,
            }
        params = {"symbol": symbol.upper(), "origClientOrderId": client_order_id}
        path = self._api_path("/api/v3/order", "/fapi/v1/order")
        return await self._request("GET", path, signed=True, params=params)
