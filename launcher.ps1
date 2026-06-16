Add-Type -AssemblyName System.Windows.Forms, System.Drawing

$Host.UI.RawUI.WindowTitle = "Digital Lab"

$target = Split-Path -Parent $MyInvocation.MyCommand.Path
$mainPy = Join-Path $target "main.py"
$iconPath = Join-Path $target "interface"

if (-not (Test-Path $mainPy)) {
    [System.Windows.Forms.MessageBox]::Show("未找到 main.py，请检查安装目录。", "Digital Lab", "OK", "Error")
    exit 1
}

function Find-Python {
    try {
        python -c "exit(0)" 2>$null
        if ($LASTEXITCODE -eq 0) { return "python" }
    } catch {}
    $paths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python314",
        "$env:LOCALAPPDATA\Programs\Python\Python313",
        "$env:LOCALAPPDATA\Programs\Python\Python312",
        "$env:LOCALAPPDATA\Programs\Python\Python311",
        "$env:LOCALAPPDATA\Programs\Python\Python310",
        "$env:ProgramFiles\Python314",
        "$env:ProgramFiles\Python313",
        "$env:ProgramFiles\Python312",
        "C:\Python314", "C:\Python313", "C:\Python312"
    )
    foreach ($p in $paths) {
        $exe = Join-Path $p "python.exe"
        if (Test-Path $exe) { return $exe }
    }
    return $null
}

$python = Find-Python
if (-not $python) {
    [System.Windows.Forms.MessageBox]::Show(
        "未找到 Python。`n`n请访问 https://www.python.org/downloads/ 安装 Python 3.10+，`n安装时请勾选「Add Python to PATH」。",
        "Digital Lab — 缺少 Python", "OK", "Error")
    exit 1
}

function Start-Mode {
    param($argsStr)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $python
    $psi.Arguments = "`"$mainPy`" $argsStr"
    $psi.WorkingDirectory = $target
    $psi.UseShellExecute = $true
    [System.Diagnostics.Process]::Start($psi) | Out-Null
    $script:form.Close()
}

$form = New-Object System.Windows.Forms.Form
$form.Text = "Digital Lab — 启动选项"
$form.Size = New-Object System.Drawing.Size(460, 420)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 10)

$title = New-Object System.Windows.Forms.Label
$title.Text = "Digital Lab"
$title.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 18, [System.Drawing.FontStyle]::Bold)
$title.TextAlign = "MiddleCenter"
$title.Size = New-Object System.Drawing.Size(400, 40)
$title.Location = New-Object System.Drawing.Point(20, 20)
$title.ForeColor = [System.Drawing.Color]::FromArgb(30, 30, 30)
$form.Controls.Add($title)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Text = "个人数字实验室 · 请选择启动模式"
$subtitle.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 9)
$subtitle.TextAlign = "MiddleCenter"
$subtitle.Size = New-Object System.Drawing.Size(400, 25)
$subtitle.Location = New-Object System.Drawing.Point(20, 60)
$subtitle.ForeColor = [System.Drawing.Color]::FromArgb(140, 140, 140)
$form.Controls.Add($subtitle)

$sep = New-Object System.Windows.Forms.Label
$sep.BorderStyle = "Fixed3D"
$sep.Size = New-Object System.Drawing.Size(400, 2)
$sep.Location = New-Object System.Drawing.Point(20, 92)
$form.Controls.Add($sep)

function New-LaunchButton {
    param($text, $sub, $y, $color, $hoverColor, $argsStr)

    $btn = New-Object System.Windows.Forms.Button
    $btn.Text = $text
    $btn.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 13, [System.Drawing.FontStyle]::Bold)
    $btn.Size = New-Object System.Drawing.Size(400, 60)
    $btn.Location = New-Object System.Drawing.Point(20, $y)
    $btn.FlatStyle = "Flat"
    $btn.FlatAppearance.BorderSize = 0
    $btn.BackColor = $color
    $btn.ForeColor = [System.Drawing.Color]::White
    $btn.Cursor = "Hand"
    $btn.Add_Click({ Start-Mode $argsStr })

    $hoverIn = {
        $this.BackColor = $hoverColor
        $this.FlatAppearance.BorderSize = 0
    }
    $hoverOut = {
        $this.BackColor = $color
        $this.FlatAppearance.BorderSize = 0
    }
    $btn.Add_MouseEnter($hoverIn)
    $btn.Add_MouseLeave($hoverOut)

    $lbl = New-Object System.Windows.Forms.Label
    $lbl.Text = $sub
    $lbl.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 8)
    $lbl.ForeColor = [System.Drawing.Color]::FromArgb(120, 120, 120)
    $lbl.Size = New-Object System.Drawing.Size(400, 18)
    $lbl.Location = New-Object System.Drawing.Point(20, $y + 62)
    $lbl.TextAlign = "MiddleCenter"

    $form.Controls.Add($btn)
    $form.Controls.Add($lbl)
}

New-LaunchButton "Web 仪表盘" "在浏览器中打开实时监控面板" 108 ([System.Drawing.Color]::FromArgb(30, 144, 255)) ([System.Drawing.Color]::FromArgb(0, 110, 220)) "dashboard"
New-LaunchButton "桌面控制台" "打开桌面 GUI 程序" 192 ([System.Drawing.Color]::FromArgb(78, 205, 196)) ([System.Drawing.Color]::FromArgb(50, 170, 160)) "gui"
New-LaunchButton "命令行菜单" "打开交互式命令行选择界面" 276 ([System.Drawing.Color]::FromArgb(155, 89, 182)) ([System.Drawing.Color]::FromArgb(120, 60, 150)) ""

$form.ShowDialog() | Out-Null
