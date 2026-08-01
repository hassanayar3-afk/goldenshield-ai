GoldenShield — Binance Demo ONLY (full package + Cognitive Hedge)
====================================================
This package opens trades on Binance Spot Demo only.
No MetaTrader / no XM / no forex / no real-money Live account.

INSTALL on Windows:
1) Delete any old package folders
2) Extract ALL files to:  C:\GoldenShield_Binance
3) Run:  00_START_VISIBLE.vbs
   (or 00_START_KEEP_OPEN.bat)
4) KEEP the black CMD window open
5) In Telegram send: /start
6) To stop: 00_STOP.bat

Package settings:
- EXECUTION_BACKEND=binance
- BINANCE_DEMO_TRADING=true
- MetaTrader disabled (hard)
- Telegram signals from 85/100
- Auto entry from 90/100
- Live positions board every ~1 second
- Live signals board every ~15 seconds

New Cognitive Hedge layers (additive):
- Shadow Stress parallel hypotheses (~15m watch)
- Trap cooldown after 3 shadow fails (1h)
- Black Box loss snapshot + Telegram
- Order book imbalance gate
- Fractional exits ~30/40/30
- Adaptive weights (+/-20%)
- Macro Fear&Greed + whale soft gate
- Risk committee (rules; LLM off by default)

See docs/COGNITIVE_HEDGE_LAYERS_AR.md inside the package.
