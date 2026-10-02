# ضبط تيليgram: إظهار قوة الإشارة + إشارات حية + دخول يدوي قبل الصفقة
$ErrorActionPreference = 'Continue'
$bot = 'C:\GoldenShield_Binance'
$envp = Join-Path $bot '.env'
if (-not (Test-Path $envp)) { Write-Host 'NO_ENV'; exit 1 }

$map = @{
  'TELEGRAM_SIGNALS_ONLY'='false'
  'TELEGRAM_LIVE_SIGNALS'='true'
  'TELEGRAM_LIVE_SIGNALS_SECONDS'='4'
  'TELEGRAM_SIGNAL_MIN_PERCENT'='70'
  'TELEGRAM_SEND_CYCLE_SIGNALS'='false'
  'MANUAL_ENTRY_REQUIRED'='true'
  'AUTO_ENTRY_MIN_PERCENT'='95'
  'BOT_FORCE_ACTIVE'='true'
  'NO_SLEEP_MODE'='true'
  'HYBRID_SIGNAL_MODE'='true'
}
$lines = Get-Content $envp -Encoding UTF8
$seen = @{}
$out = @()
foreach ($line in $lines) {
  if ($line -match '^\s*#' -or $line -notmatch '=') { $out += $line; continue }
  $k = ($line -split '=', 2)[0].Trim()
  if ($map.ContainsKey($k)) { $out += "$k=$($map[$k])"; $seen[$k] = 1 }
  else { $out += $line }
}
foreach ($k in $map.Keys) { if (-not $seen.ContainsKey($k)) { $out += "$k=$($map[$k])" } }
$utf8 = New-Object System.Text.UTF8Encoding $false
[IO.File]::WriteAllLines($envp, $out, $utf8)
Write-Host 'ENV_PATCH_OK'

schtasks /End /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
Start-Sleep -Seconds 2
Remove-Item (Join-Path $bot 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Start-ScheduledTask -TaskName 'GoldenShieldBotOfficial' -EA SilentlyContinue
Start-Sleep -Seconds 15

$pyObj = Get-ChildItem 'C:\Users\*\AppData\Local\Programs\Python\Python*\python.exe' -EA SilentlyContinue | Select-Object -First 1
$py = if ($pyObj) { $pyObj.FullName } else { 'py' }
Set-Location $bot
$env:PYTHONPATH = $bot
& $py -c @"
from config.settings import load_settings
s = load_settings(reload=True)
print('signals_only', s.telegram_signals_only)
print('live_signals', __import__('os').getenv('TELEGRAM_LIVE_SIGNALS'))
print('manual_entry', s.manual_entry_required)
print('auto_min', s.auto_entry_min_percent)
print('notify_min', s.telegram_signal_min_percent)
"@ 2>&1 | ForEach-Object { Write-Host $_ }

$n = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py' }).Count
Write-Host ("BOT_PROCS=" + $n)
Write-Host 'TELEGRAM_HYBRID_PATCH_OK'
