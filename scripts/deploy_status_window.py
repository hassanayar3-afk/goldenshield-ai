"""نشر نافذة الحالة الظاهرة + إعادة تشغيل منظمة."""
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
    "BOT_WINDOW.bat",
    "BOT_WINDOW.ps1",
    "START_BOT.bat",
    "STOP_BOT.bat",
    "REST_BOT.bat",
    "LAUNCHERS_AR.txt",
    "scripts/_kill_gs_workers.ps1",
]

PS = r"""
$ErrorActionPreference='Continue'
$g='C:\GoldenShield_Binance'
Write-Host '=== STATUS WINDOW DEPLOY ==='

# نظّف نوافذ حالة قديمة فقط (لا تقتل البوت إن كان يعمل — سنعمل REST منظم)
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'BOT_WINDOW\.(bat|ps1)|00_LIVE_CONSOLE\.bat|نافذة الحالة|BOT STATUS' } | ForEach-Object {
  Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue
}

# تأكد من العامل المخفي + مثيل واحد
$kill=Join-Path $g 'scripts\_kill_gs_workers.ps1'
schtasks /End /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
schtasks /End /TN GoldenShieldStatusWindow /F 2>$null | Out-Null
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
Start-Sleep 8

# افتح نافذة حالة ظاهرة واحدة على سطح المكتب
$win=Join-Path $g 'BOT_WINDOW.bat'
schtasks /Delete /TN GoldenShieldStatusWindow /F 2>$null | Out-Null
schtasks /Create /TN GoldenShieldStatusWindow /TR "`"$win`"" /SC ONCE /ST 00:00 /RL HIGHEST /IT /F | Out-Null
schtasks /Run /TN GoldenShieldStatusWindow | Out-Null
Start-Sleep 4

$mains=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\.py' })
$wins=@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'BOT_WINDOW\.(bat|ps1)' })
Write-Host ('MAIN_COUNT=' + $mains.Count)
Write-Host ('STATUS_WINDOW_COUNT=' + $wins.Count)
foreach($p in $mains){ Write-Host ('MAIN_PID=' + $p.ProcessId) }
foreach($p in $wins){ Write-Host ('WIN_PID=' + $p.ProcessId) }
# عيّنة محتوى متوقع من السكربت
$okFiles = (Test-Path (Join-Path $g 'BOT_WINDOW.ps1')) -and (Test-Path (Join-Path $g 'BOT_WINDOW.bat'))
Write-Host ('FILES_OK=' + $okFiles)
if($mains.Count -eq 1 -and $wins.Count -ge 1 -and $okFiles){ Write-Host 'STATUS_WINDOW_OK' } else { Write-Host 'STATUS_WINDOW_CHECK' }
"""


def main() -> int:
    if not HOST or not USER:
        print("Missing WIN_HOST/WIN_USER", file=sys.stderr)
        return 1
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

    remote_ps = r"C:\ProgramData\GoldenShield\_deploy_status_window.ps1"
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
