"""نشر حزمة التشغيل المرئية الجديدة إلى C:\\GoldenShield_Binance وتطهير القديمة."""
from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

REMOTE = r"C:\GoldenShield_Binance"

UPLOAD = [
    "start_bot.bat",
    "restart_bot.bat",
    "stop_bot.bat",
    "GS_START.bat",
    "GS_RESTART.bat",
    "GS_STOP.bat",
    "00_START.bat",
    "00_STOP.bat",
    "REST_BOT.bat",
    "run_bot_visible.cmd",
    "live_console.ps1",
    "gs_daemon.ps1",
    "BOT_WINDOW.bat",
    "BOT_WINDOW.ps1",
    "LAUNCHERS_AR.txt",
    "scripts/gs_common_env.cmd",
    "scripts/gs_kill_all.ps1",
    "operations/console_pulse.py",
    "operations/single_instance.py",
]

# Archive/remove scattered legacy launchers on server (keep data)
ARCHIVE_NAMES = [
    "00_START_KEEP_OPEN.bat",
    "00_START_VISIBLE.vbs",
    "00_LIVE_CONSOLE.bat",
    "run_official_bot.bat",
    "run_official_bot.ps1",
]

PS = r"""
$ErrorActionPreference='Continue'
$bot='C:\GoldenShield_Binance'
$arch=Join-Path $bot 'storage\runtime\_archived_launchers'
New-Item -ItemType Directory -Force -Path $arch | Out-Null
$move=@(
  '00_START_KEEP_OPEN.bat','00_START_VISIBLE.vbs','00_LIVE_CONSOLE.bat',
  'run_official_bot.bat','run_official_bot.ps1'
)
foreach($n in $move){
  $p=Join-Path $bot $n
  if(Test-Path $p){
    Move-Item $p (Join-Path $arch $n) -Force
    Write-Host ("ARCHIVED "+$n)
  }
}
# Patch .env no-sleep / binance / force active
$envp=Join-Path $bot '.env'
if(Test-Path $envp){
  $map=@{
    'NO_SLEEP_MODE'='true'
    'LOOP_INTERVAL_SECONDS'='4'
    'TELEGRAM_LIVE_SIGNALS'='true'
    'TELEGRAM_LIVE_SIGNALS_SECONDS'='4'
    'TELEGRAM_LIVE_POSITIONS_SECONDS'='3'
    'BOT_FORCE_ACTIVE'='true'
    'EXECUTION_BACKEND'='binance'
    'SSOT_SYNC_ENABLED'='true'
    'ENTERPRISE_PIPELINE_ENABLED'='true'
    'BINANCE_DEMO_TRADING'='true'
  }
  $lines=Get-Content $envp -Encoding UTF8
  $seen=@{}
  $out=@()
  foreach($line in $lines){
    if($line -match '^\s*#' -or $line -notmatch '='){ $out += $line; continue }
    $k=($line -split '=',2)[0].Trim()
    if($map.ContainsKey($k)){ $out += "$k=$($map[$k])"; $seen[$k]=1 }
    elseif($k -match '^(MT5_|BOT_AUTO_SYNC_MT5)'){ continue }
    else { $out += $line }
  }
  foreach($k in $map.Keys){ if(-not $seen.ContainsKey($k)){ $out += "$k=$($map[$k])" } }
  $utf8=New-Object System.Text.UTF8Encoding $false
  [System.IO.File]::WriteAllLines($envp, $out, $utf8)
  Write-Host 'ENV_NO_SLEEP_OK'
}
# Kill old + start new visible package
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $bot 'scripts\gs_kill_all.ps1')
Start-Sleep -Seconds 2
# Ensure hidden worker files are gone
foreach($n in @('run_official_bot.ps1','run_official_bot.bat','00_START_KEEP_OPEN.bat','00_LIVE_CONSOLE.bat')){
  $p=Join-Path $bot $n
  if(Test-Path $p){
    $arch=Join-Path $bot 'storage\runtime\_archived_launchers'
    New-Item -ItemType Directory -Force -Path $arch | Out-Null
    Move-Item $p (Join-Path $arch $n) -Force
    Write-Host ("ARCHIVED "+$n)
  }
}
schtasks /Delete /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
schtasks /Create /TN GoldenShieldBotOfficial /TR "cmd.exe /c start \"GoldenShield BOT LIVE\" /D \"$bot\" cmd.exe /k call \"$bot\run_bot_visible.cmd\"" /SC ONSTART /RL HIGHEST /F | Out-Null
$flag=Join-Path $bot 'storage\runtime\user_stopped.flag'
if(Test-Path $flag){ Remove-Item $flag -Force }
$lock=Join-Path $bot 'storage\runtime\bot_instance.lock'
if(Test-Path $lock){ Remove-Item $lock -Force }
if(Test-Path 'C:\ProgramData\GoldenShield\bot_instance.lock'){ Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue }
powercfg -change -standby-timeout-ac 0 | Out-Null
powercfg -change -hibernate-timeout-ac 0 | Out-Null
# Durable daemon (single instance, no-sleep). Visible CMDs: run start_bot.bat from RDP desktop.
$daemon = Join-Path $bot 'gs_daemon.ps1'
Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',$daemon -WorkingDirectory $bot -WindowStyle Hidden
Start-Sleep -Seconds 10

# Pulse board for RDP session if available
try {
  $actionPulse = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoExit -NoProfile -ExecutionPolicy Bypass -File `"$bot\live_console.ps1`"" -WorkingDirectory $bot
  $principal = New-ScheduledTaskPrincipal -UserId 'Administrator' -LogonType Interactive -RunLevel Highest
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
  Unregister-ScheduledTask -TaskName 'GS_VisiblePulse' -Confirm:$false -EA SilentlyContinue
  Unregister-ScheduledTask -TaskName 'GS_VisibleBot' -Confirm:$false -EA SilentlyContinue
  Register-ScheduledTask -TaskName 'GS_VisiblePulse' -Action $actionPulse -Principal $principal -Settings $settings -Force | Out-Null
  Start-ScheduledTask -TaskName 'GS_VisiblePulse' -EA SilentlyContinue
} catch {
  Write-Host ('VISIBLE_TASK_WARN ' + $_.Exception.Message)
}

$procs=@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'main\.py' })
Write-Host ('BOT_PROCS=' + $procs.Count)
foreach($p in $procs){ Write-Host ('PID=' + $p.ProcessId) }
$daemonN=@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'gs_daemon\.ps1' })
Write-Host ('DAEMON=' + $daemonN.Count)
Write-Host ('HIDDEN_WORKER=' + (Test-Path (Join-Path $bot 'run_official_bot.ps1')))
Write-Host ('START_BAT=' + (Test-Path (Join-Path $bot 'start_bot.bat')))
Write-Host ('RESTART_BAT=' + (Test-Path (Join-Path $bot 'restart_bot.bat')))
Write-Host ('STOP_BAT=' + (Test-Path (Join-Path $bot 'stop_bot.bat')))
Write-Host ('CORE_CMD=' + (Test-Path (Join-Path $bot 'run_bot_visible.cmd')))
Write-Host ('PULSE_PS1=' + (Test-Path (Join-Path $bot 'live_console.ps1')))
Write-Host ('DAEMON_PS1=' + (Test-Path $daemon))
Write-Host 'PACKAGE_DEPLOY_OK'
"""


