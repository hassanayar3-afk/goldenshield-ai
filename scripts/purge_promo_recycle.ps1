$ErrorActionPreference = "Continue"
$shell = New-Object -ComObject Shell.Application
$rb = $shell.NameSpace(0x0a)
$count = 0
if ($null -eq $rb) {
    Write-Output "NO_RECYCLE_BIN"
    exit 1
}
foreach ($item in @($rb.Items())) {
    $name = [string]$item.Name
    $orig = ""
    try { $orig = [string]$rb.GetDetailsOf($item, 1) } catch {}
    $hit = $false
    if ($name -match "PROMO_30s|promo_video|mclip_|video_silent|voice_iq|voice2|motion_silent|motion_smooth") { $hit = $true }
    if ($orig -match "promo_video|PROMO_30s") { $hit = $true }
    if ($hit) {
        Write-Output "DEL $name | $orig"
        try {
            # permanently remove
            $item.InvokeVerb("delete")
            $count++
        } catch {
            Write-Output "FAIL $name $_"
        }
    }
}
Write-Output "COUNT=$count"
if ($count -eq 0) {
    Write-Output "NO_PROMO_IN_RECYCLE_BIN"
}
