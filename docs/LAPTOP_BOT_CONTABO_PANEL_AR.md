# بوت على اللابتوب + لوحة Contabo

## الهدف
- **main.py** على IP المنزل (بدون 451).
- **Mobile API** على Contabo يقرأ ملفات `storage/runtime` المزامنة.

## 1) اللابتوب — إعداد

```powershell
cd C:\GoldenShield   # أو مسار clone المشروع
powershell -ExecutionPolicy Bypass -File .\deploy\windows\Setup-LaptopTradingBot.ps1
```

عدّل `.env`:
- `BINANCE_API_KEY` / `BINANCE_API_SECRET`
- `BINANCE_DEMO_TRADING=true`, `EXECUTION_MODE=paper`
- `PROXY_URL=` (فارغ)
- `WIN_HOST`, `WIN_USER`, `WIN_PASSWORD` أو `WIN_SSH_PRIVATE_KEY`
- `RUNTIME_SYNC_REMOTE_ROOT=C:\GoldenShield_Binance`

## 2) اختبار باينانس

```powershell
.\venv\Scripts\python.exe scripts\test_binance_connection.py
```

يجب ✅ بدون 451.

## 3) تشغيل البوت

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\windows\Start-LaptopTradingBot.ps1 -UseDaemon
```

تحقق:

```powershell
Get-Item .\storage\runtime\heartbeat.json, .\storage\runtime\binance_snapshot.json
```

## 4) مزامنة إلى Contabo (كل 15 ث)

نافذة PowerShell ثانية:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\windows\Sync-RuntimeToContabo.ps1
```

مرة واحدة:

```powershell
.\venv\Scripts\python.exe scripts\sync_runtime_to_contabo.py
```

## 5) Contabo — لوحة فقط

```powershell
powershell -ExecutionPolicy Bypass -File C:\GoldenShield_Binance\deploy\windows\Start-PanelOnlyContabo.ps1
```

يفعّل `GS_PANEL_REMOTE_SNAPSHOT_ONLY=true` ويوقف `main.py` على السيرفر.

## 6) فتح اللوحة

`storage/runtime/mobile_tunnel_url.txt` + `?pair_code=` من `MOBILE_PAIR_CODE`.

`/api/health` → `snapshot_fresh: true` بعد المزامنة.

## قيود
- اللابتوب يجب أن يبقى شغّالاً + سكربت المزامنة.
- أزرار الإيقاف على اللوحة تؤثر على Contabo فقط — البوت على اللابتوب لا يرى `user_stopped.flag` إلا بمزامنة عكسية (غير مدمجة حالياً).
