# تعليمات لوكيل Cursor (Cloud / Phone)

أنت تعمل على مستودع GoldenShield AI.

## قدراتك هنا
- تعديل الكود، الاختبارات، الإعدادات، والسكربتات
- إذا توفرت أسرار البيئة (`WIN_HOST`, `WIN_USER`, `WIN_PASSWORD`) يمكنك إدارة سيرفر ويندوز عبر SSH مثل سكربتات `scripts/`
- Demo Trading فقط ما لم يطلب المستخدم غير ذلك صراحة

## ممنوع
- طباعة أو عمل commit لأي قيم من `.env` أو كلمات المرور أو مفاتيح API
- رفع أسرار إلى GitHub
- تداول Live إلا بطلب صريح

## مراجع
- `docs/PHONE_CLOUD_AGENT_AR.md`
- `.env.example`
- `SESSION_STATE.md`

## Cursor Cloud specific instructions

Headless Python 3.12 async trading bot (no web UI). Standard commands live in `README.md` and `.github/workflows/ci.yml`.

- Python binary is `python3` only (there is NO `python` on the VM); `pip` maps to Python 3.12. Deps install into `~/.local` (no `venv` package available). The update script (`pip install -r requirements.txt`) already runs on startup.
- Copy `.env.example` to `.env` before running (`main.py` loads it). Defaults are paper mode; no secrets needed to boot.
- Run tests: `python3 -m pytest tests -q`. Run app: `python3 -u main.py`.
- Network caveat: Binance main API (`api.binance.com`, `fapi/testnet/api-gcp`) returns HTTP 451 (geo-block) from the cloud VM. So `main.py` halts at the `binance_ping` pre-flight check and the live loop cannot fetch data here. The public spot market-data mirror `https://data-api.binance.vision` (only `/api/v3` spot) IS reachable — use it (remap ccxt `urls['api']` + `options.fetchMarkets=['spot']`) to exercise the real fetch→analyze→score pipeline (`core.analyzer.MarketAnalyzer`) against live data.
- Pre-existing (NOT environment) test issues: `tests/core/test_signal_scorer.py` fails collection (`ScoreBreakdown` used but not imported), `tests/execution/test_breakeven_logic.py::test_breakeven_triggers_at_one_to_one` asserts `0.4 == 0.5`, and the `tests/data/test_ohlcv_fetcher.py` live-network tests fail with Binance 451. Expect ~226 passing otherwise.
