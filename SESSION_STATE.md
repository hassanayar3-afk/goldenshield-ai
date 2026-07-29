# GoldenShield AI — حالة الجلسة
> آخر تحديث: **2026-07-29** · البناء: `2026-07-29-v13-institutional`

## الحالة العامة
- ✅ **v1 + إضافات مؤسسية v1.3 مكتملة برمجياً**
- دخول تلقائي **≥95** · عرض إشارات **≥75** · مخاطرة افتراضية **1%** · R:R **1:3**
- التشغيل الحالي المضبوط: **paper / Binance Spot**
- الأسرار (تيليجرام / Binance / MT5): تُترك كما هي أو تُرسل لاحقاً عند الحاجة

## ما يعمل الآن (مفعّل)
- Failover API · عزل تحليل/تنفيذ · Health ساعتي · Outage 10s
- Compound streak risk · Slippage 0.1% · Flash Crash CB
- News 30m · BTC.D · Spoofing · RSI+MACD · Multi-Tier TP 40/40/20 · Structural trail
- تقرير يومي موسّع · persist لـ `exit_tier`

## معطّل عمداً (فعّل بعد استقرار Paper)
- `emergency_derisk_enabled`
- `vol_based_risk_scaling_enabled`
- `funding_guard_enabled`
- `weekend_flat_enabled`
- High Conviction / Bonus / ADX / Profit Cap

## بانتظار منك (عند الجاهزية)
1. `BINANCE_API_KEY` / `SECRET` (+ اختياري `_2` للـ Failover)
2. تأكيد `TELEGRAM_TOKEN` + `TELEGRAM_CHAT_ID` إن لزم تحديث
3. لـ Live MT5: `MT5_*` + `EXECUTION_BACKEND=mt5` + `EXECUTION_MODE=live`

## أوامر
```powershell
python scripts/apply_operational_defaults.py
pytest tests/risk/test_institutional_v13.py -q
python main.py
```

المرجع: `docs/INSTITUTIONAL_V13_ADDONS_AR.md`
