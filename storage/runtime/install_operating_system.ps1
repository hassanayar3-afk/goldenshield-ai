# GoldenShield — نظام تشغيل 24/7: منع سكون ويندوز + START/STOP + daemon
$ErrorActionPreference = 'Continue'
$bot = 'C:\GoldenShield_Binance'
Set-Location $bot

Write-Host '=== GS_OPERATING_SYSTEM ==='

# --- منع السكون على مستوى Windows (دائم) ---
powercfg -change -standby-timeout-ac 0 | Out-Null
powercfg -change -hibernate-timeout-ac 0 | Out-Null
powercfg -change -monitor-timeout-ac 0 | Out-Null
powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_SLEEP STANDBYIDLE 0 | Out-Null
powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_SLEEP HIBERNATEIDLE 0 | Out-Null
powercfg /SETACTIVE SCHEME_CURRENT | Out-Null
powercfg /hibernate off 2>$null | Out-Null
Write-Host 'WINDOWS_SLEEP_DISABLED'

# --- .env: لا سكون في البوت ---
$envp = Join-Path $bot '.env'
$map = @{
  'NO_SLEEP_MODE'='true'
  'BOT_FORCE_ACTIVE'='true'
  'LOOP_INTERVAL_SECONDS'='4'
  'TELEGRAM_LIVE_SIGNALS'='true'
  'TELEGRAM_LIVE_SIGNALS_SECONDS'='4'
  'TELEGRAM_LIVE_POSITIONS_SECONDS'='3'
  'EXECUTION_BACKEND'='binance'
  'EXECUTION_MODE'='live'
  'BINANCE_DEMO_TRADING'='true'
  'SSOT_SYNC_ENABLED'='true'
  'ENTERPRISE_PIPELINE_ENABLED'='true'
  'HYBRID_SIGNAL_MODE'='true'
  'MANUAL_ENTRY_REQUIRED'='false'
  'GOLDENSHIELD_OFFICIAL_ROOT'='C:\GoldenShield_Binance'
  'GOLDENSHIELD_ENFORCE_OFFICIAL_ROOT'='true'
}
if (Test-Path $envp) {
  $lines = Get-Content $envp -Encoding UTF8
  $seen = @{}
  $out = @()
  foreach ($line in $lines) {
    if ($line -match '^\s*#' -or $line -notmatch '=') { $out += $line; continue }
    $k = ($line -split '=', 2)[0].Trim()
    if ($map.ContainsKey($k)) { $out += "$k=$($map[$k])"; $seen[$k] = 1 }
    elseif ($k -match '^(MT5_|BOT_AUTO_SYNC_MT5)') { continue }
    else { $out += $line }
  }
  foreach ($k in $map.Keys) { if (-not $seen.ContainsKey($k)) { $out += "$k=$($map[$k])" } }
  $utf8 = New-Object System.Text.UTF8Encoding $false
  [System.IO.File]::WriteAllLines($envp, $out, $utf8)
  Write-Host 'ENV_NO_SLEEP_OK'
}

# --- اختصارات START / STOP على سطح المكتب ---
$desk = [Environment]::GetFolderPath('CommonDesktopDirectory')
$launchers = @(
  @{ Src = 'GS_START.bat'; Dst = 'GoldenShield START.bat' },
  @{ Src = 'GS_STOP.bat'; Dst = 'GoldenShield STOP.bat' },
  @{ Src = 'START_BOT.bat'; Dst = 'GoldenShield START_BOT.bat' },
  @{ Src = 'STOP_BOT.bat'; Dst = 'GoldenShield STOP_BOT.bat' }
)
foreach ($L in $launchers) {
  $src = Join-Path $bot $L.Src
  if (Test-Path $src) {
    Copy-Item $src (Join-Path $desk $L.Dst) -Force
    Write-Host ('DESKTOP ' + $L.Dst)
  }
}
if (-not (Test-Path (Join-Path $bot 'start_bot.bat')) -and (Test-Path (Join-Path $bot 'START_BOT.bat'))) {
  Copy-Item (Join-Path $bot 'START_BOT.bat') (Join-Path $bot 'start_bot.bat') -Force
}
if (-not (Test-Path (Join-Path $bot 'stop_bot.bat')) -and (Test-Path (Join-Path $bot 'STOP_BOT.bat'))) {
  Copy-Item (Join-Path $bot 'STOP_BOT.bat') (Join-Path $bot 'stop_bot.bat') -Force
}

