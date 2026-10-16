"""Binance / ccxt proxy resolution — HTTP or SOCKS5 (Contabo 451 bypass)."""

from __future__ import annotations

import os
from urllib.parse import quote


def _clean(val: str | None) -> str:
    return (val or "").strip().strip('"').strip("'")


def _build_from_parts() -> str:
    host = _clean(os.getenv("PROXY_HOST") or os.getenv("BINANCE_PROXY_HOST"))
    port = _clean(os.getenv("PROXY_PORT") or os.getenv("BINANCE_PROXY_PORT"))
    if not host or not port:
        return ""
    scheme = _clean(os.getenv("PROXY_SCHEME") or os.getenv("BINANCE_PROXY_SCHEME") or "http").lower()
    if scheme not in {"http", "https", "socks5", "socks5h"}:
        scheme = "http"
    user = _clean(os.getenv("PROXY_USER") or os.getenv("BINANCE_PROXY_USER"))
    password = _clean(os.getenv("PROXY_PASSWORD") or os.getenv("BINANCE_PROXY_PASSWORD"))
    if user:
        auth = quote(user, safe="")
        if password:
            auth += ":" + quote(password, safe="")
        return f"{scheme}://{auth}@{host}:{port}"
    return f"{scheme}://{host}:{port}"


def resolve_binance_proxy_url() -> str:
    """
    Single proxy URL for ccxt ``proxies`` dict (http + https keys).

    Priority:
    PROXY_URL / BINANCE_PROXY_URL → PROXY_HOST+PORT → BINANCE_HTTPS_PROXY /
    BINANCE_HTTP_PROXY / BINANCE_SOCKS_PROXY → HTTPS_PROXY / HTTP_PROXY
    """
    for key in (
        "PROXY_URL",
        "BINANCE_PROXY_URL",
        "ALL_PROXY",
        "BINANCE_HTTPS_PROXY",
        "BINANCE_HTTP_PROXY",
    ):
        val = _clean(os.getenv(key))
        if val:
            return val
    socks = _clean(os.getenv("BINANCE_SOCKS_PROXY") or os.getenv("SOCKS_PROXY"))
    if socks:
        if "://" not in socks:
            socks = f"socks5://{socks}"
        return socks
    built = _build_from_parts()
    if built:
        return built
    for key in ("HTTPS_PROXY", "HTTP_PROXY"):
        val = _clean(os.getenv(key))
        if val:
            return val
    return ""


def ccxt_proxies_dict() -> dict[str, str] | None:
    url = resolve_binance_proxy_url()
    if not url:
        return None
    return {"http": url, "https": url}
