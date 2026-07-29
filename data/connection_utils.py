from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from core.exceptions import ExchangeConnectionError
from data.exchange_client import get_exchange

T = TypeVar("T")


def fetch_with_retry(
    operation: Callable[[], T],
    *,
    max_retries: int = 3,
    base_delay: float = 1.0,
    operation_name: str = "exchange_request",
) -> T:
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            try:
                from data.exchange_client import rotate_exchange_on_rate_limit

                rotate_exchange_on_rate_limit(exc)
            except Exception:
                pass
            if attempt == max_retries:
                break
            time.sleep(base_delay * attempt)

    raise ExchangeConnectionError(
        f"فشل {operation_name} بعد {max_retries} محاولات: {last_error}"
    ) from last_error


def ping_exchange() -> int:
    """فحص اتصال سريع — يُرجع وقت السيرفر بالميلي ثانية."""

    def _ping() -> int:
        exchange = get_exchange()
        server_time = exchange.fetch_time()
        return int(server_time)

    return fetch_with_retry(_ping, operation_name="ping_exchange")
