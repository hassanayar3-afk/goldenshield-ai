@echo off
setlocal EnableExtensions
title GoldenShield — RESTART BOT
color 0B

set "GS_ROOT=%~dp0"
if "%GS_ROOT:~-1%"=="\" set "GS_ROOT=%GS_ROOT:~0,-1%"
if not exist "%GS_ROOT%\main.py" set "GS_ROOT=C:\GoldenShield_Binance"

call "%GS_ROOT%\scripts\gs_common_env.cmd"

echo.
echo ========================================================
echo   GoldenShield AI ^| RESTART BOT ^(VISIBLE^)
echo ========================================================
echo.

if not exist "%GS_ROOT%\main.py" (
  echo [ERROR] Project not found: %GS_ROOT%
  pause
  exit /b 1
)
if not exist "%GS_ROOT%\.env" (
  echo [ERROR] .env not found
  pause
  exit /b 1
)

cd /d "%GS_ROOT%"

echo [1/4] Stop current instance...
schtasks /End /TN "%GS_TASK%" /F >nul 2>&1
schtasks /End /TN "GoldenShieldLiveConsole" /F >nul 2>&1
schtasks /End /TN "GoldenShieldStatusWindow" /F >nul 2>&1
if exist "%GS_KILL%" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%GS_KILL%"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py|run_official_bot|run_bot_visible|BOT_WINDOW|live_console|00_LIVE_CONSOLE' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }"
)
timeout /t 3 /nobreak >nul

echo [2/4] Clear stop flag + locks...
if exist "%GS_RUNTIME%\user_stopped.flag" del /f /q "%GS_RUNTIME%\user_stopped.flag" >nul 2>&1
if exist "%GS_RUNTIME%\bot_instance.lock" del /f /q "%GS_RUNTIME%\bot_instance.lock" >nul 2>&1
if exist "C:\ProgramData\GoldenShield\bot_instance.lock" del /f /q "C:\ProgramData\GoldenShield\bot_instance.lock" >nul 2>&1

echo [3/4] No-Sleep power settings...
powercfg -change -standby-timeout-ac 0 >nul 2>&1
powercfg -change -hibernate-timeout-ac 0 >nul 2>&1

echo [4/4] Start visible bot + signals board...
start "GoldenShield BOT LIVE" /D "%GS_ROOT%" cmd.exe /k call "%GS_ROOT%\run_bot_visible.cmd"
timeout /t 5 /nobreak >nul
if exist "%GS_PULSE%" (
  start "GoldenShield LIVE SIGNALS BOARD" /D "%GS_ROOT%" powershell.exe -NoExit -NoProfile -ExecutionPolicy Bypass -File "%GS_PULSE%"
)

echo.
echo --------------------------------------------------------
echo   Status: RESTARTED ^(visible^)
echo   Pulse: ~4s in BOT LIVE window
echo --------------------------------------------------------
echo.
timeout /t 3 /nobreak >nul
endlocal
exit /b 0
