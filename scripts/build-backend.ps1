param(
  [string]$Python = $env:DLAB_PYTHON
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
if (-not $Python) {
  $venv = Join-Path $root '.venv\Scripts\python.exe'
  if (Test-Path $venv) { $Python = $venv } else { $Python = 'python' }
}
if (-not (Test-Path (Join-Path $root 'backend.spec'))) { throw 'backend.spec missing' }
if (-not (Test-Path (Join-Path $root 'main.py'))) { throw 'main.py missing' }
if (-not (Test-Path (Join-Path $root 'core'))) { throw 'core directory missing' }
Write-Host "Backend build: $Python"
& $Python -m PyInstaller --noconfirm --clean backend.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
$out = Join-Path $root 'dist\backend.exe'
if (-not (Test-Path $out)) { throw "backend.exe missing: $out" }
$item = Get-Item -LiteralPath $out
if ($item.Length -le 0) { throw 'backend.exe is empty' }
function Get-Sha256Hex([string]$file) {
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try { return ([BitConverter]::ToString($sha.ComputeHash([System.IO.File]::ReadAllBytes($file))) -replace '-','') }
  finally { $sha.Dispose() }
}
Write-Host ("Backend OK: {0} bytes sha256={1}" -f $item.Length, (Get-Sha256Hex $out))
