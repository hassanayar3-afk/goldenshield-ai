# GoldenShield Terminal — خريطة طريق الإنتاج (مرتبة)

## P0 — حرجة (تم / جاري)

1. **توجيه Routes مباشرة** → `alerts_queue` / `binance_mirror` / `bot_bridge` + `routes_registry.py`
2. **Smoke test** → `python3 scripts/smoke_terminal_api.py`
3. **لوحة control-panel-www** → ربط، stack، orderbook WS + snapshot

## P1 — تشغيل VPS

4. نشر الفرع على Windows VPS + `MOBILE_API_PORT` / `TERMINAL_WS_PORT` في الجدار الناري
5. `python3 scripts/auto_windows_deploy.py` بعد ضبط `WIN_*` secrets
6. Cloudflare tunnel → `storage/runtime/mobile_tunnel_url.txt`

## P2 — تداول حي (Demo)

7. `TRI_COMMANDER_MODE=true` + `EXECUTION_MODE=paper` أو Demo Binance
8. مراقبة `storage/runtime/module_breakers.json` و Elite Gate

## P3 — تحسينات

9. APK Android (خارج الريبو) يستهلك نفس API
10. 2FA إلزامي للطوارئ (`MOBILE_2FA_ENABLED=true`)
