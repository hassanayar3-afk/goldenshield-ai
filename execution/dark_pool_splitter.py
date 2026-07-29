"""تقسيم الصفقات الكبيرة — Dark Pool Logic."""

from __future__ import annotations

from config.settings import get_settings


def split_order(
    amount: float,
    price: float,
    *,
    max_chunk_usdt: float | None = None,
) -> list[float]:
    if amount <= 0 or price <= 0:
        return []

    settings = get_settings()
    chunk_limit = (
        max_chunk_usdt if max_chunk_usdt is not None else settings.dark_pool_max_chunk_usdt
    )
    total_usdt = amount * price

    if total_usdt <= chunk_limit:
        return [round(amount, 8)]

    chunk_amount = chunk_limit / price
    chunks: list[float] = []
    remaining = amount

    while remaining > 0:
        piece = min(remaining, chunk_amount)
        rounded = round(piece, 8)
        if rounded <= 0:
            break
        chunks.append(rounded)
        remaining = round(remaining - rounded, 8)
        if remaining < 1e-8:
            break

    return chunks if chunks else [round(amount, 8)]
