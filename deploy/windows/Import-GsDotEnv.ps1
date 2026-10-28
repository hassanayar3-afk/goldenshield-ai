param(
    [Parameter(Mandatory = $true)]
    [string]$EnvPath
)
if (-not (Test-Path $EnvPath)) { return }
Get-Content $EnvPath -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    if ($line -notmatch "=") { return }
    $k, $v = $line.Split("=", 2)
    $k = $k.Trim()
    $v = $v.Trim().Trim('"').Trim("'")
    if ($k) { Set-Item -Path "Env:$k" -Value $v }
}
