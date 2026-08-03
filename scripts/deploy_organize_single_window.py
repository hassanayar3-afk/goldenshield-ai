"""تنظيف نوافذ VPS المكررة + نشر تشغيل مخفي بمثيلة واحدة."""
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
    "START_BOT.bat",
    "STOP_BOT.bat",
    "REST_BOT.bat",
    "run_official_bot.bat",
    "run_official_bot.ps1",
    "LAUNCHERS_AR.txt",
    "scripts/_kill_gs_workers.ps1",
    "00_START.bat",
    "00_STOP.bat",
]

PS = r"""
$ErrorActionPreference='Continue'
$g='C:\GoldenShield_Binance'
$log=Join-Path $g 'storage\logs\organize_windows.log'
function WLog($m){ $line='[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m; Add-Content $log $line; Write-Host $line }

WLog '=== ORGANIZE START ==='

# 1) أوقف المهام الزائدة
foreach($tn in @('GoldenShieldLiveConsole','GoldenShieldBotVisible','GoldenShieldBot','GoldenShieldBotBoot')){
  schtasks /End /TN $tn /F 2>$null | Out-Null
  schtasks /Change /TN $tn /DISABLE 2>$null | Out-Null
  schtasks /Delete /TN $tn /F 2>$null | Out-Null
  WLog ("disabled_deleted=$tn")
}
schtasks /End /TN GoldenShieldBotOfficial /F 2>$null | Out-Null

# 2) اقتل كل العمال المكررين
$kill=Join-Path $g 'scripts\_kill_gs_workers.ps1'
if(Test-Path $kill){
  powershell -NoProfile -ExecutionPolicy Bypass -File $kill
  WLog 'killed via _kill_gs_workers.ps1'
} else {
  Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py|run_official_bot|00_LIVE_CONSOLE' } | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue
  }
  WLog 'killed via inline'
}
Start-Sleep 3

# 3) حرر القفل فقط
$flags=@(
  (Join-Path $g 'storage\runtime\user_stopped.flag'),
  (Join-Path $g 'storage\runtime\bot_instance.lock'),
  'C:\ProgramData\GoldenShield\bot_instance.lock'
)
foreach($f in $flags){ if(Test-Path $f){ Remove-Item $f -Force -EA SilentlyContinue; WLog ("cleared=$f") } }

# 4) سجّل مهمة مخفية واحدة
$worker=Join-Path $g 'run_official_bot.ps1'
$tr=('powershell.exe -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $worker)
schtasks /Delete /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
schtasks /Create /TN GoldenShieldBotOfficial /TR $tr /SC ONSTART /RL HIGHEST /F | Out-Null
try {
  $t=Get-ScheduledTask -TaskName 'GoldenShieldBotOfficial'
  $t.Settings.Hidden=$true
  $t.Settings.ExecutionTimeLimit='PT0S'
  $t | Set-ScheduledTask | Out-Null
  WLog 'task_hidden=OK'
} catch {
  WLog ('task_hidden_warn=' + $_.Exception.Message)
}

# 5) شغّل مرة واحدة
schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
WLog 'task_run=requested'
Start-Sleep 10

# 6) تقرير الحالة
$mains=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\.py' })
$oldBat=@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'run_official_bot\.bat' })
$psWorkers=@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'run_official_bot\.ps1' })
$live=@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match '00_LIVE_CONSOLE|LIVE VIEW' })
WLog ('MAIN_COUNT=' + $mains.Count)
WLog ('OLD_BAT_COUNT=' + $oldBat.Count)
WLog ('PS_WORKER_COUNT=' + $psWorkers.Count)
WLog ('LIVE_COUNT=' + $live.Count)
foreach($p in $mains){ WLog ('MAIN_PID=' + $p.ProcessId) }
foreach($p in $oldBat){ WLog ('OLD_BAT_PID=' + $p.ProcessId) }
foreach($p in $psWorkers){ WLog ('PS_WORKER_PID=' + $p.ProcessId) }

# اختصارات سطح المكتب — الثلاثة فقط
$desk=[Environment]::GetFolderPath('Desktop')
$w=New-Object -ComObject WScript.Shell
foreach($pair in @(
  @('START BOT.lnk','START_BOT.bat'),
  @('STOP BOT.lnk','STOP_BOT.bat'),
  @('REST BOT.lnk','REST_BOT.bat')
)){
  $lnk=Join-Path $desk $pair[0]
  $sc=$w.CreateShortcut($lnk)
  $sc.TargetPath=(Join-Path $g $pair[1])
  $sc.WorkingDirectory=$g
  $sc.Save()
  WLog ('shortcut=' + $pair[0])
}
# احذف اختصارات قديمة مربكة إن وُجدت
foreach($bad in @('GoldenShield LIVE.lnk','LIVE CONSOLE.lnk','00_START.lnk','START.lnk')){
  $p=Join-Path $desk $bad
  if(Test-Path $p){ Remove-Item $p -Force -EA SilentlyContinue; WLog ('removed_shortcut=' + $bad) }
}

WLog '=== ORGANIZE DONE ==='
$ok = ($mains.Count -eq 1 -and $oldBat.Count -eq 0 -and $psWorkers.Count -le 1 -and $live.Count -eq 0)
if($ok){ Write-Host 'ORGANIZE_OK' } else { Write-Host 'ORGANIZE_CHECK'; Write-Host ('MAIN='+$mains.Count+' OLD_BAT='+$oldBat.Count+' PS='+$psWorkers.Count+' LIVE='+$live.Count) }
"""


def main() -> int:
    if not HOST or not USER:
        print("Missing WIN_HOST/WIN_USER", file=sys.stderr)
        return 1

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        HOST,
        username=USER,
        password=PASSWORD,
        timeout=45,
        allow_agent=False,
        look_for_keys=False,
    )
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

    ensure_dir(KEEP + r"\scripts")
    for rel in UPLOADS:
        local = ROOT / rel
        remote = KEEP + "\\" + rel.replace("/", "\\")
        ensure_dir(str(Path(remote).parent))
        sftp.put(str(local), remote)
        print(f"UPLOADED {rel}")

    remote_ps = r"C:\ProgramData\GoldenShield\_organize_windows.ps1"
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
    return 0 if "ORGANIZE_OK" in out or "ORGANIZE_CHECK" in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
