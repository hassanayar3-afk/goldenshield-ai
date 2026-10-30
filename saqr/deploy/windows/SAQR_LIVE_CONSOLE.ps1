# SAQR v6.2.3 — live console (BTCUSDT + balance + signals)
$ErrorActionPreference = "SilentlyContinue"
$base = "http://127.0.0.1:8788"
$maxWait = 45
$waited = 0

Write-Host ""
Write-Host "  SAQR v6.2.3 — انتظار المحرك..." -ForegroundColor Cyan

while ($waited -lt $maxWait) {
    try {
        $h = Invoke-RestMethod -Uri "$base/api/health" -TimeoutSec 2
        if ($h.ok) { break }
    } catch {}
    Start-Sleep -Seconds 1
    $waited++
    Write-Host "  ... $waited s"
}

if ($waited -ge $maxWait) {
    Write-Host "[FAIL] المحرك لم يفتح المنفذ 8788 — راجع logs\console.log" -ForegroundColor Red
    if (Test-Path "logs\console.log") { Get-Content "logs\console.log" -Tail 25 }
    Read-Host "Enter للإغلاق"
    exit 1
}

Start-Process "http://127.0.0.1:8788"
Write-Host "[OK] لوحة التحكم: http://127.0.0.1:8788" -ForegroundColor Green
Write-Host "Ctrl+C لإيقاف المراقبة (أوقف saqr.exe من STOP_SAQR.bat)" -ForegroundColor Yellow
Write-Host ""

while ($true) {
    $proc = Get-Process -Name "saqr" -ErrorAction SilentlyContinue
    if (-not $proc) {
        Write-Host "[!] saqr.exe توقف — آخر سطور السجل:" -ForegroundColor Red
        if (Test-Path "logs\console.log") { Get-Content "logs\console.log" -Tail 20 }
        Read-Host "Enter للإغلاق"
        break
    }
    try {
        $st = Invoke-RestMethod -Uri "$base/api/status" -TimeoutSec 5
        $tk = Invoke-RestMethod -Uri "$base/api/market/ticker?symbol=BTCUSDT" -TimeoutSec 8
        $mir = Invoke-RestMethod -Uri "$base/api/binance_mirror" -TimeoutSec 5
        $sig = Invoke-RestMethod -Uri "$base/api/market/signals?interval=15m" -TimeoutSec 12
        $top = $sig.signals | Select-Object -First 1
        $sigLine = if ($top) { "$($top.pair) $($top.direction) $($top.strengthScore)%" } else { "—" }
        $px = if ($tk.ok) { [double]$tk.price } else { 0 }
        $bot = if ($st.bot_running) { "نشط" } else { "متوقف" }
        $ts = Get-Date -Format "HH:mm:ss"
        Write-Host "[$ts] BTCUSDT: $px | رصيد Paper: $([math]::Round($mir.total_balance_usd,2)) USD | صفقات: $($mir.open_positions_count) | بوت: $bot"
        Write-Host "         إشارة: $sigLine | سوق: $($st.market_rest_url)"
    } catch {
        Write-Host "[!] API: $_" -ForegroundColor DarkYellow
    }
    Start-Sleep -Seconds 4
}
