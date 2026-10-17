# صقر (Saqr AI) — التشغيل المحلي

المسار المعتمد على Windows: **`C:\Users\acer\saqr\`** — ضع ملف **`.env`** في جذر هذا المجلد (انظر `.env.example`).

## تشغيل

1. `run_saqr_local.bat`
2. لوحة التحكم: `http://127.0.0.1:8000` (المنفذ من `MOBILE_API_PORT` / `TERMINAL_WS_PORT`)
3. WebSocket: `ws://127.0.0.1:8000/ws`

## متغيرات البيئة المعتمدة

جميع المفاتيح موثقة في **`.env.example`** — لا تُضاف متغيرات خارج هذه القائمة في التشغيل الرسمي.

- **`PAPER_TRADING` / `EXECUTION_MODE`**: paper = تنفيذ محاكى + شموع حية
- **`DB_PATH`**: مثال `database/saqr_local.db`
- **`BINANCE_BASE_URL`**: Futures REST (`fapi`) عند استخدام العقود
- **`BINANCE_MARKET_WS_URL`**: بث الشموع (Spot stream)
- **`BINANCE_USER_WS_BASE`**: User stream (مثلاً `fstream`)
- **`LOOP_INTERVAL_SECONDS`**: دورة المزامنة والمحركات
- **`WATCHDOG_ENABLED`**: مراقبة تجمد الـ Event Loop

## هيكل الوحدات

`gateway/` · `engines/` · `database/` · `terminal_ui/` · `utils/`
