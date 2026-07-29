# مزامنة تلقائية: سحب من GitHub ثم رفع التعديلات المحلية
# لا يرفع .env (محمي بـ .gitignore)

$ErrorActionPreference = "Continue"
$Repo = "C:\Users\acer\goldenshield\GoldenShield_AI"
$LogDir = Join-Path $Repo "storage\logs"
$Log = Join-Path $LogDir "git_autosync.log"
$Git = "C:\Program Files\Git\cmd\git.exe"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log([string]$msg) {
  $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
  Add-Content -LiteralPath $Log -Value $line -Encoding UTF8
}

try {
  if (-not (Test-Path -LiteralPath (Join-Path $Repo ".git"))) {
    Write-Log "SKIP: not a git repo"
    exit 0
  }

  Set-Location -LiteralPath $Repo

  # تأكد أننا على main وتتبع origin
  & $Git fetch origin 2>&1 | Out-Null

  $pull = & $Git pull --rebase --autostash origin main 2>&1
  Write-Log ("PULL: " + (($pull | Out-String).Trim()))

  # لا نضيف أسراراً
  & $Git add -A
  # دفاع إضافي
  & $Git reset HEAD -- .env 2>$null
  & $Git restore --staged .env 2>$null

  $status = & $Git status --porcelain
  if (-not $status) {
    Write-Log "OK: nothing to push"
    exit 0
  }

  # منع أي .env staged
  $staged = & $Git diff --cached --name-only
  if ($staged -match '(^|/)\.env$') {
    Write-Log "BLOCKED: .env would be committed"
    & $Git reset HEAD -- .env 2>$null
  }

  $msg = "auto-sync " + (Get-Date -Format "yyyy-MM-dd HH:mm")
  & $Git commit -m $msg 2>&1 | Out-Null
  $push = & $Git push origin main 2>&1
  Write-Log ("PUSH: " + (($push | Out-String).Trim()))
  Write-Log "OK: synced"
}
catch {
  Write-Log ("ERROR: " + $_.Exception.Message)
  exit 1
}
