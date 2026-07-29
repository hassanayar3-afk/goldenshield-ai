@echo off
chcp 65001 >nul
title فحص MT5 - للمبتدئ
cd /d "%~dp0"
echo.
echo ========================================
echo   فحص سريع قبل تشغيل البوت
echo ========================================
echo.
echo اعمل الخطوات بالترتيب:
echo.
echo [1] افتح برنامج XM MetaTrader 5
echo     (ليس MetaQuotes Demo)
echo.
echo [2] تأكد انك داخل حسابك
echo     مثال: 345814054
echo     السيرفر: XM.COM-MT5
echo.
echo [3] من القائمة:
echo     Tools → Options → Expert Advisors
echo     ضع علامة على:
echo     Allow Algorithmic Trading
echo     ثم OK
echo.
echo [4] اترك MT5 مفتوحاً على الشاشة
echo.
echo [5] شغّل: 00_STOP.bat
echo     ثم:   00_START.bat
echo.
echo ========================================
echo جاري فحص هل بايثون يرى MT5 ...
echo ========================================
where py >nul 2>&1
if errorlevel 1 (
  set PY=python
) else (
  set PY=py
)
%PY% -c "import MetaTrader5 as m; print('initialize=', m.initialize()); print('account=', m.account_info()); print('error=', m.last_error())"
echo.
echo اذا طلع account=None او Authorization failed:
echo معناها المشكلة من دخول MT5 عندك وليس من البوت.
echo ارجع لخطوات 1 الى 4 ثم اعد الفحص.
echo.
pause
