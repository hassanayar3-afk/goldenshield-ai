# GoldenShield Terminal — الهيكل النقي (القادة الثلاثة)

## القادة (Micro-Modules معزولة)

| القائد | المسار | سقف متزامن | الأطر |
|--------|--------|------------|-------|
| SMC & Macro | `engines/smc_macro/` | 4 | 4h/1h/15m + HTF cache |
| gold_flash 2.0 | `gold_flash/` | 12 | 5m Z-Score / POC |
| Micro Momentum | `engines/micro_momentum/` | 5 | WS order book top-5 |

## المنصة المركزية (`terminal/`)

- `orchestrator.py` — حلقة موحّدة بلا تلوث تحليلي
- `elite_gate.py` — Score ≥ 85% (`ELITE_MIN_PERCENT`)
- `dispatcher.py` — 20 صفقة عالمية، صفقة/زوج، حرارة 6–8%
- `module_breaker.py` — خسارتان → إيقاف القسم فقط
- `flash_crash_switch.py` — BTC −1.5%/1m

## التشغيل

- `TRI_COMMANDER_MODE=true` (افتراضي) في `.env`
- `MAX_ELITE_CONCURRENT_POSITIONS=20`

## Terminal App

- `mobile_api_server.py` — `panic` يتطلب `confirm=MOBILE_PANIC_CONFIRM`
