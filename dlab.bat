@echo off
title Digital Lab
cd /d "%~dp0"

set "PYTHON="

py -c "exit(0)" >nul 2>&1
if not errorlevel 1 set "PYTHON=py" & goto :run

python3 -c "exit(0)" >nul 2>&1
if not errorlevel 1 set "PYTHON=python3" & goto :run

python -c "exit(0)" >nul 2>&1
if not errorlevel 1 set "PYTHON=python" & goto :run

for %%d in (
    "%LOCALAPPDATA%\Programs\Python\Python312"
    "%LOCALAPPDATA%\Programs\Python\Python311"
    "%LOCALAPPDATA%\Programs\Python\Python310"
    "%LOCALAPPDATA%\Programs\Python\Python39"
    "%LOCALAPPDATA%\Programs\Python\Python38"
    "%LOCALAPPDATA%\Programs\Python\Python37"
    "%ProgramFiles%\Python312"
    "%ProgramFiles%\Python311"
    "%ProgramFiles%\Python310"
    "%ProgramFiles%\Python39"
    "%ProgramFiles%\Python38"
    "%ProgramFiles%\Python37"
    "C:\Python312"
    "C:\Python311"
    "C:\Python310"
    "C:\Python39"
    "C:\Python38"
    "C:\Python37"
) do (
    if exist "%%d\python.exe" (
        set "PYTHON=%%d\python.exe"
        goto :run
    )
)

echo [ERROR] Python 3.7+ not found
echo Please install from https://www.python.org/downloads/
pause
exit /b 1

:run
if "%~1"=="" (
    "%PYTHON%" main.py
    pause
) else (
    "%PYTHON%" main.py %*
)
