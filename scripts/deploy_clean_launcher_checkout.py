"""تنظيف ملفات التشغيل القديمة على VPS + تثبيت launcher موحّد + فحص تناسق."""

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
    "run_official_bot.ps1",
    "run_official_bot.bat",
    "START_BOT.bat",
    "STOP_BOT.bat",
    "REST_BOT.bat",
    "BOT_WINDOW.bat",
    "BOT_WINDOW.ps1",
    "scripts/_kill_gs_workers.ps1",
]

# ملفات تشغيل قديمة/مكررة تُحذف من جذر المشروع على السيرفر فقط
DELETE_OLD = [
    r"C:\GoldenShield_Binance\00_START_KEEP_OPEN.bat",
    r"C:\GoldenShield_Binance\00_START_VISIBLE.vbs",
    r"C:\GoldenShield_Binance\INSTALL_AUTOSTART.bat",
    r"C:\GoldenShield_Binance\scripts\DISABLED_START_FROM_DOWNLOADS.bat",
    r"C:\GoldenShield_Binance\scripts\00_START_AUTO.bat",
    r"C:\ProgramData\GoldenShield\_close_dust_once.py",
    r"C:\ProgramData\GoldenShield\fast_signals.ps1",
]

PS = r"""
$ErrorActionPreference='Continue'
$g='C:\GoldenShield_Binance'
$py='C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
Write-Host '=== CLEAN_OLD_LAUNCHERS ==='

# 1) إيقاف كل شيء متعلق بالبوت
schtasks /End /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
schtasks /End /TN GoldenShieldLiveConsole /F 2>$null | Out-Null
schtasks /End /TN GoldenShieldStatusWindow /F 2>$null | Out-Null
schtasks /Delete /TN GoldenShieldStatusWindow /F 2>$null | Out-Null
schtasks /Change /TN GoldenShieldLiveConsole /DISABLE 2>$null | Out-Null
if (Test-Path (Join-Path $g 'scripts\_kill_gs_workers.ps1')) {
  & (Join-Path $g 'scripts\_kill_gs_workers.ps1')
} else {
  Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and ($_.CommandLine -match 'main\.py|run_official_bot|BOT_WINDOW|00_LIVE_CONSOLE|00_START')
  } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
}
Start-Sleep 2

# 2) حذف ملف التشغيل القديم + نسخ قديمة (لا يمس .env / DB / reports)
$oldWorkers = @(
  (Join-Path $g 'run_official_bot.ps1'),
  (Join-Path $g 'run_official_bot.bat'),
  (Join-Path $g 'START_BOT.bat'),
  (Join-Path $g 'REST_BOT.bat')
)
foreach($p in $oldWorkers){
  if(Test-Path $p){
    Remove-Item $p -Force -EA SilentlyContinue
    Write-Host ('DELETED ' + $p)
  }
}

# 3) تنظيف أقفال/tmp فقط
$rt = Join-Path $g 'storage\runtime'
New-Item -ItemType Directory -Force -Path $rt | Out-Null
@(
  (Join-Path $rt 'user_stopped.flag'),
  (Join-Path $rt 'bot_instance.lock'),
  'C:\ProgramData\GoldenShield\bot_instance.lock'
) | ForEach-Object { Remove-Item $_ -Force -EA SilentlyContinue }
Get-ChildItem $rt -Filter '*.tmp' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
Get-ChildItem $rt -Filter '*.temp' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
Write-Host 'RUNTIME_CLEAN_OK'

# ملاحظة: الملفات الجديدة تُرفع من سكربت بايثون قبل هذا القسم الثاني
Write-Host 'CLEAN_PHASE_DONE'
"""

