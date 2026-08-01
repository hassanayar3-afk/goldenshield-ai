$ErrorActionPreference = 'Continue'
Write-Host 'KILLALL'
taskkill /F /IM python.exe /T 2>$null
taskkill /F /IM pythonw.exe /T 2>$null
taskkill /F /IM py.exe /T 2>$null
Start-Sleep -Seconds 3
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'main\.py|GoldenShield') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2
$bot = 'C:\GoldenShield_Binance'
Remove-Item (Join-Path $bot 'storage\runtime\bot_instance.lock') -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $bot 'storage\runtime\user_stopped.flag') -Force -ErrorAction SilentlyContinue
Set-Location $bot
$env:PYTHONPATH = $bot
$env:PYTHONIOENCODING = 'utf-8'
py -c @'
from config.settings import load_settings
load_settings(reload=True)
from database.connection import init_database
from database.repositories.trade_repo import TradeRepository
from execution.trade_executor import TradeExecutor
from risk.risk_orchestrator import RiskOrchestrator
from execution.binance_position_sync import sync_binance_spot_positions, format_holdings_report
from operations.alert_dispatcher import AlertDispatcher

s = load_settings()
db = init_database(s.db_path)
risk = RiskOrchestrator()
ex = TradeExecutor(risk_orchestrator=risk)
ex.trade_repo = TradeRepository(db)
ex.alerts = AlertDispatcher()
ex.restore_open_positions()
added = sync_binance_spot_positions(ex)
report = format_holdings_report(ex)
print("SYNCED", added)
print(report)
open("storage/logs/holdings_report.txt", "w", encoding="utf-8").write(report + "\nSYNCED=" + str(added))
'@
Start-Process -FilePath 'py' -ArgumentList '-u','main.py' -WorkingDirectory $bot -WindowStyle Hidden
Start-Sleep -Seconds 15
$n = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'main\.py') }).Count
Write-Host ("RUNNING count=" + $n)
Get-Content (Join-Path $bot 'storage\logs\holdings_report.txt') -ErrorAction SilentlyContinue
