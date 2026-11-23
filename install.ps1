$ErrorActionPreference = "Stop"
$repo = "praha6248/PrismaFlow"

Write-Host "Looking up the latest PrismaFlow release..."
$release = Invoke-RestMethod "https://api.github.com/repos/$repo/releases/latest"
$asset = $release.assets | Where-Object { $_.name -like "*windows-x64-setup.exe" } | Select-Object -First 1
if (-not $asset) { throw "No Windows installer found in the latest release." }

$target = Join-Path $env:TEMP $asset.name
Write-Host "Downloading $($asset.browser_download_url)"
Invoke-WebRequest $asset.browser_download_url -OutFile $target
Start-Process $target -Wait

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
  Write-Host ""
  Write-Host "Next: install Ollama from https://ollama.com/download, then run:"
  Write-Host "  ollama pull gemma3:12b   (or gemma3:4b with less than 16 GB RAM)"
}