PS2 = r"""
$ErrorActionPreference='Continue'
$g='C:\GoldenShield_Binance'
$py='C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
Write-Host '=== INSTALL_NEW_LAUNCHER ==='

# حذف بقايا قديمة إضافية
$extra=@(
  (Join-Path $g '00_START_KEEP_OPEN.bat'),
  (Join-Path $g '00_START_VISIBLE.vbs'),
  (Join-Path $g 'INSTALL_AUTOSTART.bat'),
  (Join-Path $g 'scripts\DISABLED_START_FROM_DOWNLOADS.bat'),
  (Join-Path $g 'scripts\00_START_AUTO.bat')
)
foreach($p in $extra){ if(Test-Path $p){ Remove-Item $p -Force -EA SilentlyContinue; Write-Host ('DELETED_EXTRA ' + $p) } }

# اختصارات سطح المكتب
$desk=[Environment]::GetFolderPath('Desktop')
$w=New-Object -ComObject WScript.Shell
foreach($t in @(
  @{Name='START BOT.lnk'; Target=(Join-Path $g 'START_BOT.bat')},
  @{Name='STOP BOT.lnk'; Target=(Join-Path $g 'STOP_BOT.bat')},
  @{Name='REST BOT.lnk'; Target=(Join-Path $g 'REST_BOT.bat')}
)){
  $lnk=Join-Path $desk $t.Name
  $s=$w.CreateShortcut($lnk)
  $s.TargetPath=$t.Target
  $s.WorkingDirectory=$g
  $s.Save()
  Write-Host ('SHORTCUT ' + $t.Name)
}

# مهمة رسمية → العامل الجديد فقط
$worker=Join-Path $g 'run_official_bot.ps1'
if(-not (Test-Path $worker)){ Write-Host 'MISSING_WORKER'; exit 1 }
$tr = "powershell.exe -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$worker`""
schtasks /Delete /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
schtasks /Create /TN GoldenShieldBotOfficial /TR $tr /SC ONSTART /RL HIGHEST /F | Out-Null
try {
  $t=Get-ScheduledTask -TaskName 'GoldenShieldBotOfficial' -EA Stop
  $t.Settings.Hidden=$true
  $t.Settings.ExecutionTimeLimit='PT0S'
  $t | Set-ScheduledTask | Out-Null
} catch {}
Write-Host 'TASK_REGISTERED'

# ضبط .env بمفاتيح القواعد (بدون لمس الأسرار)
$envp=Join-Path $g '.env'
$map=@{
  'BOT_FORCE_ACTIVE'='true'
  'TELEGRAM_LIVE_SIGNALS'='true'
  'TELEGRAM_LIVE_SIGNALS_SECONDS'='15'
  'TELEGRAM_LIVE_POSITIONS_SECONDS'='1'
  'PROJECT_REFERENCE_CAPITAL'='5000'
  'PROJECT_MIN_TRADE_NOTIONAL'='25'
  'PROJECT_MIN_EXCHANGE_NOTIONAL'='5'
}
$lines=Get-Content $envp -EA SilentlyContinue
$keys=@{}
$out=foreach($line in $lines){
  if($line -match '^\s*#' -or $line -notmatch '='){ $line; continue }
  $k=($line -split '=',2)[0].Trim()
  if($map.ContainsKey($k)){ "$k=$($map[$k])"; $keys[$k]=1 } else { $line }
}
foreach($k in $map.Keys){ if(-not $keys.ContainsKey($k)){ $out += "$k=$($map[$k])" } }
$utf8=New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllLines($envp,$out,$utf8)
Write-Host 'ENV_RULES_OK'

# تشغيل
Remove-Item (Join-Path $g 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $g 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue
schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
Start-Sleep 14

# نافذة حالة واحدة
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'BOT_WINDOW\.(bat|ps1)' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
$bat=Join-Path $g 'BOT_WINDOW.bat'
schtasks /Delete /TN GoldenShieldStatusWindow /F 2>$null | Out-Null
schtasks /Create /TN GoldenShieldStatusWindow /TR "`"$bat`"" /SC ONCE /ST 00:00 /RL HIGHEST /IT /F 2>$null | Out-Null
schtasks /Run /TN GoldenShieldStatusWindow 2>$null | Out-Null

Write-Host '=== CHECKOUT ==='
$checks = New-Object System.Collections.Generic.List[string]

# ملفات
$need=@(
  'main.py','run_official_bot.ps1','START_BOT.bat','STOP_BOT.bat','REST_BOT.bat',
  'BOT_WINDOW.ps1','config\project_rules.py','operations\startup_cleanup.py',
  'operations\period_report.py','execution\binance_position_sync.py',
  'operations\telegram_dashboard.py','.env'
)
foreach($f in $need){
  $ok=Test-Path (Join-Path $g $f)
  $checks.Add(($f + '=' + $ok))
  Write-Host (($f) + '=' + $ok)
}

# علامة الإصدار في العامل
$hasTag = Select-String -Path (Join-Path $g 'run_official_bot.ps1') -Pattern 'GS_OFFICIAL_WORKER_v2026_08' -Quiet
Write-Host ('WORKER_TAG=' + $hasTag)
$checks.Add('WORKER_TAG=' + $hasTag)

$hasMirror = Select-String -Path (Join-Path $g 'operations\telegram_dashboard.py') -Pattern '_mirror_live_spot_state' -Quiet
Write-Host ('LIVE_MIRROR=' + $hasMirror)
$checks.Add('LIVE_MIRROR=' + $hasMirror)

$hasCloseMenu = Select-String -Path (Join-Path $g 'operations\telegram_keyboards.py') -Pattern 'close_menu_keyboard' -Quiet
Write-Host ('CLOSE_MENU=' + $hasCloseMenu)
$checks.Add('CLOSE_MENU=' + $hasCloseMenu)

# مهمة
$trLine = (schtasks /Query /TN GoldenShieldBotOfficial /FO LIST /V 2>$null | Select-String 'Task To Run').ToString()
Write-Host ('TASK_TR=' + $trLine)
$taskOk = $trLine -match 'run_official_bot\.ps1'
Write-Host ('TASK_POINTS_WORKER=' + $taskOk)
$checks.Add('TASK_POINTS_WORKER=' + $taskOk)

# عمليات
$mains=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\.py' })
Write-Host ('MAIN_COUNT=' + $mains.Count)
$checks.Add('MAIN_COUNT=' + $mains.Count)
if($mains.Count -ge 1){
  Write-Host ('MAIN_PID=' + ($mains | ForEach-Object ProcessId | Select-Object -First 1))
  Write-Host ('MAIN_CMD_HAS_ROOT=' + (($mains[0].CommandLine -match 'GoldenShield_Binance') -or ($mains[0].ExecutablePath -match 'python')))
}

# استيراد القواعد على السيرفر
& $py -c "import sys; sys.path.insert(0,r'C:\GoldenShield_Binance'); from config.project_rules import load_project_rules; from execution.binance_position_sync import live_mirror_sync_from_binance; from operations.startup_cleanup import run_startup_cleanup; r=load_project_rules(); assert r.reference_capital>=5000; print('IMPORT_OK', r.reference_capital, r.min_trade_notional)"
$importOk = ($LASTEXITCODE -eq 0)
Write-Host ('IMPORTS=' + $importOk)
$checks.Add('IMPORTS=' + $importOk)

# .env keys
Get-Content (Join-Path $g '.env') | Where-Object { $_ -match '^(BOT_FORCE_ACTIVE|PROJECT_|TELEGRAM_LIVE_|EXECUTION_|BINANCE_DEMO)=' } | ForEach-Object {
  if($_ -match '^(BINANCE_API|TELEGRAM_TOKEN)'){ } else { Write-Host ('ENV ' + $_) }
}

$dbOk = Test-Path (Join-Path $g 'storage\db\goldenshield.db')
Write-Host ('DB_EXISTS=' + $dbOk)
$checks.Add('DB_EXISTS=' + $dbOk)

$fail = @($checks | Where-Object { $_ -match '=False$' -or $_ -match 'MAIN_COUNT=0' -or $_ -eq 'IMPORTS=False' -or $_ -eq 'TASK_POINTS_WORKER=False' -or $_ -eq 'WORKER_TAG=False' })
if($mains.Count -eq 1 -and $fail.Count -eq 0 -and $importOk -and $taskOk -and $hasTag -and $hasMirror){
  Write-Host 'HARMONY_OK'
} else {
  Write-Host 'HARMONY_ISSUES'
  $fail | ForEach-Object { Write-Host ('ISSUE ' + $_) }
}
"""