# --- إيقاف نظيف ثم تشغيل daemon 24/7 ---
Remove-Item (Join-Path $bot 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $bot 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
if (Test-Path 'C:\ProgramData\GoldenShield\bot_instance.lock') {
  Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue
}
if (Test-Path (Join-Path $bot 'scripts\gs_kill_all.ps1')) {
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $bot 'scripts\gs_kill_all.ps1')
}
Start-Sleep -Seconds 2

$pyObj = Get-ChildItem 'C:\Users\*\AppData\Local\Programs\Python\Python*\python.exe' -EA SilentlyContinue | Select-Object -First 1
if ($pyObj) { $py = $pyObj.FullName } else { $py = 'py' }

foreach ($tn in @('GoldenShieldLiveConsole', 'GoldenShieldStatusWindow', 'GoldenShieldBot', 'GoldenShieldBotBoot')) {
  schtasks /End /TN $tn /F 2>$null | Out-Null
  schtasks /Delete /TN $tn /F 2>$null | Out-Null
}

schtasks /End /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
schtasks /Delete /TN GoldenShieldBotOfficial /F 2>$null | Out-Null

try {
  $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$bot\gs_daemon.ps1`"" -WorkingDirectory $bot
  $user = $env:USERNAME
  $prin = New-ScheduledTaskPrincipal -UserId $user -LogonType S4U -RunLevel Highest
  $setOn = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 3650)
  Register-ScheduledTask -TaskName 'GoldenShieldBotOfficial' -Action $action -Principal $prin -Settings $setOn `
    -Trigger (New-ScheduledTaskTrigger -AtStartup) -Force | Out-Null
  Start-ScheduledTask -TaskName 'GoldenShieldBotOfficial' | Out-Null
  Write-Host 'TASK_DAEMON_OK'
} catch {
  Write-Host ('TASK_ERR ' + $_.Exception.Message)
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = 'powershell.exe'
  $psi.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$bot\gs_daemon.ps1`""
  $psi.WorkingDirectory = $bot
  $psi.UseShellExecute = $true
  [System.Diagnostics.Process]::Start($psi) | Out-Null
  Write-Host 'DAEMON_FALLBACK_OK'
}

Start-Sleep -Seconds 20

$procs = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'main\.py' })
Write-Host ('BOT_PROCS=' + $procs.Count)

# --- تحقق Binance + Telegram ---
Set-Location $bot
$env:PYTHONPATH = $bot
$verify = @'
import asyncio
from config.settings import load_settings
from data.exchange_client import get_exchange, reset_exchange

s = load_settings(reload=True)
print("SETTINGS_BACKEND", s.execution_backend)
print("SETTINGS_MODE", s.execution_mode)
print("DEMO", bool(s.binance_demo_trading))
print("KEY_LEN", len(s.binance_api_key or ""))
print("SECRET_LEN", len(s.binance_api_secret or ""))
reset_exchange()
ex = get_exchange()
pub = (ex.urls.get("api") or {}).get("public", "")
print("API_PUBLIC", pub)
try:
    bal = ex.fetch_balance()
    usdt = (bal.get("USDT") or {}).get("free")
    print("USDT_FREE", usdt)
    print("BINANCE_OK")
except Exception as e:
    print("BINANCE_FAIL", type(e).__name__)

from operations.telegram_bot import TelegramBot
bot = TelegramBot()
mid = bot.send_message(
    "🛡 <b>GoldenShield</b>\n✅ نظام التشغيل 24/7 مثبت\n"
    "⚡ NO_SLEEP=ON | Binance متصل\nالبوت يعمل على السيرفر.",
    parse_mode="HTML",
)
print("TELEGRAM_OK", bool(mid))
'@
$vf = Join-Path $env:TEMP 'gs_verify_os.py'
Set-Content -Path $vf -Value $verify -Encoding UTF8
& $py $vf 2>&1 | ForEach-Object { Write-Host $_ }

Write-Host 'OPERATING_SYSTEM_OK'
