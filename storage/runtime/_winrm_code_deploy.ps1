
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
foreach ($n in $keepNames) {
  $src = Join-Path $bot $n
  if (Test-Path $src) {
    Copy-Item -Path $src -Destination (Join-Path $staging $n) -Recurse -Force
  }
}

$zip = Join-Path $env:TEMP 'goldenshield_main.zip'
$extract = Join-Path $env:TEMP 'goldenshield_main_extract'
Remove-Item $zip,$extract -Recurse -Force -EA SilentlyContinue
New-Item -ItemType Directory -Force -Path $extract | Out-Null
Write-Host 'DOWNLOAD_ZIP'
Invoke-WebRequest -Uri 'https://github.com/hassanayar3-afk/goldenshield-ai/archive/refs/heads/main.zip' -OutFile $zip -UseBasicParsing
Expand-Archive -Path $zip -DestinationPath $extract -Force
$inner = Get-ChildItem $extract -Directory | Select-Object -First 1
if (-not $inner) { Write-Host 'EXTRACT_FAIL'; exit 2 }

Get-ChildItem $bot -Force | Where-Object { $_.Name -notin $keepNames } | Remove-Item -Recurse -Force -EA SilentlyContinue
Copy-Item -Path (Join-Path $inner.FullName '*') -Destination $bot -Recurse -Force

foreach ($n in $keepNames) {
  $saved = Join-Path $staging $n
  if (Test-Path $saved) {
    $dest = Join-Path $bot $n
    if (Test-Path $dest) { Remove-Item $dest -Recurse -Force -EA SilentlyContinue }
    Copy-Item -Path $saved -Destination $dest -Recurse -Force
  }
}
Remove-Item $staging,$zip,$extract -Recurse -Force -EA SilentlyContinue

Write-Host ('HAS_MAIN=' + (Test-Path (Join-Path $bot 'main.py')))
Write-Host ('HAS_ENV=' + (Test-Path (Join-Path $bot '.env')))

$py = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
if (-not (Test-Path $py)) { $py = 'py' }
Set-Location $bot
& $py -m pip install -r requirements.txt -q
Write-Host 'PIP_OK'

powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $bot 'scripts\gs_kill_all.ps1')
Start-Sleep -Seconds 2
$flag = Join-Path $bot 'storage\runtime\user_stopped.flag'
if (Test-Path $flag) { Remove-Item $flag -Force }
schtasks /End /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
try {
  Start-ScheduledTask -TaskName 'GoldenShieldBotOfficial' -EA Stop
} catch {
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = 'powershell.exe'
  $psi.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$bot\gs_daemon.ps1`""
  $psi.WorkingDirectory = $bot
  $psi.UseShellExecute = $true
  $psi.WindowStyle = 'Hidden'
  [System.Diagnostics.Process]::Start($psi) | Out-Null
}
Start-Sleep -Seconds 12
$procs = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'main\.py' })
Write-Host ('BOT_PROCS=' + $procs.Count)
if (Test-Path (Join-Path $bot 'storage\logs\bot_stderr.log')) {
  Write-Host '--- STDERR ---'
  Get-Content (Join-Path $bot 'storage\logs\bot_stderr.log') -Tail 15 -EA SilentlyContinue
}
Write-Host 'CODE_DEPLOY_OK'
