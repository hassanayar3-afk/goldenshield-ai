# نفق Cloudflare ثابت (Named Tunnel) — GoldenShield

رابط `trycloudflare.com` **مؤقت** ويتغيّر عند كل إعادة تشغيل للنفق. للحصول على رابط **ثابت 100%** تحتاج Named Tunnel + hostname في Cloudflare Zero Trust.

## 1) في لوحة Cloudflare

1. **Zero Trust** → **Networks** → **Tunnels** → **Create a tunnel**.
2. اختر **Cloudflared** وسمِّ النفق (مثلاً `goldenshield-vps`).
3. أضف **Public Hostname** يشير إلى `http://127.0.0.1:8790` (أو المنفذ في `MOBILE_API_PORT`).
4. انسخ **Tunnel Token** (يبدأ عادة بسلسلة طويلة).

## 2) أسرار Cursor / `.env` على VPS

أضف في أسرار Cloud Agent (أو `vps-production.env`) **دون رفعها إلى GitHub**:

```env
CLOUDFLARE_TUNNEL_TOKEN=<token من لوحة Cloudflare>
MOBILE_PUBLIC_BASE_URL=https://panel.example.com/
MOBILE_PAIR_CODE=GS-LINKxxxxxx
```

- `MOBILE_PUBLIC_BASE_URL` = نفس الـ hostname الذي أنشأته في Public Hostname (مع `/` في النهاية).
- `MOBILE_PAIR_CODE` اختياري؛ إن تُرك فارغاً يُقرأ من `storage/runtime/mobile_api_credentials.txt` تلقائياً.

## 3) بعد النشر

```powershell
C:\GoldenShield_Binance\deploy\windows\Cleanup-GsLegacy.ps1 -Root C:\GoldenShield_Binance -Aggressive
C:\GoldenShield_Binance\deploy\windows\Ensure-GsStableMobileEnv.ps1
C:\GoldenShield_Binance\deploy\windows\Install-GsWindowsServices.ps1 -RemoveScheduledTasks
C:\GoldenShield_Binance\deploy\windows\BUILD_ANDROID_APK.ps1
```

تحميل APK: `https://<MOBILE_PUBLIC_BASE_URL>/download/apk`

## 4) تحقق

- `GET /api/health` عبر الرابط العام
- `GET /api/mobile/pair-link` — يجب أن يحتوي `pair_code` ثابتاً
- التطبيق v2.2+ يقرأ `default_servers.txt` المحدّث بعد `Sync-GsMobileUrls.ps1`

بدون `CLOUDFLARE_TUNNEL_TOKEN` + `MOBILE_PUBLIC_BASE_URL` يبقى النظام على **quick tunnel** فقط (غير ثابت).