def main() -> int:
    if not HOST or not USER or not PASSWORD:
        print("Set WIN_HOST / WIN_USER / WIN_PASSWORD")
        return 1
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
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
    try:
        def run_ps(content: str, name: str, timeout: int = 240) -> str:
            remote = f"C:\\ProgramData\\GoldenShield\\{name}"
            sftp = ssh.open_sftp()
            with sftp.file(remote, "w") as fh:
                fh.write(content.replace("\r\n", "\n").replace("\n", "\r\n"))
            sftp.close()
            _, o, e = ssh.exec_command(
                f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
                timeout=timeout,
            )
            return (o.read() + e.read()).decode("utf-8", errors="replace")

        # Phase 1: stop + delete old launchers + clean locks
        out1 = run_ps(PS, "_clean_launchers.ps1", timeout=120)
        print(out1.encode("ascii", "replace").decode("ascii"))

        # Phase 2: upload new launchers
        sftp = ssh.open_sftp()
        for rel in UPLOADS:
            local = ROOT / rel
            if not local.is_file():
                print("MISSING", rel)
                continue
            remote = f"{KEEP}\\{rel.replace('/', '\\')}"
            sftp.put(str(local), remote.replace("\\", "/"))
            print("UPLOADED", rel)
        for p in DELETE_OLD:
            try:
                sftp.remove(p.replace("\\", "/"))
                print("REMOTE_DEL", p)
            except OSError:
                pass
        sftp.close()

        # Phase 3: install task + start + checkout
        out2 = run_ps(PS2, "_install_launcher_checkout.ps1", timeout=240)
        print(out2.encode("ascii", "replace").decode("ascii"))
        return 0 if "HARMONY_OK" in out2 else 1
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
