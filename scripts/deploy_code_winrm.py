"""نشر الكود على VPS عبر WinRM: git clone (مستودع خاص) + pip + إعادة تشغيل."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import winrm
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

REMOTE = r"C:\GoldenShield_Binance"
REPO = "https://github.com/hassanayar3-afk/goldenshield-ai.git"


def _gh_token() -> str:
    try:
        return subprocess.check_output(
            ["gh", "auth", "token"],
            text=True,
            timeout=20,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception as exc:
        raise SystemExit("gh auth token unavailable — run: gh auth login") from exc


def _build_ps(token: str) -> str:
    # Token stays on server script only for clone; not printed by this module.
    tok = token.replace("'", "''")
    return rf"""
$ErrorActionPreference = 'Continue'
$bot = '{REMOTE}'
$cloneRoot = Join-Path $env:TEMP ('gs_clone_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $cloneRoot | Out-Null

if (-not (Get-Command git -EA SilentlyContinue)) {{
  Write-Host 'INSTALL_GIT'
  $gexe = Join-Path $env:TEMP 'Git-Min.exe'
  Invoke-WebRequest -Uri 'https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.2/MinGit-2.47.1.2-64-bit.zip' -OutFile (Join-Path $env:TEMP 'mingit.zip') -UseBasicParsing
  Expand-Archive -Path (Join-Path $env:TEMP 'mingit.zip') -DestinationPath (Join-Path $env:TEMP 'mingit') -Force
  $gitCmd = Get-ChildItem (Join-Path $env:TEMP 'mingit') -Recurse -Filter 'git.exe' | Select-Object -First 1
  if (-not $gitCmd) {{ Write-Host 'GIT_INSTALL_FAIL'; exit 3 }}
  $env:Path = $gitCmd.DirectoryName + ';' + $env:Path
}} else {{
  Write-Host 'GIT_OK'
}}

$env:GIT_TERMINAL_PROMPT = '0'
$url = 'https://x-access-token:{tok}@github.com/hassanayar3-afk/goldenshield-ai.git'
Write-Host 'CLONE'
& git clone --depth 1 $url $cloneRoot 2>&1 | ForEach-Object {{ Write-Host $_ }}
if (-not (Test-Path (Join-Path $cloneRoot 'main.py'))) {{ Write-Host 'CLONE_FAIL'; exit 4 }}

$keep = @('storage','.env')
foreach ($name in $keep) {{
  $src = Join-Path $bot $name
  if (Test-Path $src) {{
    $bak = Join-Path $env:TEMP ('gs_keep_' + $name)
    Copy-Item $src $bak -Recurse -Force
  }}
}}

Get-ChildItem $bot -Force | Where-Object {{ $_.Name -notin $keep }} | Remove-Item -Recurse -Force -EA SilentlyContinue
Copy-Item -Path (Join-Path $cloneRoot '*') -Destination $bot -Recurse -Force
foreach ($name in $keep) {{
  $bak = Join-Path $env:TEMP ('gs_keep_' + $name)
  if (Test-Path $bak) {{
    $dest = Join-Path $bot $name
    if (Test-Path $dest) {{ Remove-Item $dest -Recurse -Force -EA SilentlyContinue }}
    Copy-Item $bak $dest -Recurse -Force
  }}
}}
Remove-Item $cloneRoot -Recurse -Force -EA SilentlyContinue

Write-Host ('HAS_MAIN=' + (Test-Path (Join-Path $bot 'main.py')))
Write-Host ('HAS_ENV=' + (Test-Path (Join-Path $bot '.env')))

$py = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
if (-not (Test-Path $py)) {{ $py = 'py' }}
Set-Location $bot
& $py -m pip install -r requirements.txt -q
Write-Host 'PIP_OK'

powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $bot 'scripts\gs_kill_all.ps1')
Start-Sleep -Seconds 2
Remove-Item (Join-Path $bot 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
schtasks /End /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
Start-ScheduledTask -TaskName 'GoldenShieldBotOfficial' -EA SilentlyContinue
if ($LASTEXITCODE -ne 0) {{
  Start-Process powershell.exe -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $bot 'gs_daemon.ps1') -WorkingDirectory $bot -WindowStyle Hidden
}}
Start-Sleep -Seconds 15
$n = @(Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -and $_.CommandLine -match 'main\.py' }}).Count
Write-Host ('BOT_PROCS=' + $n)
$err = Join-Path $bot 'storage\logs\bot_stderr.log'
if (Test-Path $err) {{ Get-Content $err -Tail 12 }}
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

    token = _gh_token()
    ps = _build_ps(token)
    staging = ROOT / "storage" / "runtime" / "_winrm_git_deploy.ps1"
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_text(ps, encoding="utf-8")

    session = winrm.Session(
        f"http://{host}:5985/wsman",
        auth=(user, password),
        transport="basic",
        server_cert_validation="ignore",
        read_timeout_sec=600,
        operation_timeout_sec=300,
    )
    from deploy_visible_winrm import _upload_file

    remote_ps = r"C:\Users\Public\gs_git_deploy.ps1"
    _upload_file(session, staging, remote_ps)
    print("UP git_deploy.ps1")
    r = session.run_cmd(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote_ps}"'
    )
    out = (r.std_out or b"").decode("utf-8", errors="replace")
    try:
        print(out)
    except UnicodeEncodeError:
        print(out.encode("ascii", "replace").decode("ascii"))
    err = (r.std_err or b"").decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err[-2000:])
    try:
        staging.unlink(missing_ok=True)
    except OSError:
        pass
    return 0 if r.status_code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
