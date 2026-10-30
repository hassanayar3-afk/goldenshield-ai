# تشغيل صقر تلقائياً عند إقلاع Windows — مهمة SYSTEM  # pragma: allowlist secret
$TaskName = "SAQR_Bot_AtStartup"
$BatPath  = "C:\Saqr\RUN_SAQR_BOT.bat"
$WorkDir  = "C:\Saqr"

if (-not (Test-Path $BatPath)) {
  Write-Error "Missing $BatPath"
  exit 1
}

$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BatPath`"" -WorkingDirectory $WorkDir
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force

Write-Host "OK: Scheduled task '$TaskName' registered (At Startup -> RUN_SAQR_BOT.bat)"
