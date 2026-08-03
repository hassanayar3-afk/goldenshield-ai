"""Deploy live-signals CMD board (signals only, not trades)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
HOST = os.getenv("WIN_HOST", "").strip()
USER = os.getenv("WIN_USER", "").strip()
PASSWORD = os.getenv("WIN_PASSWORD", "")
KEEP = r"C:\GoldenShield_Binance"

UPLOADS = [
    "operations/dashboard_templates.py",
    "operations/telegram_dashboard.py",
    "BOT_WINDOW.bat",
    "BOT_WINDOW.ps1",
    "START_BOT.bat",
    "STOP_BOT.bat",
    "REST_BOT.bat",
    "scripts/_kill_gs_workers.ps1",
]

PS = r"""
$ErrorActionPreference='Continue'
$g='C:\GoldenShield_Binance'
Write-Host '=== SIGNALS BOARD DEPLOY ==='

Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -and ($_.CommandLine -match 'BOT_WINDOW\.(bat|ps1)|00_LIVE_CONSOLE|LIVE SIGNALS|BOT STATUS|نافذة الحالة')
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
schtasks /End /TN GoldenShieldStatusWindow /F 2>$null | Out-Null
schtasks /End /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
$kill=Join-Path $g 'scripts\_kill_gs_workers.ps1'
if(Test-Path $kill){ powershell -NoProfile -ExecutionPolicy Bypass -File $kill }
Start-Sleep 2
Remove-Item (Join-Path $g 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $g 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue

$worker=Join-Path $g 'run_official_bot.ps1'
$tr=('powershell.exe -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $worker)
schtasks /Delete /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
schtasks /Create /TN GoldenShieldBotOfficial /TR $tr /SC ONSTART /RL HIGHEST /F | Out-Null
try { $t=Get-ScheduledTask GoldenShieldBotOfficial; $t.Settings.Hidden=$true; $t.Settings.ExecutionTimeLimit='PT0S'; $t|Set-ScheduledTask|Out-Null } catch {}
schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
Start-Sleep 12

$board=Join-Path $g 'storage\runtime\signals_board.txt'
$deadline=(Get-Date).AddSeconds(45)
while((Get-Date) -lt $deadline -and -not (Test-Path $board)){ Start-Sleep 2 }
Write-Host ('BOARD_EXISTS=' + (Test-Path $board))
if(Test-Path $board){
  Write-Host 'BOARD_SAMPLE:'
  Get-Content $board -Encoding UTF8 -TotalCount 16
}

$win=Join-Path $g 'BOT_WINDOW.bat'
$future=(Get-Date).AddMinutes(3).ToString('HH:mm')
schtasks /Delete /TN GoldenShieldStatusWindow /F 2>$null | Out-Null
schtasks /Create /TN GoldenShieldStatusWindow /TR "`"$win`"" /SC ONCE /ST $future /RL HIGHEST /IT /F | Out-Null
schtasks /Run /TN GoldenShieldStatusWindow | Out-Null
Start-Sleep 4

$mains=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\.py' })
$wins=@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'BOT_WINDOW\.(bat|ps1)' })
Write-Host ('MAIN_COUNT=' + $mains.Count)
Write-Host ('STATUS_WINDOW_COUNT=' + $wins.Count)
if($mains.Count -eq 1 -and (Test-Path $board) -and $wins.Count -ge 1){ Write-Host 'SIGNALS_BOARD_OK' } else { Write-Host 'SIGNALS_BOARD_CHECK' }
"""


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=45, allow_agent=False, look_for_keys=False)
    sftp = ssh.open_sftp()

    def ensure_dir(remote: str) -> None:
        parts = remote.replace("/", "\\").split("\\")
        cur = parts[0] + "\\"
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

    for rel in UPLOADS:
        local = ROOT / rel
        remote = KEEP + "\\" + rel.replace("/", "\\")
        ensure_dir(str(Path(remote).parent))
        sftp.put(str(local), remote)
        print(f"UPLOADED {rel}")

    remote_ps = r"C:\ProgramData\GoldenShield\_deploy_signals_board.ps1"
    ensure_dir(r"C:\ProgramData\GoldenShield")
    with sftp.file(remote_ps, "w") as fh:
        fh.write(PS.replace("\r\n", "\n").replace("\n", "\r\n"))
    sftp.close()

    _, o, e = ssh.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote_ps}"',
        timeout=180,
    )
    out = (o.read() + e.read()).decode("utf-8", "replace")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(out)
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
