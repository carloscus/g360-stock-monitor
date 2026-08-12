# Build portable zip
Write-Host "Creating portable zip..."
$portable = "g360-stock-monitor-portable"
$zip = "g360-stock-monitor-portable.zip"

if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path "$portable\*" -DestinationPath $zip -Force
Write-Host "Created: $zip"
