"""نظّف حزم التشغيل القديمة من السيرفر وثبّت حزمة كاملة جديدة داخل Downloads."""
from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".cursor",
    "htmlcov",
    "node_modules",
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log"}
EXCLUDE_FILES = {"storage/db/goldenshield.db"}


def _build_env_text() -> str:
    local: dict[str, str] = {}
    env_path = ROOT / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            local[k.strip()] = v.strip()

    desired = {
        "ENV": local.get("ENV", "production"),
        "EXECUTION_MODE": "live",
        "EXECUTION_BACKEND": "binance",
        "BINANCE_DEMO_TRADING": "true",
        "MT5_ENABLED": "false",
        "BOT_FORCE_ACTIVE": "true",
        "NO_SLEEP_MODE": "true",
        "LOOP_INTERVAL_SECONDS": "4",
        "TELEGRAM_LIVE_SIGNALS": "true",
        "TELEGRAM_LIVE_SIGNALS_SECONDS": "4",
        "TELEGRAM_LIVE_POSITIONS_SECONDS": "3",
        "HYBRID_SIGNAL_MODE": "true",
        "AUTO_ENTRY_MIN_PERCENT": "90",
        "TELEGRAM_SIGNAL_MIN_PERCENT": "70",
        "MANUAL_ENTRY_REQUIRED": "false",
        "ENTERPRISE_PIPELINE_ENABLED": "true",
        "SSOT_SYNC_ENABLED": "true",
        "POST_MORTEM_ENGINE_ACTIVE": "true",
        "CIRCUIT_BREAKER_MAX_LOSSES": "3",
        "PROJECT_REFERENCE_CAPITAL": "5000",
        "PROJECT_MIN_TRADE_NOTIONAL": "25",
        "PROJECT_MIN_EXCHANGE_NOTIONAL": "5",
        "DB_PATH": "storage/db/goldenshield.db",
        "BINANCE_API_KEY": local.get("BINANCE_API_KEY", ""),
        "BINANCE_API_SECRET": local.get("BINANCE_API_SECRET", ""),
        "BINANCE_API_KEY_2": local.get("BINANCE_API_KEY_2", ""),
        "BINANCE_API_SECRET_2": local.get("BINANCE_API_SECRET_2", ""),
        "TELEGRAM_TOKEN": local.get("TELEGRAM_TOKEN", ""),
        "TELEGRAM_BOT_USERNAME": local.get("TELEGRAM_BOT_USERNAME", "GoldenShield_2026_bot"),
        "TELEGRAM_CHAT_ID": local.get("TELEGRAM_CHAT_ID", ""),
        "TELEGRAM_BACKUP_CHANNEL_ID": local.get("TELEGRAM_BACKUP_CHANNEL_ID", ""),
        "WIN_HOST": local.get("WIN_HOST", ""),
        "WIN_USER": local.get("WIN_USER", "Administrator"),
        "WIN_PASSWORD": local.get("WIN_PASSWORD", ""),
    }

    lines: list[str] = []
    seen: set[str] = set()
    if env_path.is_file():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k = line.split("=", 1)[0].strip()
            if k in desired:
                lines.append(f"{k}={desired[k]}")
                seen.add(k)
            else:
                lines.append(raw)
                seen.add(k)
    for k, v in desired.items():
        if k not in seen:
            lines.append(f"{k}={v}")
    return "\n".join(lines) + "\n"


