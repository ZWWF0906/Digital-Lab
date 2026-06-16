param(
    [Parameter(Mandatory=$true)]
    [string]$LabRoot
)

$ErrorActionPreference = "Stop"

$LabRoot = (Resolve-Path $LabRoot).Path

$desktop = [Environment]::GetFolderPath("Desktop")
$pythonExe = "C:\Python314\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "[!] Python not found: $pythonExe"
    Write-Host "    Please edit install.ps1 and update `$pythonExe"
    Write-Host "    Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

$oldNames = @("Digital Lab Console.lnk", "Digital Lab Web.lnk", "Digital Lab GUI.lnk", "Digital Lab CLI.lnk", "Digital Lab.lnk")
for ($i = 0; $i -lt $oldNames.Length; $i++) {
    $old = Join-Path $desktop $oldNames[$i]
    if ($old -ne $null -and (Test-Path $old)) {
        Remove-Item $old -Force -ErrorAction SilentlyContinue
    }
}

$lnkPath = Join-Path $desktop "Digital Lab.lnk"
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut($lnkPath)
$lnk.TargetPath = $pythonExe
$lnk.Arguments = "desktop\launcher.py"
$lnk.WorkingDirectory = $LabRoot
$lnk.WindowStyle = 7
$lnk.Description = "Digital Lab - Web/GUI/CLI Launcher"

$iconPath = Join-Path $LabRoot "assets\icon.ico"
if ($iconPath -ne $null -and (Test-Path $iconPath)) {
    $lnk.IconLocation = $iconPath
} else {
    $lnk.IconLocation = "C:\Windows\System32\imageres.dll,15"
}

$lnk.Save()

Write-Host "[OK] Digital Lab shortcut created on Desktop"
Write-Host "    Double-click to choose: Web / GUI / CLI"