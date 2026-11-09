param(
  [string]$Python = $env:DLAB_PYTHON
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
function Get-Sha256Hex([string]$file) {
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try { return ([BitConverter]::ToString($sha.ComputeHash([System.IO.File]::ReadAllBytes($file))) -replace '-','') }
  finally { $sha.Dispose() }
}

$pkg = Get-Content -LiteralPath (Join-Path $root 'package.json') -Raw | ConvertFrom-Json
if ($pkg.version -ne '1.6.0') { throw "package.json version is $($pkg.version), expected 1.6.0" }
if (Test-Path (Join-Path $root 'backend.exe')) { throw 'root backend.exe exists; refusing legacy backend input' }
if ($pkg.build.extraResources.Count -ne 1 -or $pkg.build.extraResources[0].from -ne 'dist/backend.exe') {
  throw 'extraResources must be sourced from dist/backend.exe'
}
if ($pkg.build.files -notcontains 'core/test_hook_policy.js') {
  throw 'package files must contain core/test_hook_policy.js'
}

& (Join-Path $PSScriptRoot 'build-backend.ps1') -Python $Python
if ($LASTEXITCODE -ne 0) { throw 'backend build failed' }
$backend = Join-Path $root 'dist\backend.exe'
if (-not (Test-Path $backend)) { throw "missing built backend: $backend" }
$backendHash = Get-Sha256Hex $backend
Write-Host "Building Electron with backend sha256=$backendHash"

& npm run build:electron
if ($LASTEXITCODE -ne 0) { throw "electron-builder failed with exit code $LASTEXITCODE" }

$packaged = Join-Path $root 'release\win-unpacked\resources\backend.exe'
if (-not (Test-Path $packaged)) { throw "packaged backend missing: $packaged" }
$packagedHash = Get-Sha256Hex $packaged
if ($packagedHash -ne $backendHash) { throw "packaged backend hash mismatch: $packagedHash != $backendHash" }
if (-not (Test-Path (Join-Path $root 'release\win-unpacked\resources\app\core\test_hook_policy.js'))) {
  throw 'core/test_hook_policy.js missing from packaged app'
}
$installer = Get-ChildItem (Join-Path $root 'release') -Filter '*.exe' -File | Where-Object { $_.Name -like 'DigitalLab Setup *' } | Select-Object -First 1
if (-not $installer) { throw 'NSIS installer missing' }
Write-Host ("Build OK: backend={0} packaged_backend={1} installer={2} sha256={3}" -f $backendHash, $packagedHash, $installer.FullName, (Get-Sha256Hex $installer.FullName))
