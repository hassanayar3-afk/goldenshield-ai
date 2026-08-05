@echo off
setlocal EnableExtensions
title GoldenShield — STOP BOT
color 0C

set "GS_ROOT=%~dp0"
if "%GS_ROOT:~-1%"=="\" set "GS_ROOT=%GS_ROOT:~0,-1%"
if not exist "%GS_ROOT%\main.py" set "GS_ROOT=C:\GoldenShield_Binance"

call "%GS_ROOT%\scripts\gs_common_env.cmd"

echo.
echo ========================================================
echo   GoldenShield AI ^| STOP BOT
echo   Full shutdown — single instance cleared
echo ========================================================
echo.

if not exist "%GS_ROOT%\main.py" (
  echo [ERROR] Project not found: %GS_ROOT%
  pause
  exit /b 1
)

cd /d "%GS_ROOT%"

echo [1/3] End scheduled tasks...
schtasks /End /TN "%GS_TASK%" /F >nul 2>&1
schtasks /End /TN "GoldenShieldLiveConsole" /F >nul 2>&1
schtasks /End /TN "GoldenShieldStatusWindow" /F >nul 2>&1

echo [2/3] Kill bot + pulse windows...
if exist "%GS_KILL%" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%GS_KILL%"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py|run_official_bot|run_bot_visible|BOT_WINDOW|live_console|00_LIVE_CONSOLE' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }"
)
timeout /t 2 /nobreak >nul

echo [3/3] Write user_stopped.flag + clear locks...
if not exist "%GS_RUNTIME%" mkdir "%GS_RUNTIME%" >nul 2>&1
(
  echo {
  echo   "reason": "stop_bot.bat",
  echo   "source": "user",
  echo   "stopped_at": "%DATE% %TIME%"
  echo }
) > "%GS_RUNTIME%\user_stopped.flag"
if exist "%GS_RUNTIME%\bot_instance.lock" del /f /q "%GS_RUNTIME%\bot_instance.lock" >nul 2>&1
if exist "C:\ProgramData\GoldenShield\bot_instance.lock" del /f /q "C:\ProgramData\GoldenShield\bot_instance.lock" >nul 2>&1

echo.
echo --------------------------------------------------------
echo   Status: STOPPED
echo   Data kept: DB / reports / logs
echo   Start again: start_bot.bat
echo --------------------------------------------------------
echo.
pause
endlocal
exit /b 0
