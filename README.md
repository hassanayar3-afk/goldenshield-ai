# GoldenShield AI

نظام تداول آلي هجين — تحليل فني (SMC/FVG) + ذكاء سوقي (VIX، أخبار، مشاعر).

**حالة الإصدار:** ✅ **مكتمل 100%** + طبقات مؤسسية **v1.3** (2026-07-29) — راجع `docs/PROJECT_COMPLETION_STATUS.md` و `docs/INSTITUTIONAL_V13_ADDONS_AR.md`

**وثائق التخطيط:** `GoldenShield_AI_Planning/` (خارج المستودع) — ابدأ من `phases/00_الفهرس_الهرمي.md`

---

## التشغيل السريع

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
$env:PYTHONIOENCODING = "utf-8"
python main.py
```

```powershell
pytest tests -v
```

---

## هيكل المشروع

```
GoldenShield_AI/
├── main.py                 # نقطة الدخول — حلقة async
├── requirements.txt
├── .env.example
├── pytest.ini
├── README.md
│
├── config/                 # المرحلة 1 — إعدادات YAML + .env
│   ├── settings.py
│   ├── trading_pairs.yaml
│   ├── risk_params.yaml
│   ├── hybrid_params.yaml
│   ├── economic_calendar.yaml
│   └── environments/       # dev | staging | production
│
├── data/                   # المرحلة 2 — جلب بيانات السوق (Binance/ccxt)
│   ├── exchange_client.py
│   ├── ohlcv_fetcher.py
│   ├── ticker_fetcher.py
│   ├── orderbook_fetcher.py
│   ├── volume_profile.py
│   ├── cache_manager.py
│   ├── connection_monitor.py
│   └── models/
│
├── core/                   # المراحل 3–4 — التحليل والذكاء الهجين
│   ├── analyzer.py
│   ├── hybrid_engine.py
│   ├── market_halt.py
│   ├── constants.py
│   ├── exceptions.py
│   ├── technical/          # SMC, FVG, Signal Scorer
│   ├── fundamental/        # أخبار اقتصادية
│   ├── sentiment/          # Fear & Greed، شذوذ
│   ├── macro/              # VIX، سندات
│   └── liquidity/          # حيتان، مناطق مؤسساتية
│
├── execution/              # المرحلة 5 — محرك التنفيذ
│   ├── trade_executor.py
│   ├── order_manager.py
│   ├── position_manager.py
│   ├── mutex_guard.py
│   ├── correlation_filter.py
│   ├── dark_pool_splitter.py
│   ├── breakeven_logic.py
│   ├── emergency_flat.py
│   ├── sl_tp_calculator.py
│   └── models/
├── risk/                   # المرحلة 6 — إدارة المخاطر
│   ├── risk_orchestrator.py
│   ├── high_conviction_protocol.py
│   ├── standard_bonus_profile.py
│   ├── protocol_models.py
│   ├── lot_calculator.py
│   ├── kill_switch.py
│   ├── monte_carlo.py
│   └── ...
├── audit/                  # المرحلة 7 — تدقيق وShadow Execution
│   ├── audit_trail.py
│   ├── snapshot_recorder.py
│   ├── decision_logger.py
│   ├── shadow_executor.py
│   ├── consensus_gate.py
│   └── models/
├── operations/             # المرحلة 8 — Telegram والمراقبة ✅
│   ├── telegram_bot.py
│   ├── telegram_commands.py
│   ├── panic_button.py
│   ├── alert_dispatcher.py
│   ├── error_logger.py
│   ├── api_watchdog.py
│   ├── pre_flight_checklist.py
│   ├── daily_report.py
│   └── scheduler.py
├── database/               # المرحلة 9 — SQLite والنسخ الاحتياطي ✅
│   ├── connection.py
│   ├── backup_manager.py
│   ├── migrations/
│   └── repositories/
├── saas/                   # المرحلة 10 — SaaS (خارج نطاق v1 — مؤجّل)
├── deployment/             # المرحلة 11 — Docker وCI/CD ✅
├── intelligence/           # المرحلة 12 — ML وRegime (خارج نطاق v1 — مؤجّل)
│
├── storage/                # ملفات تشغيل (ليست حزمة Python)
│   ├── db/                 # قواعد SQLite — لا تتداخل مع data/
│   └── logs/
│
└── tests/                  # اختبارات لكل طبقة
    ├── conftest.py
    ├── test_settings.py
    ├── core/
    └── data/
