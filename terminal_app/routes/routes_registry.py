"""سجل مسارات GoldenShield Terminal — مرجع وحيد للـ router."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteEntry:
    method: str
    path: str
    auth: str  # public | device | master
    module: str
    handler: str


ROUTE_REGISTRY: tuple[RouteEntry, ...] = (
    RouteEntry("GET", "/api/health", "public", "api_public", "handle_public_get"),
    RouteEntry("GET", "/api/bootstrap", "public", "api_public", "handle_public_get"),
    RouteEntry("GET", "/api/boot", "public", "api_public", "handle_public_get"),
    RouteEntry("GET", "/api/rules", "device", "api_read", "handle_authenticated_get"),
    RouteEntry("GET", "/api/status", "device", "api_read", "handle_authenticated_get"),
    RouteEntry("GET", "/api/account", "device", "api_read", "handle_authenticated_get"),
    RouteEntry("GET", "/api/signals", "device", "api_read", "handle_authenticated_get"),
    RouteEntry("GET", "/api/positions", "device", "api_read", "handle_authenticated_get"),
    RouteEntry("GET", "/api/history", "device", "api_read", "handle_authenticated_get"),
    RouteEntry("GET", "/api/alerts", "device", "api_read", "handle_authenticated_get"),
    RouteEntry("GET", "/api/stack", "device", "api_read", "handle_authenticated_get"),
    RouteEntry("GET", "/api/battalion", "device", "api_read", "handle_authenticated_get"),
    RouteEntry("GET", "/api/discord", "device", "api_read", "handle_authenticated_get"),
    RouteEntry("GET", "/api/ws/snapshot", "device", "api_read", "handle_authenticated_get"),
    RouteEntry("POST", "/api/pair", "public", "api_pair", "handle_pair_post"),
    RouteEntry("POST", "/api/heartbeat", "device", "api_act", "handle_heartbeat_post"),
    RouteEntry("POST", "/api/act", "device", "api_act", "handle_act_post"),
    RouteEntry("POST", "/api/discord/config", "device", "router", "discord_config"),
    RouteEntry("PUT", "/upload/apk", "device", "api_upload", "handle_upload_put"),
)
