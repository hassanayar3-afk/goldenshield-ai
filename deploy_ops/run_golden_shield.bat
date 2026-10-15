@echo off
setlocal
set "ROOT=C:\GoldenShield_Binance"
cd /d "%ROOT%"
if not exist "%ROOT%\main.py" (
  echo GOLDENSHIELD_ROOT_MISSING
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\deploy\windows\GS_START_FULL_STACK.ps1" -Root "%ROOT%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\deploy\windows\REGISTER_GS_BOOT_STACK.ps1" -Root "%ROOT%" -SkipRegister
for /f "delims=" %%P in ('powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\deploy\windows\Resolve-GsPython.ps1" -Root "%ROOT%"') do set "GSPY=%%P"
start "" /B "%GSPY%" "%ROOT%\core_engine\neural_matrix.py"
start "" /B "%GSPY%" "%ROOT%\deploy_ops\push_discord_live_status.py"
endlocal
exit /b 0
