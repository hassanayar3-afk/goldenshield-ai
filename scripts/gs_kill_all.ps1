# GoldenShield — kill all bot / launcher / pulse processes (single-instance prep)
$ErrorActionPreference = "Continue"
$patterns = @(
    'main\.py',
    'run_official_bot\.(bat|ps1|cmd)',
    'run_bot_visible\.(bat|cmd|ps1)',
    'gs_daemon\.ps1',
    'BOT_WINDOW\.(bat|ps1)',
    'live_console\.(bat|ps1)',
    '00_LIVE_CONSOLE\.bat'
)
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and (
        ($_.CommandLine -match 'main\.py') -or
        ($_.CommandLine -match 'run_official_bot') -or
        ($_.CommandLine -match 'run_bot_visible') -or
        ($_.CommandLine -match 'gs_daemon\.ps1') -or
        ($_.CommandLine -match 'BOT_WINDOW\.(bat|ps1)') -or
        ($_.CommandLine -match 'live_console\.(bat|ps1)') -or
        ($_.CommandLine -match '00_LIVE_CONSOLE')
    )
} | ForEach-Object {
    try {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
        Write-Output ("KILLED=" + $_.ProcessId + " " + $_.Name)
    } catch {}
}

# End AND delete legacy scheduled tasks (no hidden workers)
foreach ($tn in @('GoldenShieldBotOfficial','GoldenShieldLiveConsole','GoldenShieldStatusWindow','GoldenShield_WindowsBoot')) {
    schtasks /End /TN $tn /F 2>$null | Out-Null
    schtasks /Delete /TN $tn /F 2>$null | Out-Null
}

# Remove hidden official worker scripts if still present
$root = 'C:\GoldenShield_Binance'
$arch = Join-Path $root 'storage\runtime\_archived_launchers'
New-Item -ItemType Directory -Force -Path $arch | Out-Null
foreach ($n in @('run_official_bot.ps1','run_official_bot.bat')) {
    $p = Join-Path $root $n
    if (Test-Path $p) {
        Move-Item $p (Join-Path $arch $n) -Force -ErrorAction SilentlyContinue
        Write-Output ("ARCHIVED=" + $n)
    }
}
