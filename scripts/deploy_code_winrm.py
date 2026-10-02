"""سحب/تحديث كود GoldenShield على VPS عبر git clone أو zip ثم إعادة تشغيل الـ daemon."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import winrm
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# مستودع عام — لا أسرار
REPO_ZIP = "https://github.com/hassanayar3-afk/goldenshield-ai/archive/refs/heads/main.zip"

PS = rf"""
$ErrorActionPreference = 'Continue'
$bot = 'C:\GoldenShield_Binance'
$arch = Join-Path $bot 'storage\runtime\_archived_launchers'
New-Item -ItemType Directory -Force -Path $arch | Out-Null

# احتفظ بملفات التشغيل والبيانات
$keepNames = @(
  'start_bot.bat','restart_bot.bat','stop_bot.bat','GS_START.bat','GS_RESTART.bat','GS_STOP.bat',
  '00_START.bat','00_STOP.bat','REST_BOT.bat','run_bot_visible.cmd','live_console.ps1','gs_daemon.ps1',
  'BOT_WINDOW.bat','BOT_WINDOW.ps1','LAUNCHERS_AR.txt','.env','storage'
)
$staging = Join-Path $env:TEMP ('gs_launch_staging_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $staging | Out-Null
foreach ($n in $keepNames) {{
  $src = Join-Path $bot $n
  if (Test-Path $src) {{
    Copy-Item -Path $src -Destination (Join-Path $staging $n) -Recurse -Force
  }}
}}

$zip = Join-Path $env:TEMP 'goldenshield_main.zip'
$extract = Join-Path $env:TEMP 'goldenshield_main_extract'
Remove-Item $zip,$extract -Recurse -Force -EA SilentlyContinue
New-Item -ItemType Directory -Force -Path $extract | Out-Null
Write-Host 'DOWNLOAD_ZIP'
Invoke-WebRequest -Uri '{REPO_ZIP}' -OutFile $zip -UseBasicParsing
Expand-Archive -Path $zip -DestinationPath $extract -Force
$inner = Get-ChildItem $extract -Directory | Select-Object -First 1
if (-not $inner) {{ Write-Host 'EXTRACT_FAIL'; exit 2 }}

Get-ChildItem $bot -Force | Where-Object {{ $_.Name -notin $keepNames }} | Remove-Item -Recurse -Force -EA SilentlyContinue
Copy-Item -Path (Join-Path $inner.FullName '*') -Destination $bot -Recurse -Force

foreach ($n in $keepNames) {{
  $saved = Join-Path $staging $n
  if (Test-Path $saved) {{
    $dest = Join-Path $bot $n
    if (Test-Path $dest) {{ Remove-Item $dest -Recurse -Force -EA SilentlyContinue }}
    Copy-Item -Path $saved -Destination $dest -Recurse -Force
  }}
}}
Remove-Item $staging,$zip,$extract -Recurse -Force -EA SilentlyContinue

Write-Host ('HAS_MAIN=' + (Test-Path (Join-Path $bot 'main.py')))
Write-Host ('HAS_ENV=' + (Test-Path (Join-Path $bot '.env')))

$py = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
if (-not (Test-Path $py)) {{ $py = 'py' }}
Set-Location $bot
& $py -m pip install -r requirements.txt -q
Write-Host 'PIP_OK'

powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $bot 'scripts\gs_kill_all.ps1')
Start-Sleep -Seconds 2
$flag = Join-Path $bot 'storage\runtime\user_stopped.flag'
if (Test-Path $flag) {{ Remove-Item $flag -Force }}
schtasks /End /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
try {{
  Start-ScheduledTask -TaskName 'GoldenShieldBotOfficial' -EA Stop
}} catch {{
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = 'powershell.exe'
  $psi.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$bot\gs_daemon.ps1`""
  $psi.WorkingDirectory = $bot
  $psi.UseShellExecute = $true
  $psi.WindowStyle = 'Hidden'
  [System.Diagnostics.Process]::Start($psi) | Out-Null
}}
Start-Sleep -Seconds 12
$procs = @(Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -and $_.CommandLine -match 'main\.py' }})
Write-Host ('BOT_PROCS=' + $procs.Count)
if (Test-Path (Join-Path $bot 'storage\logs\bot_stderr.log')) {{
  Write-Host '--- STDERR ---'
  Get-Content (Join-Path $bot 'storage\logs\bot_stderr.log') -Tail 15 -EA SilentlyContinue
}}
Write-Host 'CODE_DEPLOY_OK'
"""


def main() -> int:
    load_dotenv(ROOT / ".env", override=True)
    host = (os.getenv("WIN_HOST") or "").strip()
    user = (os.getenv("WIN_USER") or "Administrator").strip()
    password = os.getenv("WIN_PASSWORD") or ""
    if not (host and password):
        print("missing WIN_*")
        return 1
    session = winrm.Session(
        f"http://{host}:5985/wsman",
        auth=(user, password),
        transport="basic",
        server_cert_validation="ignore",
        read_timeout_sec=600,
        operation_timeout_sec=300,
    )
    staging = ROOT / "storage" / "runtime" / "_winrm_code_deploy.ps1"
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_text(PS, encoding="utf-8")

    from deploy_visible_winrm import _upload_file

    remote_ps = r"C:\Users\Public\gs_code_deploy.ps1"
    _upload_file(session, staging, remote_ps)
    print("UP code_deploy.ps1")
    r = session.run_cmd(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote_ps}"'
    )
    print((r.std_out or b"").decode("utf-8", errors="replace"))
    err = (r.std_err or b"").decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err[-2000:])
    return 0 if r.status_code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
