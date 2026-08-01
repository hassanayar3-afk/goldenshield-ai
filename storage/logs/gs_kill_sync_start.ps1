$ErrorActionPreference = 'Continue'
Write-Host 'KILLALL'
taskkill /F /IM python.exe /T 2>$null
taskkill /F /IM pythonw.exe /T 2>$null
taskkill /F /IM py.exe /T 2>$null
Start-Sleep -Seconds 4
$bot = 'C:\GoldenShield_Binance'
Remove-Item (Join-Path $bot 'storage\runtime\bot_instance.lock') -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $bot 'storage\runtime\user_stopped.flag') -Force -ErrorAction SilentlyContinue
Set-Location $bot
$env:PYTHONPATH = $bot
$env:PYTHONIOENCODING = 'utf-8'
Write-Host 'SYNC'
py -u scripts\sync_holdings_local.py
Write-Host 'START'
Start-Process -FilePath 'py' -ArgumentList '-u','main.py' -WorkingDirectory $bot -WindowStyle Hidden
Start-Sleep -Seconds 15
$n = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'main\.py') }).Count
Write-Host ("RUNNING count=" + $n)
if (Test-Path (Join-Path $bot 'storage\logs\holdings_report.txt')) {
  Write-Host '--- HOLDINGS ---'
  Get-Content (Join-Path $bot 'storage\logs\holdings_report.txt')
}
