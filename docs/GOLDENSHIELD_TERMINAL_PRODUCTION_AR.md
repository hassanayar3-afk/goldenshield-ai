# GoldenShield Terminal — دليل التشغيل الإنتاجي (100%)

## 1) الإعداد

1. فك الحزمة إلى `C:\GoldenShield_Binance`
2. `deploy\windows\INSTALL_GOLDENSHIELD_TERMINAL.ps1`
3. انسخ `config\env.production.template` → `.env` (أو استخدم `.env.template` من ZIP)
4. املأ: `BINANCE_API_KEY` / `SECRET` (Demo)، `DISCORD_WEBHOOK_URL` (أو Bot+Channel)، اختياري `TELEGRAM_*`

## 2) تشغيل المنظومة الكاملة

**أمر واحد (موصى به):**

```
C:\GoldenShield_Binance\GS_START_FULL_STACK.bat
```

أو: `START_BOT_24_7.bat` (نفس المكدس)

يشغّل بالترتيب:

| الطبقة | المكوّن |
|--------|---------|
| 24/7 | `ENFORCE_NO_SLEEP` + مهمة `GoldenShieldNoSleepGuard` |
| Terminal API | `python -m terminal_app.server` (:8790 / WS :8791) |
| Tri-Commander | `gs_daemon.ps1` → `main.py` |
| Discord Stack | `bridges/discord/discord_bridge.py` |
| Tunnel | `cloudflared` → `storage/runtime/mobile_tunnel_url.txt` |

**إيقاف:** `STOP_BOT_FULL.bat`

## 3) التحقق

```bat
python scripts\smoke_terminal_api.py
python scripts\smoke_tri_commander.py
```

- محلي: http://127.0.0.1:8790/
- JSON: `/api/mobile/config` ، `/api/stack`
- نفق: `storage/runtime/mobile_tunnel_url.txt`

## 4) تطبيق Android

- بناء: `deploy\windows\BUILD_ANDROID_APK.ps1`
- تحميل (GitHub مسجّل): `deploy\windows\DOWNLOAD_APK_TO_DESKTOP.ps1`
- Release: https://github.com/hassanayar3-afk/goldenshield-ai/releases/tag/control-apk-p1

في التطبيق: أدخل عنوان السيرفر (LAN أو محلي) → **اكتشاف النفق** → يفتح لوحة HTTPS عبر Cloudflare.

## 5) حزمة ZIP للنشر

```bash
python3 scripts/build_deployment_package.py
```

→ `dist/GoldenShield-Terminal-P1-*.zip` + `.sha256`

## 6) متغيرات `.env` الحرجة

| المتغير | الغرض |
|---------|--------|
| `TRI_COMMANDER_MODE` | القادة الثلاثة |
| `BINANCE_DEMO_TRADING` | Demo API |
| `DISCORD_*` | تنبيهات Stack |
| `CLOUDFLARE_TUNNEL_ENABLED` | نفق للهاتف |
| `MOBILE_PUBLIC_BASE_URL` | بديل ثابت للنفق |
| `MOBILE_API_PORT` / `TERMINAL_WS_PORT` | Terminal |

Demo فقط ما لم يُغيّر `EXECUTION_MODE=live` صراحة.
