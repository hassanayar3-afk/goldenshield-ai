Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'main\.py') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 3
Get-Process py,python,pythonw -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Start-Process -FilePath "py" -ArgumentList "-u","main.py" -WorkingDirectory "C:\GoldenShield_Binance" -WindowStyle Hidden
Start-Sleep -Seconds 12
$n = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'main\.py') }).Count
Write-Host ("RUNNING count=" + $n)