```

---

## حالة المراحل — الإصدار الحالي مكتمل 100%

| المرحلة | الوصف | الحالة |
|---------|-------|--------|
| 1 | الأساسيات والإعدادات | ✅ 100% |
| 2 | طبقة البيانات | ✅ 100% |
| 3 | التحليل الفني | ✅ 100% |
| 4 | الذكاء الهجين | ✅ 100% |
| 5 | محرك التنفيذ + MT5 | ✅ 100% |
| 6 | إدارة المخاطر + بروتوكولات | ✅ 100% |
| 7 | التدقيق والظل | ✅ 100% |
| 8 | التشغيل وTelegram | ✅ 100% |
| 9 | قاعدة البيانات | ✅ 100% |
| 11 | Docker والنشر | ✅ 100% |
| — | بروتوكولات التشغيل المؤسسية | ✅ 100% |
| 10 | SaaS | ⏸️ خارج v1 |
| 12 | ذكاء متقدم / ML | ⏸️ خارج v1 |

> التفاصيل الكاملة: [`docs/PROJECT_COMPLETION_STATUS.md`](docs/PROJECT_COMPLETION_STATUS.md)

---

## إعداد خارجي (خطوات يدوية قصيرة)

### 1) Binance Live
```powershell
# ضع المفاتيح في .env ثم:
.\.venv\Scripts\python.exe scripts\test_binance_connection.py
```

### 2) Google Drive
```powershell
pip install google-api-python-client google-auth google-auth-oauthlib
# ضع client_secret.json في storage/gdrive_client_secret.json
.\.venv\Scripts\python.exe scripts\setup_gdrive_oauth.py
# ضع GDRIVE_FOLDER_ID في .env
```

### 3) Docker (تشغيل 24/7)
```powershell
docker compose up -d --build
docker compose logs -f
```

### 4) تقويم اقتصادي بعيد
- انسخ `config/economic_calendar.remote.example.json` لسيرفرك
- فعّل `remote_feed_url` في `config/economic_calendar.yaml`

---

## ملاحظات معمارية

- **`data/`** = حزمة Python لجلب بيانات السوق — لا تُخزَّن فيها ملفات `.db`
- **`storage/db/`** = مسار قواعد البيانات (المرحلة 9) — يُضبط عبر `DB_PATH` أو YAML
- **التخطيط** في مجلد منفصل `GoldenShield_AI_Planning/` — افتح `GoldenShield_AI.code-workspace` لعرض الكود والتخطيط معاً

---

## سياسات التشغيل المؤسسية

- **حالة الإكمال الكاملة:** [`docs/PROJECT_COMPLETION_STATUS.md`](docs/PROJECT_COMPLETION_STATUS.md)
- الوثيقة: `docs/EXECUTION_PROTOCOLS_AR.md`
- **قائمة الجودة والسيطرة والوعي بالسوق:** [`docs/QUALITY_CONTROL_CHECKLIST_AR.md`](docs/QUALITY_CONTROL_CHECKLIST_AR.md)
  - تصفية هرمية (SMC/OB/Volume · Re-test · RSI Divergence · Volume Spike)
  - سيطرة (Rate Limiter · Cool-down · Multi-Target Exit)
  - أمان (Watchdog · Kill Zones · Correlation · News)
  - تحسين مستمر (Shadow Logging · Slippage Monitor)
- الإعدادات: `config/high_conviction_protocol.yaml` · `config/standard_bonus_profile.yaml`
- التفعيل عبر `.env`:
  - `HIGH_CONVICTION_MODE=false` — وضع 3% Risk (افتراضي معطّل)
  - `STANDARD_BONUS_PROFILE=false` — ملحق حساب Standard/Bonus (افتراضي معطّل)
- الدمج البرمجي:
  - `risk/high_conviction_protocol.py` — بوابة HC قبل التنفيذ
  - `risk/standard_bonus_profile.py` — تعديل TP وفلاتر السبريد
  - `main.py` → `check_symbol()` يمرّر `prefs` و`protocol` إلى المخاطر والتنفيذ
  - `risk/risk_orchestrator.py` — يحسب اللوت حسب البروتوكول
  - `execution/trade_executor.py` — يوسم الصفقة `risk_mode=high_conviction`
