# صقر (Saqr AI) — التشغيل المحلي على Binance

منظومة تداول asyncio معزولة معمارياً، بدون تيليجرام/ديسكord أو أنفاق سحابية.

## مسار التثبيت على Windows

انسخ مجلد `Saqr_Binance` بالكامل إلى:

- `C:\Saqr_Binance\` (المسار المعتمد للتشغيل)
- أو `C:\Users\acer\صقر\` ثم شغّل من داخل المجلد

## التشغيل السريع

1. انسخ `.env.example` إلى `.env` وأدخل مفاتيح Binance Demo إن لزم.
2. تأكد أن `PAPER_TRADING=True` للتجربة الآمنة.
3. شغّل `run_saqr_local.bat` (يفتح المتصفح على لوحة التحكم).
4. WebSocket الحي: `ws://127.0.0.1:8000/ws`

## الهيكل

| مجلد | الدور |
|------|--------|
| `gateway/` | FastAPI، Binance client، WebSocket hub، مزامنة الحالة |
| `engines/` | SMC macro، Gold Flash، Momentum |
| `database/` | SQLite WAL + DAO locks |
| `terminal_ui/` | لوحة محلية مع مؤشر ● LIVE |
| `utils/` | Logger دوّار + crash wrapper + watchdog |

## Linux / Cloud (اختبار)

```bash
cd Saqr_Binance
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m gateway.main
```

## أمان

- أوامر `STOP_MARKET` على سيرفرات Binance عند تفعيل `DEFAULT_STOP_MARKET=true`.
- لا ترفع ملف `.env` إلى Git (مذكور في `.gitignore`).
