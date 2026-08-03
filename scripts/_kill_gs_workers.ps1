# يوقف عمال GoldenShield المكررين فقط — لا يمسح بيانات
$patterns = @(
    'main\.py',
    'run_official_bot\.(bat|ps1)',
    '00_LIVE_CONSOLE\.bat',
    'LIVE VIEW',
    'GoldenShield WORKER'
)
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | ForEach-Object {
    $cl = $_.CommandLine
    if (-not $cl) { return }
    foreach ($pat in $patterns) {
        if ($cl -match $pat) {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            break
        }
    }
}
