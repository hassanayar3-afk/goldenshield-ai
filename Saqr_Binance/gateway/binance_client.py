"""
Binance REST abstraction: exponential backoff, circuit breaker, paper/live modes.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import aiohttp

from utils.logger_config import setup_logger

logger = setup_logger("saqr.binance")


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


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
        default_factory=lambda: os.getenv("BINANCE_BASE_URL", "https://demo-api.binance.com")
    )
    paper_trading: bool = field(
        default_factory=lambda: _env_bool("PAPER_TRADING", True)
        or _env_bool("BINANCE_DEMO_TRADING", True)
    )
    max_retries: int = 5
    base_backoff: float = 0.5
    _session: Optional[aiohttp.ClientSession] = field(default=None, init=False, repr=False)
    _breaker: CircuitBreaker = field(default_factory=CircuitBreaker, init=False)

    async def start(self) -> None:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

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

    async def _request(
        self,
        method: str,
        path: str,
        *,
        signed: bool = False,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if not self._breaker.allow():
            raise RuntimeError("Binance circuit breaker is open")

        await self.start()
        assert self._session is not None
        params = params or {}
        headers = {"X-MBX-APIKEY": self.api_key} if signed else {}

        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                if signed:
                    params = self._sign(params)
                url = f"{self.base_url}{path}"
                async with self._session.request(method, url, params=params, headers=headers) as resp:
                    body = await resp.json(content_type=None)
                    if resp.status >= 400:
                        raise RuntimeError(f"HTTP {resp.status}: {body}")
                self._breaker.record_success()
                return body
            except Exception as exc:
                last_error = exc
                self._breaker.record_failure()
                delay = self.base_backoff * (2**attempt)
                logger.warning(
                    "Binance request failed (%s %s) attempt %s/%s: %s",
                    method,
                    path,
                    attempt + 1,
                    self.max_retries,
                    exc,
                )
                await asyncio.sleep(delay)

        raise RuntimeError(f"Binance request exhausted retries: {last_error}")

    async def ping(self) -> bool:
        if self.paper_trading:
            return True
        try:
            await self._request("GET", "/api/v3/ping")
            return True
        except Exception as exc:
            logger.error("Binance ping failed: %s", exc)
            return False

    async def exchange_info(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        if self.paper_trading:
            filters = [
                {"filterType": "MIN_NOTIONAL", "minNotional": "5"},
                {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001"},
            ]
            symbols = [
                {
                    "symbol": symbol or "BTCUSDT",
                    "status": "TRADING",
                    "filters": filters,
                }
            ]
            return {"symbols": symbols}
        params: Dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        return await self._request("GET", "/api/v3/exchangeInfo", params=params)

    async def account_balances(self) -> List[Dict[str, Any]]:
        if self.paper_trading:
            return [
                {"asset": "USDT", "free": "10000", "locked": "0"},
                {"asset": "BTC", "free": "0.05", "locked": "0"},
            ]
        data = await self._request("GET", "/api/v3/account", signed=True)
        return list(data.get("balances", []))

    async def open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.paper_trading:
            return []
        params: Dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        return await self._request("GET", "/api/v3/openOrders", signed=True, params=params)

    async def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        *,
        time_in_force: str = "GTC",
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
            }
        params = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": f"{quantity:.8f}".rstrip("0").rstrip("."),
        }
        return await self._request("POST", "/api/v3/order", signed=True, params=params)

    async def place_stop_market(
        self,
        symbol: str,
        side: str,
        stop_price: float,
        quantity: float,
    ) -> Dict[str, Any]:
        """
        Exchange-side STOP_MARKET protection — survives local process shutdown.
        """
        client_id = f"saqr_stop_{uuid.uuid4().hex[:16]}"
        if self.paper_trading:
            return {
                "symbol": symbol,
                "clientOrderId": client_id,
                "type": "STOP_MARKET",
                "status": "NEW",
                "stopPrice": str(stop_price),
            }
        params = {
            "symbol": symbol,
            "side": side,
            "type": "STOP_MARKET",
            "stopPrice": f"{stop_price:.8f}".rstrip("0").rstrip("."),
            "quantity": f"{quantity:.8f}".rstrip("0").rstrip("."),
            "newClientOrderId": client_id,
        }
        return await self._request("POST", "/api/v3/order", signed=True, params=params)

    async def place_ioc_limit(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
    ) -> Dict[str, Any]:
        if self.paper_trading:
            return {
                "symbol": symbol,
                "status": "FILLED",
                "type": "LIMIT",
                "timeInForce": "IOC",
                "executedQty": str(quantity),
            }
        params = {
            "symbol": symbol,
            "side": side,
            "type": "LIMIT",
            "timeInForce": "IOC",
            "quantity": f"{quantity:.8f}".rstrip("0").rstrip("."),
            "price": f"{price:.8f}".rstrip("0").rstrip("."),
        }
        return await self._request("POST", "/api/v3/order", signed=True, params=params)
