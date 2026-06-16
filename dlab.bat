@echo off
chcp 65001 >nul 2>&1
title Digital Lab
setlocal EnableDelayedExpansion

set "LAB_ROOT=%~dp0"
if "%LAB_ROOT:~-1%"=="\" set "LAB_ROOT=%LAB_ROOT:~0,-1%"

set "PYTHON="

python -c "exit(0)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON=python"
    goto :run
)

for %%d in (
    "%LOCALAPPDATA%\Programs\Python\Python314"
    "%LOCALAPPDATA%\Programs\Python\Python313"
    "%LOCALAPPDATA%\Programs\Python\Python312"
    "%LOCALAPPDATA%\Programs\Python\Python311"
    "%LOCALAPPDATA%\Programs\Python\Python310"
    "%ProgramFiles%\Python314"
    "%ProgramFiles%\Python313"
    "%ProgramFiles%\Python312"
    "%ProgramFiles%\Python311"
    "%ProgramFiles%\Python310"
    "C:\Python314"
    "C:\Python313"
    "C:\Python312"
    "C:\Python311"
    "C:\Python310"
) do (
    if exist "%%d\python.exe" (
        set "PYTHON=%%d\python.exe"
        goto :run
    )
)

echo [ERROR] Python 3.10+ not found
echo.
echo Please install Python from https://www.python.org/downloads/
echo Make sure to check "Add Python to PATH" during installation.
echo.
pause
exit /b

:run
cd /d "%LAB_ROOT%"
"%PYTHON%" "%LAB_ROOT%\main.py"
if %errorlevel% neq 0 (
    echo.
    echo ============================================
    echo [ERROR] Program exited with code %errorlevel%
    echo ============================================
)
pause
