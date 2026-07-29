# إلغاء التشغيل التلقائي لـ GoldenShield مع Windows
$TaskName = "GoldenShield_WindowsBoot"
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Removed scheduled task: $TaskName"