def sftp_mkdirs(sftp: paramiko.SFTPClient, remote_dir: str) -> None:
    parts = remote_dir.replace("/", "\\").split("\\")
    cur = parts[0] + "\\" if parts[0].endswith(":") else parts[0]
    for part in parts[1:]:
        if not part:
            continue
        cur = cur.rstrip("\\") + "\\" + part
        try:
            sftp.stat(cur)
        except OSError:
            try:
                sftp.mkdir(cur)
            except OSError:
                pass


def main() -> int:
    host = os.getenv("WIN_HOST")
    user = os.getenv("WIN_USER")
    password = os.getenv("WIN_PASSWORD")
    if not (host and user and password):
        print("missing WIN_*")
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password, timeout=45, allow_agent=False, look_for_keys=False)
    sftp = client.open_sftp()
    for rel in UPLOAD:
        local = ROOT / rel
        if not local.exists():
            print("SKIP", rel)
            continue
        remote = REMOTE + "\\" + rel.replace("/", "\\")
        sftp_mkdirs(sftp, str(Path(remote).parent))
        sftp.put(str(local), remote)
        print("UP", rel)
    sftp.close()

    remote_ps = r"C:\Users\Public\gs_deploy_visible_pkg.ps1"
    sftp = client.open_sftp()
    with sftp.file(remote_ps, "w") as fh:
        fh.write(PS)
    sftp.close()
    _i, stdout, stderr = client.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote_ps}"',
        timeout=180,
    )
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    try:
        print(out)
    except UnicodeEncodeError:
        print(out.encode("ascii", "replace").decode("ascii"))
    if err.strip():
        print("STDERR:", err[-1500:])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
