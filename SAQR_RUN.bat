@echo off
title Saqr - Local Sovereign Launcher
cd /d "%~dp0"
echo After start, open: http://127.0.0.1:8000/dashboard
call "%~dp0deploy_ops\run.bat"
