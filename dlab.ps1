$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$python = $null
@("py", "python3", "python") | ForEach-Object {
    $found = Get-Command $_ -ErrorAction SilentlyContinue
    if ($found) {
        try {
            $versionCheck = & $_ -c "import sys; print(sys.version_info[:2] >= (3,7))"
            if ($versionCheck -eq "True") {
                $python = $_
                return
            }
        } catch {}
    }
}

if (-not $python) {
    Write-Host "[ERROR] 未找到 Python 3.7+" -ForegroundColor Red
    Write-Host "请从 https://www.python.org/downloads/ 安装 Python"
    exit 1
}

Write-Host "正在启动 Digital Lab..." -ForegroundColor Cyan

& $python "$ScriptDir\main.py" @args
exit $LASTEXITCODE
