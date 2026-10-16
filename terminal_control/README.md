# terminal_control (Black Horse 2.0)

Isolated UI layer — **does not** import `core_engine` directly.

| Asset | Path |
|-------|------|
| Control panel (web) | `../control-panel-www/` |
| Android APK sources | `../mobile_android/` |
| Mobile API (legacy HTTP) | `../terminal_app/` |
| Fast gateway (SSE) | `../gateway_api/fast_router.py` |

Permanent panel URL: set `MOBILE_PUBLIC_BASE_URL` / `config/mobile_default_servers.txt`.
