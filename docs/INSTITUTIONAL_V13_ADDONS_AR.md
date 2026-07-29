# إضافات مؤسسية v1.3 — ملحق تشغيل

> المرجع التنفيذي: طبقات فوق Iron Protocol دون كسر 1% / R:R 1:3 / Zero-SL.
> الإعدادات: `config/risk_params.yaml` → `institutional_v13` + `.env` لمفاتيح Binance الاحتياطية.

## الموجة 1 — بنية ومخاطر
| # | الميزة | الملف / الربط |
|---|--------|----------------|
| 1 | Multi-API Failover | `data/api_failover.py` + `data/exchange_client.py` (`BINANCE_API_KEY_2`) |
| 2 | عزل تحليل/تنفيذ | `main.py` — `manage_positions` قبل التحليل |
| 3 | Health ساعتي | `main.py` → `_maybe_send_alive_pulse` |
| 4 | Crash recovery | موجود مسبقاً (SQLite + restore) |
| 5 | Network Outage 10s | `risk/advanced_shields.py` + `main.py` |
| 6 | Compound streak risk | `risk/compound_growth.py` + `advanced_shields` |
| 7 | Max Slippage 0.1% | pre-trade في `trade_executor` + YAML |
| 8 | Flash Crash CB | `advanced_shields.evaluate_flash_crash` + Kill Switch |

## الموجة 2 — فلاتر وتخارج
| # | الميزة | الملف |
|---|--------|-------|
| 11 | News blackout 30m | `hybrid_params.yaml` |
| 12 | BTC Dominance | `core/market_filters_extra.py` عبر `hybrid_engine` |
| 13 | VP/POC | موجود في quality gates |
| 14 | Spoofing | `detect_spoofing` |
| 15 | RSI+MACD matrix | `quality_gates` + `market_filters_extra` |
| 16–17 | Structural trail + TP 40/40/20 | `execution/smart_exits.py` |
| 20 | تقرير WinRate/Slip/Best | `operations/message_templates.py` |

## الموجة 3 — اختيارية
| # | الميزة | ملاحظة |
|---|--------|--------|
| 9 | Emergency De-Risk | تقليص تحت ضغط — ليس hedge عكسي |
| 10 | Vol-Based Risk % | خلف علم `vol_based_risk_scaling_enabled` |
| 18 | Funding Guard | stub — يتخطى Spot |
| 19 | Weekend Flat | خلف علم — أنسب لـ MT5 |

## تفعيل سريع
- أعلام الموجة 1/2 الافتراضية: ON للحماية، OFF للطبقات الاختيارية (derisk/vol/funding/weekend).
- مفتاح احتياطي: `BINANCE_API_KEY_2` / `BINANCE_API_SECRET_2`.