def _should_include(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    rel_str = str(rel).replace("\\", "/")
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return False
    if rel_str in EXCLUDE_FILES:
        return False
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    if "storage" in rel.parts and path.suffix.lower() in {".db", ".zip"}:
        return False
    return True


def build_zip() -> Path:
    out_dir = ROOT / "storage"
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / "goldenshield_server_downloads_package.zip"
    if zip_path.exists():
        zip_path.unlink()

    env_text = _build_env_text()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if not _should_include(path):
                continue
            rel = path.relative_to(ROOT)
            if rel.name == ".env":
                continue
            zf.write(path, str(rel).replace("\\", "/"))
        zf.writestr(".env", env_text)
        zf.writestr(
            "INSTALL_README.txt",
            (
                "GoldenShield clean server package\n\n"
                "Target folder: C:\\Users\\Administrator\\Downloads\\GoldenShield\n"
                "Demo mode: Binance Demo enabled\n"
                "Launcher entrypoint: START_BOT.bat\n"
                "Live signals window: BOT_WINDOW.bat\n"
                "Pulse mode: 4 seconds\n"
                "Telegram signals screen shows ready + WAIT entries\n"
            ),
        )
    return zip_path


REMOTE_CLEAN_PS = r"""
$ErrorActionPreference='Continue'
$downloads='C:\Users\Administrator\Downloads'
$desktop='C:\Users\Administrator\Desktop'
$public='C:\Users\Public\Desktop'
$root='C:\GoldenShield_Binance'

Write-Output '=== REMOVE OLD DOWNLOAD PACKAGES ==='
Get-ChildItem $downloads -Force -ErrorAction SilentlyContinue | ForEach-Object {
  if ($_.Name -match '(?i)goldenshield') {
    try {
      Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
      Write-Output ('REMOVED_DOWNLOAD ' + $_.Name)
    } catch {
      Write-Output ('REMOVE_SKIP ' + $_.Name)
    }
  }
}

Write-Output '=== REMOVE OLD DESKTOP FILES ==='
foreach($desk in @($desktop,$public)){
  if(-not (Test-Path $desk)){ continue }
  Get-ChildItem $desk -Force -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.Name -match '^(START_BOT|REST_BOT|STOP_BOT|BOT_WINDOW|00_LIVE_CONSOLE|run_official_bot)\.(bat|ps1|zip)$') {
      Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
      Write-Output ('REMOVED_DESKTOP ' + $_.Name + ' -> ' + $desk)
    }
  }
}

Write-Output '=== REMOVE OLD ROOT LAUNCHERS ==='
foreach($name in @(
  'START_BOT.bat','REST_BOT.bat','STOP_BOT.bat','BOT_WINDOW.bat','BOT_WINDOW.ps1',
  '00_LIVE_CONSOLE.bat','run_official_bot.bat','run_official_bot.ps1','run.bat','00_START.bat','00_START_KEEP_OPEN.bat'
)){
  $p = Join-Path $root $name
  if(Test-Path $p){
    Remove-Item $p -Force -ErrorAction SilentlyContinue
    Write-Output ('REMOVED_ROOT ' + $name)
  }
}
"""

REMOTE_EXTRACT_PS = r"""
$ErrorActionPreference='Stop'
$downloads='C:\Users\Administrator\Downloads'
$zip=Join-Path $downloads 'goldenshield_server_downloads_package.zip'
$target=Join-Path $downloads 'GoldenShield'
if(Test-Path $target){
  Remove-Item $target -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Path $target -Force | Out-Null
Expand-Archive -Path $zip -DestinationPath $target -Force

Write-Output '=== VERIFY NEW PACKAGE ==='
foreach($name in @('START_BOT.bat','REST_BOT.bat','STOP_BOT.bat','BOT_WINDOW.bat','run_official_bot.ps1','.env','requirements.txt','main.py')){
  $p = Join-Path $target $name
  Write-Output ('VERIFY ' + $name + '=' + (Test-Path $p))
}
Write-Output ('PACKAGE_DIR=' + $target)
"""


def main() -> int:
    host = os.getenv("WIN_HOST", "").strip()
    user = os.getenv("WIN_USER", "").strip()
    password = os.getenv("WIN_PASSWORD", "")
    if not host or not user:
        print("Missing WIN_HOST/WIN_USER", file=sys.stderr)
        return 2

    zip_path = build_zip()
    print("PACKAGE_READY", zip_path.name, zip_path.stat().st_size)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password, timeout=45)

    sftp = client.open_sftp()
    clean_ps = r"C:\GoldenShield_Binance\storage\runtime\_clean_old_gs_packages.ps1"
    with sftp.open(clean_ps, "w") as f:
        f.write(REMOTE_CLEAN_PS.encode("utf-8"))
    sftp.close()
    _i, stdout, stderr = client.exec_command(
        rf'powershell -NoProfile -ExecutionPolicy Bypass -File "{clean_ps}"',
        timeout=180,
    )
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR_CLEAN:", err[-1200:])

    sftp = client.open_sftp()
    remote_zip = r"C:\Users\Administrator\Downloads\goldenshield_server_downloads_package.zip"
    sftp.put(str(zip_path), remote_zip)
    extract_ps = r"C:\GoldenShield_Binance\storage\runtime\_extract_new_gs_package.ps1"
    with sftp.open(extract_ps, "w") as f:
        f.write(REMOTE_EXTRACT_PS.encode("utf-8"))
    sftp.close()

    _i, stdout, stderr = client.exec_command(
        rf'powershell -NoProfile -ExecutionPolicy Bypass -File "{extract_ps}"',
        timeout=300,
    )
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR_EXTRACT:", err[-1200:])

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
