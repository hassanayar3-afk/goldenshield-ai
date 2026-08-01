"""يبني حزمة تثبيت Windows: GoldenShield Binance Demo فقط (بدون MetaTrader)."""

from __future__ import annotations

import io
import os
import sys
import tarfile
import time
import zipfile
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.windows_package import CHECK_BAT, START_BAT, STOP_BAT, production_env

OUT_ZIP = ROOT / "storage" / "GOLDENSHIELD_BINANCE_DEMO.zip"
REMOTE_DIR = r"C:\GoldenShield_Binance"

EXCLUDE_DIRS = {
    ".venv",
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".cursor",
    "htmlcov",
    "tests",
    ".github",
    "saas",
    "docs",
    "agent-tools",
    "agent-transcripts",
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log", ".zip", ".tgz", ".tar", ".gz"}
EXCLUDE_FILES = {
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.prod.yml",
    ".dockerignore",
    "SESSION_STATE.md",
    "pytest.ini",
    "CHAT_HISTORY_FIX_AR.md",
    "00_TEST_MT5.bat",
    "00_فحص_MT5.bat",
    "00_اختبار_MT5.bat",
}
EXCLUDE_NAME_SUBSTR = (
    "test_mt5",
    "mt5_connect",
    "GOLDENSHIELD_MT5",
    "send_windows_zip",
    "send_simple_windows",
    "send_update_with_start",
    "generate_project",
    "generate_detailed",
)


README = """GoldenShield — Binance Demo ONLY (full package + Cognitive Hedge)
====================================================
This package opens trades on Binance Spot Demo only.
No MetaTrader / no XM / no forex / no real-money Live account.

INSTALL on Windows:
1) Delete any old package folders
2) Extract ALL files to:  C:\\GoldenShield_Binance
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
"""

def _bat(text: str) -> bytes:
    """ملفات CMD يجب أن تكون CRLF + ASCII بدون BOM."""
    cleaned = (
        text.replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("—", "-")
        .replace("–", "-")
        .replace("“", '"')
        .replace("”", '"')
        .replace("…", "...")
    )
    return cleaned.replace("\n", "\r\n").encode("ascii", "replace")


START_BINANCE = r"""@echo off
chcp 65001 >nul
title GoldenShield Binance Demo
cd /d "%~dp0"
set "PYTHONPATH=%~dp0"
set "PYTHONIOENCODING=utf-8"
echo === GoldenShield Binance Demo ===
echo Folder: %CD%
echo.
if not exist "main.py" goto :missing_main
if not exist ".env" goto :missing_env
set "GS_PY="
where py >nul 2>&1
if not errorlevel 1 set "GS_PY=py"
if not defined GS_PY (
  where python >nul 2>&1
  if not errorlevel 1 set "GS_PY=python"
)
if not defined GS_PY goto :missing_python
echo Installing requirements once...
"%GS_PY%" -m pip install -r requirements.txt
if exist "scripts\bootstrap_storage.py" "%GS_PY%" scripts\bootstrap_storage.py
echo.
echo Starting bot - keep this window open
echo.
:loop
"%GS_PY%" -u main.py
echo.
echo Bot exited - restart in 5s
timeout /t 5 /nobreak >nul
goto loop

:missing_main
echo [ERROR] main.py missing - extract ZIP fully to C:\GoldenShield_Binance
pause
exit /b 1

:missing_env
echo [ERROR] .env missing
pause
exit /b 1

:missing_python
echo [ERROR] Python not installed
pause
exit /b 1
"""

STOP_BINANCE = r"""@echo off
chcp 65001 >nul
title Stop GoldenShield Binance Demo
echo Stopping GoldenShield python main.py ...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo Done.
echo Binance Demo account stays on the exchange.
pause
"""


def should_skip(rel: Path) -> bool:
    if set(rel.parts) & EXCLUDE_DIRS:
        return True
    if rel.suffix.lower() in EXCLUDE_SUFFIXES:
        return True
    if rel.name in EXCLUDE_FILES:
        return True
    if rel.name == ".env":
        return True
    if rel.name == ".env.cognitive.example":
        return True  # يُضاف يدوياً لاحقاً مرة واحدة
    low = str(rel).lower().replace("\\", "/")
    if any(s in low for s in EXCLUDE_NAME_SUBSTR):
        return True
    # لا تضع سكربتات MT5/نشر قديمة في الحزمة
    if rel.parts[:1] == ("scripts",) and any(
        x in rel.name.lower()
        for x in (
            "mt5",
            "windows_boot",
            "send_contabo",
            "send_simple_windows",
            "send_windows_zip",
            "deploy_to_windows",
            "deploy_to_contabo",
            "force_start",
            "boot_bot",
            "promo",
            "cursor_chat",
            "composer",
        )
    ):
        return True
    # بيانات/جسور غير مستخدمة في وضع Binance Demo
    if rel.as_posix().lower() in {
        "data/mt5_market_data.py",
        "data/forex_market_data.py",
        "data/stock_market_data.py",
        "config/mt5_symbol_map.yaml",
        "execution/mt5_bridge.py",
        "scripts/test_mt5_connect.py",
        "scripts/windows_boot.py",
    }:
        return True
    return False


def load_local_env() -> dict[str, str]:
    local: dict[str, str] = {}
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return local
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        local[k.strip()] = v.strip()
    return local


def build_zip(local: dict[str, str]) -> Path:
    OUT_ZIP.parent.mkdir(parents=True, exist_ok=True)
    if OUT_ZIP.exists():
        OUT_ZIP.unlink()

    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            if should_skip(rel):
                continue
            # استبدل ملفات البدء القديمة
            if rel.name in {
                "00_START.bat",
                "00_STOP.bat",
                "00_START_KEEP_OPEN.bat",
                "00_START_VISIBLE.vbs",
                "فحص_المجلد_CHECK.bat",
                "README_BINANCE_AR.txt",
            }:
                continue
            zf.write(path, arcname=str(rel).replace("\\", "/"))

        keep_open = _bat(
            '@echo off\n'
            'cd /d "%~dp0"\n'
            'start "GoldenShield Binance Demo" /D "%~dp0" cmd.exe /k "00_START.bat"\n'
        )
        visible = (
            'Set fso = CreateObject("Scripting.FileSystemObject")\r\n'
            'Set sh = CreateObject("WScript.Shell")\r\n'
            'folder = fso.GetParentFolderName(WScript.ScriptFullName)\r\n'
            'cmd = "cmd.exe /k cd /d """ & folder & """ && title GoldenShield Binance Demo && call 00_START.bat"\r\n'
            'sh.Run cmd, 1, False\r\n'
        ).encode("ascii")
        check = _bat(CHECK_BAT)
        zf.writestr("00_START.bat", _bat(START_BINANCE))
        zf.writestr("00_STOP.bat", _bat(STOP_BINANCE))
        zf.writestr("00_START_KEEP_OPEN.bat", keep_open)
        zf.writestr("00_START_VISIBLE.vbs", visible)
        zf.writestr("فحص_المجلد_CHECK.bat", check)
        zf.writestr("README_BINANCE_AR.txt", README.replace("\n", "\r\n").encode("utf-8"))
        zf.writestr(".env", production_env(local).replace("\n", "\r\n"))
        # توثيق الركائز المعرفية (docs/ مستثناة عادة)
        cognitive_doc = ROOT / "docs" / "COGNITIVE_HEDGE_LAYERS_AR.md"
        if cognitive_doc.is_file():
            zf.writestr(
                "docs/COGNITIVE_HEDGE_LAYERS_AR.md",
                cognitive_doc.read_text(encoding="utf-8"),
            )
        cognitive_env = ROOT / ".env.cognitive.example"
        if cognitive_env.is_file():
            zf.writestr(
                ".env.cognitive.example",
                cognitive_env.read_text(encoding="utf-8"),
            )
        # نسخة آمنة بلا أسرار للأرشفة المحلية إن لزم
        zf.writestr(
            ".env.example.binance",
            production_env(
                {
                    "BINANCE_API_KEY": "",
                    "BINANCE_API_SECRET": "",
                    "TELEGRAM_TOKEN": "",
                    "TELEGRAM_CHAT_ID": "",
                    "TELEGRAM_BOT_USERNAME": "GoldenShield_2026_bot",
                    "TELEGRAM_BACKUP_CHANNEL_ID": "",
                }
            ),
        )
    return OUT_ZIP


def deploy_to_vps(zip_path: Path) -> int:
    host = os.environ.get("WIN_HOST", "")
    user = os.environ.get("WIN_USER", "")
    password = os.environ.get("WIN_PASSWORD", "")
    if not (host and user and password):
        print("SKIP_DEPLOY: no WIN_* credentials")
        return 0

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=user, password=password, timeout=45, allow_agent=False, look_for_keys=False)

    def run(cmd: str, timeout: int = 300) -> str:
        _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        text = (out + ("\n" + err if err.strip() else "")).strip()
        safe = text[:3000].encode("ascii", "replace").decode("ascii")
        print(f"[{code}] {safe}\n")
        return text

    # أوقف البوت القديم
    run(
        "powershell -NoProfile -Command "
        "\"Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\\.py' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }; "
        "schtasks /End /TN GoldenShieldBotVisible 2>$null; "
        "Start-Sleep -Seconds 2\""
    )

    run(f'powershell -NoProfile -Command "New-Item -ItemType Directory -Force -Path \'{REMOTE_DIR}\',\'{REMOTE_DIR}\\storage\\logs\',\'{REMOTE_DIR}\\storage\\runtime\',\'{REMOTE_DIR}\\storage\\db\' | Out-Null"')

    remote_zip = REMOTE_DIR + r"\_binance_demo.zip"
    sftp = ssh.open_sftp()
    print(f"UPLOAD {zip_path} -> {remote_zip} ({zip_path.stat().st_size/1024/1024:.1f} MB)")
    sftp.put(str(zip_path), remote_zip.replace("\\", "/"))
    sftp.close()

    # استخرج فوق المجلد النظيف
    run(
        "powershell -NoProfile -Command "
        f"\"Set-Location '{REMOTE_DIR}'; "
        "if (Test-Path '_extract') { Remove-Item '_extract' -Recurse -Force }; "
        "New-Item -ItemType Directory -Force -Path '_extract' | Out-Null; "
        "Expand-Archive -Path '_binance_demo.zip' -DestinationPath '_extract' -Force; "
        "Copy-Item -Path '_extract\\*' -Destination '.' -Recurse -Force; "
        "Remove-Item '_extract' -Recurse -Force; Remove-Item '_binance_demo.zip' -Force -EA SilentlyContinue; "
        "Remove-Item 'storage\\runtime\\user_stopped.flag' -Force -EA SilentlyContinue; "
        "Get-ChildItem | Select-Object Name | Format-Table -AutoSize\"",
        timeout=600,
    )

    # ثبّت المتطلبات وشغّل
    py = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"
    run(
        "powershell -NoProfile -Command "
        f"\"Set-Location '{REMOTE_DIR}'; & '{py}' -m pip install -r requirements.txt\"",
        timeout=900,
    )
    run(
        "powershell -NoProfile -Command "
        f"\"if (Test-Path '{REMOTE_DIR}\\scripts\\bootstrap_storage.py') {{ Set-Location '{REMOTE_DIR}'; & '{py}' scripts\\bootstrap_storage.py }}\""
    )

    # مهمة مجدولة على المسار النظيف بدون مسافات
    run("schtasks /Delete /TN GoldenShieldBotVisible /F")
    run(
        "powershell -NoProfile -Command "
        f"\"$tr='cmd.exe /c cd /d {REMOTE_DIR} && \\\"{py}\\\" -u main.py >> storage\\logs\\bot_stdout.log 2>&1'; "
        "schtasks /Create /TN GoldenShieldBotVisible /TR $tr /SC ONCE /ST 00:00 /RL HIGHEST /F; "
        "schtasks /Run /TN GoldenShieldBotVisible\""
    )
    time.sleep(12)
    proc = run(
        "powershell -NoProfile -Command "
        "\"Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\\.py' } | "
        "Select-Object ProcessId,CommandLine | Format-List\""
    )
    run(
        "powershell -NoProfile -Command "
        f"\"Set-Location '{REMOTE_DIR}'; & '{py}' -c \\\"from config.settings import load_settings; s=load_settings(reload=True); "
        "print('mt5',s.mt5_enabled); print('mode',s.execution_mode); print('backend',s.execution_backend); print('demo',s.binance_demo_trading)\\\"\""
    )

    # حدّث junction C:\GSBot ليشير للحزمة الجديدة
    run(
        "powershell -NoProfile -Command "
        f"\"if (Test-Path 'C:\\GSBot') {{ cmd /c rmdir C:\\GSBot }}; cmd /c mklink /J C:\\GSBot '{REMOTE_DIR}'\""
    )

    ssh.close()
    if "ProcessId" not in proc:
        print("DEPLOYED_BUT_NOT_RUNNING")
        return 1
    print("DEPLOY_OK", REMOTE_DIR)
    return 0


def main() -> int:
    load_dotenv(ROOT / ".env", override=True)
    local = load_local_env()
    zip_path = build_zip(local)
    print("ZIP=", zip_path, f"({zip_path.stat().st_size/1024/1024:.1f} MB)")

    # انسخ أيضاً ملفات START المحلية لتطابق الحزمة
    (ROOT / "00_START.bat").write_text(START_BINANCE, encoding="utf-8")
    (ROOT / "00_STOP.bat").write_text(STOP_BINANCE, encoding="utf-8")
    (ROOT / "فحص_المجلد_CHECK.bat").write_text(CHECK_BAT, encoding="utf-8")
    (ROOT / "README_BINANCE_AR.txt").write_text(README, encoding="utf-8")
    print("LOCAL_START_FILES_UPDATED")

    return deploy_to_vps(zip_path)


if __name__ == "__main__":
    raise SystemExit(main())
