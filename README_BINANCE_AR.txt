GoldenShield — Binance Demo ONLY (full clean package)
====================================================
This package opens trades on Binance Demo only.
No MetaTrader / no XM / no forex / no real-money Live account.

INSTALL on Windows:
1) Delete any old package folders
2) Extract ALL files to:  C:\GoldenShield_Binance
3) Run:  00_START_VISIBLE.vbs
   (or 00_START_KEEP_OPEN.bat)
4) KEEP the black CMD window open
5) In Telegram send: /start
6) To stop: 00_STOP.bat

WHY a blue PowerShell window appeared and closed:
- Windows sometimes opens .bat in Terminal/PowerShell
- If the bot exits immediately, that window closes at once
- Use 00_START_VISIBLE.vbs so a real CMD window stays open

Package settings:
- EXECUTION_BACKEND=binance
- BINANCE_DEMO_TRADING=true
- MT5_ENABLED=false
- Telegram signals from 85/100
- Auto entry from 90/100
- Live board every 15 seconds
