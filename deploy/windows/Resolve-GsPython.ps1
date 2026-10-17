param(
    [string]$Root = ""
)
$ErrorActionPreference = "SilentlyContinue"
if (-not $Root) {
    $Root = if ($env:GOLDENSHIELD_OFFICIAL_ROOT) { $env:GOLDENSHIELD_OFFICIAL_ROOT } else { "C:\GoldenShield_Binance" }
}

$candidates = @(
    $env:GS_PYTHON_EXE,
    (Join-Path $Root ".venv\Scripts\python.exe"),
    (Join-Path $Root "venv\Scripts\python.exe")
)

foreach ($name in @("python", "python3", "py")) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { $candidates += $cmd.Source }
}

$localApp = [Environment]::GetFolderPath("LocalApplicationData")
$candidates += Get-ChildItem -Path (Join-Path $localApp "Programs\Python") -Filter python.exe -Recurse -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty FullName

foreach ($py in $candidates) {
    if ($py -and (Test-Path -LiteralPath $py)) {
        return (Resolve-Path -LiteralPath $py).Path
    }
}

return "py"
