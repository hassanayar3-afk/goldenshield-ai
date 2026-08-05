# نافذة قراءة الإشارات الحية — نفس أسلوب CMD القديم (زوج/سعر/درجة/WAIT)
# ليست للصفقات. إغلاق النافذة لا يوقف البوت.

$ErrorActionPreference = "Continue"
$Root = "C:\GoldenShield_Binance"
$Board = Join-Path $Root "storage\runtime\signals_board.txt"
$Log = Join-Path $Root "storage\logs\bot_stdout.log"

try {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class ConsoleQuickEdit {
  const int STD_INPUT_HANDLE = -10;
  const uint ENABLE_QUICK_EDIT = 0x0040;
  const uint ENABLE_EXTENDED = 0x0080;
  [DllImport("kernel32.dll", SetLastError=true)] static extern IntPtr GetStdHandle(int n);
  [DllImport("kernel32.dll", SetLastError=true)] static extern bool GetConsoleMode(IntPtr h, out uint mode);
  [DllImport("kernel32.dll", SetLastError=true)] static extern bool SetConsoleMode(IntPtr h, uint mode);
  public static void Disable() {
    IntPtr h = GetStdHandle(STD_INPUT_HANDLE);
    uint mode;
    if (!GetConsoleMode(h, out mode)) return;
    mode &= ~ENABLE_QUICK_EDIT;
    mode |= ENABLE_EXTENDED;
    SetConsoleMode(h, mode);
  }
}
"@ -ErrorAction Stop
    [ConsoleQuickEdit]::Disable()
} catch {}

try { $Host.UI.RawUI.WindowTitle = "GoldenShield LIVE SIGNALS" } catch {}
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

function Get-MainInfo {
    @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -match '^(python|pythonw|py)\.exe$' -and
        $_.CommandLine -and
        $_.CommandLine -match 'main\.py'
    })
}

function Get-FallbackSignalsFromLog {
    if (-not (Test-Path $Log)) { return @() }
    $lines = Get-Content -Path $Log -Tail 80 -ErrorAction SilentlyContinue
    $out = New-Object System.Collections.Generic.List[string]
    foreach ($line in $lines) {
        # أسطر الإشارات القديمة من main.py
        if ($line -match 'USDT\s*\|\s*.*(score|درجة|WAIT|BUY|SELL|REJECT)') {
            $clean = [regex]::Replace($line, '[^\x20-\x7E\|:/.\-_*]', '')
            $clean = $clean.Trim()
            if ($clean.Length -gt 8) { $out.Add("  * " + $clean) }
        }
        elseif ($line -match '[A-Z0-9]+/USDT') {
            $clean = [regex]::Replace($line, '[^\x20-\x7E\|:/.\-_*]', '')
            if ($clean -match 'WAIT|BUY|SELL|REJECT|score|/10') {
                $out.Add("  * " + $clean.Trim())
            }
        }
    }
    if ($out.Count -eq 0) { return @() }
    $start = [Math]::Max(0, $out.Count - 20)
    return @($out.GetRange($start, $out.Count - $start))
}

while ($true) {
    try { [ConsoleQuickEdit]::Disable() } catch {}
    Clear-Host
    $mains = Get-MainInfo
    $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    Write-Host ""
    if ($mains.Count -ge 1) {
        Write-Host ("  BOT: ACTIVE   PID: " + (($mains | ForEach-Object ProcessId) -join ",")) -ForegroundColor Green
    } else {
        Write-Host "  BOT: STOPPED   use START BOT" -ForegroundColor Red
    }
    Write-Host ("  TIME: " + $now)
    Write-Host "  VIEW: LIVE SIGNALS only (not trades)"
    Write-Host ""

    if (Test-Path $Board) {
        try {
            Get-Content -Path $Board -Encoding UTF8 -ErrorAction Stop | ForEach-Object {
                Write-Host $_
            }
        } catch {
            Write-Host "  (cannot read signals board file)"
        }
    } else {
        Write-Host "========================================================"
        Write-Host "  Waiting for signals board file..."
        Write-Host "  (bot will create it after analysis cycle)"
        Write-Host "========================================================"
        $fb = Get-FallbackSignalsFromLog
        if ($fb.Count -gt 0) {
            Write-Host "  ---- from recent log ----"
            $fb | ForEach-Object { Write-Host $_ }
        }
    }

    Write-Host ""
    Write-Host "  Tip: do not click inside window | close window != stop bot"
    Start-Sleep -Seconds 1
}
