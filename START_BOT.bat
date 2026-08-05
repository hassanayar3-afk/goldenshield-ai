@echo off
setlocal EnableExtensions
title GoldenShield — START BOT
color 0A

set "GS_ROOT=%~dp0"
if "%GS_ROOT:~-1%"=="\" set "GS_ROOT=%GS_ROOT:~0,-1%"
if not exist "%GS_ROOT%\main.py" set "GS_ROOT=C:\GoldenShield_Binance"

call "%GS_ROOT%\scripts\gs_common_env.cmd"

echo.
echo ========================================================
echo   GoldenShield AI ^| START BOT ^(VISIBLE^)
echo   Binance only ^| Single Instance ^| No-Sleep 24/7
echo   Telegram + Dashboard + SSoT + Live CMD pulse
echo ========================================================
echo.

if not exist "%GS_ROOT%\main.py" (
  echo [ERROR] Project not found: %GS_ROOT%
  pause
  exit /b 1
)
if not exist "%GS_ROOT%\.env" (
  echo [ERROR] .env not found in %GS_ROOT%
  pause
  exit /b 1
)

cd /d "%GS_ROOT%"

echo [1/6] Disable Windows sleep / hibernate...
powercfg -change -standby-timeout-ac 0 >nul 2>&1
powercfg -change -hibernate-timeout-ac 0 >nul 2>&1
powercfg -change -monitor-timeout-ac 0 >nul 2>&1

echo [2/6] Stop any previous bot / duplicate workers...
schtasks /End /TN "%GS_TASK%" /F >nul 2>&1
schtasks /End /TN "GoldenShieldLiveConsole" /F >nul 2>&1
schtasks /End /TN "GoldenShieldStatusWindow" /F >nul 2>&1
schtasks /Delete /TN "GoldenShieldStatusWindow" /F >nul 2>&1
schtasks /Delete /TN "GoldenShieldLiveConsole" /F >nul 2>&1
if exist "%GS_KILL%" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%GS_KILL%"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py|run_official_bot|run_bot_visible|BOT_WINDOW|live_console|00_LIVE_CONSOLE' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }"
)
timeout /t 2 /nobreak >nul

echo [3/6] Clear stop flag and stale locks only...
if not exist "%GS_RUNTIME%" mkdir "%GS_RUNTIME%" >nul 2>&1
if not exist "%GS_LOGS%" mkdir "%GS_LOGS%" >nul 2>&1
if exist "%GS_RUNTIME%\user_stopped.flag" del /f /q "%GS_RUNTIME%\user_stopped.flag" >nul 2>&1
if exist "%GS_RUNTIME%\bot_instance.lock" del /f /q "%GS_RUNTIME%\bot_instance.lock" >nul 2>&1
if exist "C:\ProgramData\GoldenShield\bot_instance.lock" del /f /q "C:\ProgramData\GoldenShield\bot_instance.lock" >nul 2>&1

echo [4/6] Register ONSTART visible core ^(no hidden worker^)...
schtasks /Delete /TN "%GS_TASK%" /F >nul 2>&1
schtasks /Create /TN "%GS_TASK%" /TR "cmd.exe /c start \"GoldenShield BOT LIVE\" /D \"%GS_ROOT%\" cmd.exe /k call \"%GS_ROOT%\run_bot_visible.cmd\"" /SC ONSTART /RL HIGHEST /F >nul 2>&1

echo [5/6] Open VISIBLE bot window ^(live pulse in CMD^)...
start "GoldenShield BOT LIVE" /D "%GS_ROOT%" cmd.exe /k call "%GS_ROOT%\run_bot_visible.cmd"
timeout /t 5 /nobreak >nul

echo [6/6] Open live signals board companion window...
if exist "%GS_PULSE%" (
  start "GoldenShield LIVE SIGNALS BOARD" /D "%GS_ROOT%" powershell.exe -NoExit -NoProfile -ExecutionPolicy Bypass -File "%GS_PULSE%"
) else if exist "%GS_ROOT%\BOT_WINDOW.ps1" (
  start "GoldenShield LIVE SIGNALS BOARD" /D "%GS_ROOT%" powershell.exe -NoExit -NoProfile -ExecutionPolicy Bypass -File "%GS_ROOT%\BOT_WINDOW.ps1"
)

echo.
echo --------------------------------------------------------
echo   Status: STARTED ^(visible^)
echo   Root:   %GS_ROOT%
echo   Windows:
echo     1^) GoldenShield BOT LIVE  — main.py + pulse ~4s
echo     2^) LIVE SIGNALS BOARD     — signals_board mirror
echo   Telegram dashboard / close menu / reports: active
echo   Stop with:  stop_bot.bat
echo --------------------------------------------------------
echo.
timeout /t 4 /nobreak >nul
endlocal
exit /b 0
