"""حارس الرموز — X-GS-Token / Bearer / query token (مقارنة آمنة زمنياً)."""

from __future__ import annotations

import hmac
import os
import secrets
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import parse_qs, urlparse


class HeaderReader(Protocol):
    def headers_get(self, name: str, default: str = "") -> str: ...

    @property
    def path(self) -> str: ...


@dataclass(frozen=True)
class AuthContext:
    token: str
    source: str
    is_master: bool
    device_id: str | None


@dataclass(frozen=True)
class TokenVerificationResult:
    ok: bool
    reason: str
    context: AuthContext | None = None


def _secure_eq(a: str, b: str) -> bool:
    if not a or not b:
        return False
    try:
        return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
    except Exception:
        return False


def extract_bearer(authorization: str) -> str:
    text = (authorization or "").strip()
    if not text:
        return ""
    lower = text.lower()
    if lower.startswith("bearer "):
        return text[7:].strip()
    return text


class TokenGuard:
    """يتحقق من MASTER token وجلسات الأجهزة المقترنة."""

    def __init__(
        self,
        *,
        master_token: str,
        devices_loader: Callable[[], Mapping[str, Any]] | None = None,
        allow_query_token: bool = True,
    ) -> None:
        self._master = (master_token or "").strip()
        if not self._master:
            self._master = secrets.token_urlsafe(32)
        self._devices_loader = devices_loader
        self._allow_query_token = allow_query_token

    @classmethod
    def from_env(
        cls,
        *,
        devices_loader: Callable[[], Mapping[str, Any]] | None = None,
    ) -> TokenGuard:
        master = (os.getenv("MOBILE_API_TOKEN") or "").strip()
        allow_query = (os.getenv("MOBILE_ALLOW_QUERY_TOKEN", "false") or "false").strip().lower()
        return cls(
            master_token=master,
            devices_loader=devices_loader,
            allow_query_token=allow_query in {"1", "true", "yes", "on"},
        )

    @property
    def master_token(self) -> str:
        return self._master

    def _device_tokens(self) -> dict[str, str]:
        if self._devices_loader is None:
            return {}
        try:
            raw = self._devices_loader()
        except Exception:
            return {}
        devices = raw.get("devices") if isinstance(raw, dict) else raw
        if not isinstance(devices, dict):
            return {}
        mapping: dict[str, str] = {}
        for device_id, meta in devices.items():
            if not isinstance(meta, dict):
                continue
            token = str(meta.get("token") or meta.get("device_token") or "").strip()
            if token:
                mapping[str(device_id)] = token
        return mapping

    def extract_token(self, reader: HeaderReader) -> AuthContext:
        header_token = reader.headers_get("X-GS-Token") or extract_bearer(
            reader.headers_get("Authorization")
        )
        if header_token:
            return AuthContext(
                token=header_token.strip(),
                source="header",
                is_master=False,
                device_id=None,
            )
        if self._allow_query_token:
            query = parse_qs(urlparse(reader.path).query)
            qtoken = (query.get("token") or [""])[0]
            if qtoken:
                return AuthContext(
                    token=str(qtoken).strip(),
                    source="query",
                    is_master=False,
                    device_id=None,
                )
        return AuthContext(token="", source="none", is_master=False, device_id=None)

    def verify(self, reader: HeaderReader) -> TokenVerificationResult:
        ctx = self.extract_token(reader)
        if not ctx.token:
            return TokenVerificationResult(False, "missing_token", None)
        if _secure_eq(ctx.token, self._master):
            return TokenVerificationResult(
                True,
                "master_ok",
                AuthContext(
                    token=ctx.token,
                    source=ctx.source,
                    is_master=True,
                    device_id=None,
                ),
            )
        for device_id, device_token in self._device_tokens().items():
            if _secure_eq(ctx.token, device_token):
                return TokenVerificationResult(
                    True,
                    "device_ok",
                    AuthContext(
                        token=ctx.token,
                        source=ctx.source,
                        is_master=False,
                        device_id=device_id,
                    ),
                )
        return TokenVerificationResult(False, "invalid_token", None)

    def verify_raw_token(self, token: str) -> TokenVerificationResult:
        class _R:
            path = ""

            def headers_get(self, name: str, default: str = "") -> str:
                if name.lower() == "x-gs-token":
                    return token
                return default

        return self.verify(_R())
