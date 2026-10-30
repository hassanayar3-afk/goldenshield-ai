@echo off
chcp 65001 >nul
cd /d "%~dp0..\.."
if not exist ".env" if exist "saqr.env" copy /Y saqr.env .env
if not exist ".env" (
  echo Create .env from saqr.env.template first.
  pause
  exit /b 1
)
for /f "delims=" %%F in ('where python 2^>nul') do set PY=%%F
if not defined PY (
  echo Install Python 3 to run env sanitizer.
  pause
  exit /b 1
)
if exist "scripts\sanitize_saqr_env.py" (
  "%PY%" scripts\sanitize_saqr_env.py .env
) else (
  "%PY%" ..\..\scripts\sanitize_saqr_env.py .env
)
echo OK — .env sanitized. Port default SAQR_WEB_BIND_PORT=8788
pause
