@echo off
title Saqr Binance Bot - Local Sovereign Mode
cd /d %~dp0..
echo Starting Local Gateway and Neural Matrix...
start cmd /k "python -m uvicorn gateway_api.fast_router:app --host 127.0.0.1 --port 8000 --reload"
timeout /t 3
start cmd /k "python core_engine/neural_matrix.py"
echo System is running successfully! Open your browser at: http://localhost:8000
pause
