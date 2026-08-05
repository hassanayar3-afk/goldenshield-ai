"""نظف ملفات تشغيل البوت من السيرفر وأرسل حزمة التشغيل إلى تيليجرام."""
from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

import paramiko
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

SERVER_ROOT = r"C:\GoldenShield_Binance"
PACKAGE_FILES = [
    "START_BOT.bat",
    "REST_BOT.bat",
    "STOP_BOT.bat",
    "BOT_WINDOW.bat",
    "BOT_WINDOW.ps1",
    "00_LIVE_CONSOLE.bat",
    "run_official_bot.bat",
    "run_official_bot.ps1",
]

SERVER_CLEAN_PS = r"""
$ErrorActionPreference='Continue'
$root='C:\GoldenShield_Binance'
$admin='C:\Users\Administrator\Desktop'
$pub='C:\Users\Public\Desktop'
$files=@(
  'START_BOT.bat',
  'REST_BOT.bat',
  'STOP_BOT.bat',
  'BOT_WINDOW.bat',
  'BOT_WINDOW.ps1',
  '00_LIVE_CONSOLE.bat',
  'run_official_bot.bat',
  'run_official_bot.ps1'
)
Write-Output '=== STOP TASKS ==='
schtasks /End /TN 'GoldenShieldBotOfficial' /F 2>$null
schtasks /Delete /TN 'GoldenShieldBotOfficial' /F 2>$null
schtasks /End /TN 'GoldenShieldLiveConsole' /F 2>$null
schtasks /Delete /TN 'GoldenShieldLiveConsole' /F 2>$null
schtasks /End /TN 'GoldenShieldStatusWindow' /F 2>$null
schtasks /Delete /TN 'GoldenShieldStatusWindow' /F 2>$null
Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object {
  $_.CommandLine -and ($_.CommandLine -match 'main\.py|run_official_bot|BOT_WINDOW|00_LIVE_CONSOLE')
} | ForEach-Object {
  Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue
  Write-Output ('KILLED_PID ' + $_.ProcessId)
}
Start-Sleep -Seconds 2

Write-Output '=== REMOVE ROOT FILES ==='
foreach($name in $files){
  $p=Join-Path $root $name
  if(Test-Path $p){
    Remove-Item $p -Force -EA SilentlyContinue
    Write-Output ('REMOVED_ROOT ' + $name)
  }
}

Write-Output '=== REMOVE DESKTOP FILES ==='
foreach($desk in @($admin,$pub)){
  if(-not (Test-Path $desk)){ continue }
  foreach($name in $files){
    $p=Join-Path $desk $name
    if(Test-Path $p){
      Remove-Item $p -Force -EA SilentlyContinue
      Write-Output ('REMOVED_DESKTOP ' + $name + ' -> ' + $desk)
    }
  }
}

Write-Output '=== VERIFY CLEAN ==='
foreach($name in $files){
  $rootHit = Test-Path (Join-Path $root $name)
  $adminHit = Test-Path (Join-Path $admin $name)
  $pubHit = Test-Path (Join-Path $pub $name)
  Write-Output ('VERIFY ' + $name + ' root=' + $rootHit + ' admin=' + $adminHit + ' public=' + $pubHit)
}
"""


def build_package() -> Path:
    out_dir = ROOT / "storage"
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / "goldenshield_launcher_package.zip"
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in PACKAGE_FILES:
            path = ROOT / rel
            if path.is_file():
                zf.write(path, rel)
        zf.writestr(
            "INSTALL_README.txt",
            (
                "GoldenShield launcher package\n\n"
                "1. Copy these files into C:\\GoldenShield_Binance\\\n"
                "2. Keep your existing project files and .env as-is.\n"
                "3. Run START_BOT.bat to start the bot.\n"
                "4. Use REST_BOT.bat to restart.\n"
                "5. Use STOP_BOT.bat to stop.\n"
                "6. Use BOT_WINDOW.bat to watch live signals.\n"
            ),
        )
    return zip_path


def clean_server() -> None:
    host = os.getenv("WIN_HOST", "").strip()
    user = os.getenv("WIN_USER", "").strip()
    password = os.getenv("WIN_PASSWORD", "")
    if not host or not user:
        raise RuntimeError("Missing WIN_HOST/WIN_USER")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password, timeout=45)

    sftp = client.open_sftp()
    remote = SERVER_ROOT + r"\storage\runtime\_clean_launchers_only.ps1"
    with sftp.open(remote, "w") as f:
        f.write(SERVER_CLEAN_PS.encode("utf-8"))
    sftp.close()

    _i, stdout, stderr = client.exec_command(
        rf'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
        timeout=120,
    )
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err[-1200:])
    client.close()


def send_telegram(zip_path: Path) -> None:
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        raise RuntimeError("Telegram config missing")

    caption = (
        "حزمة تشغيل GoldenShield فقط\n"
        "تحتوي ملفات START/REST/STOP/BOT_WINDOW والعامل الرسمي.\n"
        "فكّها داخل C:\\GoldenShield_Binance ثم شغّل START_BOT.bat."
    )
    with zip_path.open("rb") as fh:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data={"chat_id": chat, "caption": caption},
            files={"document": (zip_path.name, fh, "application/zip")},
            timeout=180,
        )
    data = response.json()
    print("TELEGRAM_SEND", response.status_code, data.get("ok"), data.get("description", "ok"))
    if not data.get("ok"):
        raise RuntimeError("Telegram send failed")


def main() -> int:
    try:
        zip_path = build_package()
        print("PACKAGE_READY", zip_path.name, zip_path.stat().st_size)
        clean_server()
        send_telegram(zip_path)
        print("DONE")
        return 0
    except Exception as exc:  # noqa: BLE001
        print("ERROR", str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
