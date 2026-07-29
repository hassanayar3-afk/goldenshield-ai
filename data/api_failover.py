"""تبديل مفاتيح Binance الاحتياطية عند Rate Limit / حظر مؤقت."""

from __future__ import annotations

from dataclasses import dataclass

from config.settings import get_settings


@dataclass
class ApiCredential:
    api_key: str
    secret: str
    label: str


def list_binance_credentials() -> list[ApiCredential]:
    settings = get_settings()
    creds: list[ApiCredential] = []
    if settings.binance_api_key and settings.binance_api_secret:
        creds.append(
            ApiCredential(
                settings.binance_api_key,
                settings.binance_api_secret,
                "primary",
            )
        )
    key2 = getattr(settings, "binance_api_key_2", None)
    secret2 = getattr(settings, "binance_api_secret_2", None)
    if key2 and secret2:
        creds.append(ApiCredential(str(key2), str(secret2), "backup"))
    return creds


def is_rate_limit_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    markers = (
        "429",
        "418",
        "rate limit",
        "too many requests",
        "banned",
        "ddos",
        "way too many",
    )
    return any(m in text for m in markers)


def failover_enabled() -> bool:
    settings = get_settings()
    cfg = getattr(settings, "institutional_v13", {}) or {}
    if "api_failover_enabled" in cfg:
        return bool(cfg.get("api_failover_enabled"))
    return bool(getattr(settings, "api_failover_enabled", True))
