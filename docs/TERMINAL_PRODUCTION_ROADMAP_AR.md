# GoldenShield Terminal — خريطة طريق الإنتاج (مرتبة)

## P0 — حرجة (تم / جاري)

1. **توجيه Routes مباشرة** → `alerts_queue` / `binance_mirror` / `bot_bridge` + `routes_registry.py`
2. **Smoke test** → `python3 scripts/smoke_terminal_api.py`
3. **لوحة control-panel-www** → ربط، stack، orderbook WS + snapshot

## P1 — تشغيل VPS (بدون SSH)

4. **حزمة ZIP:** `python3 scripts/build_deployment_package.py` → `dist/GoldenShield-Terminal-P1-*.zip`
5. RDP → فك إلى `C:\GoldenShield_Binance` → `deploy\windows\INSTALL_GOLDENSHIELD_TERMINAL.ps1`
6. `deploy\windows\START_TERMINAL_STACK.ps1` + فتح منافذ `8790`/`8791`
7. (اختياري لاحقاً) `WIN_SSH_PRIVATE_KEY` + `scripts/auto_windows_deploy.py`
8. Cloudflare tunnel → `storage/runtime/mobile_tunnel_url.txt`

## P1b — E2E Tri-Commander محلي

```bash
python3 scripts/smoke_tri_commander.py   # TRI_SMOKE_OK
python3 scripts/smoke_terminal_api.py    # SMOKE_OK
```

إعدادات: `config/tri_commander_smoke.env`

## P2 — تداول حي (Demo)

7. `TRI_COMMANDER_MODE=true` + `EXECUTION_MODE=paper` أو Demo Binance
8. مراقبة `storage/runtime/module_breakers.json` و Elite Gate

## P3 — تحسينات

9. APK Android (خارج الريبو) يستهلك نفس API
10. 2FA إلزامي للطوارئ (`MOBILE_2FA_ENABLED=true`)
