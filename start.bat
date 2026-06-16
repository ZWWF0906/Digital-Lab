@echo off
chcp 65001 >nul 2>&1
title Digital Lab
setlocal EnableDelayedExpansion

set "LAB_ROOT=%~dp0"
if "%LAB_ROOT:~-1%"=="\" set "LAB_ROOT=%LAB_ROOT:~0,-1%"
cd /d "%LAB_ROOT%"

set "LOG=%LAB_ROOT%\startup.log"
> "%LOG%" echo [%date% %time%] start.bat running

set "PYTHON="

python -c "exit(0)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON=python"
    >> "%LOG%" echo [%date% %time%] python from PATH
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
    "C:\Python314"  "C:\Python313"  "C:\Python312"  "C:\Python311"  "C:\Python310"
) do (
    if exist "%%d\python.exe" (
        set "PYTHON=%%d\python.exe"
        >> "%LOG%" echo [%date% %time%] python: %%d
        goto :run
    )
)

>> "%LOG%" echo [%date% %time%] ERROR: no python found
echo.
echo ============================================
echo [ERROR] Python 3.10+ not found
echo.
echo Install from https://www.python.org/downloads/
echo Check "Add Python to PATH" during installation.
echo ============================================
echo.
pause
exit /b

:run
>> "%LOG%" echo [%date% %time%] cwd=%LAB_ROOT%
>> "%LOG%" echo [%date% %time%] run: "%PYTHON%" launcher.py

"%PYTHON%" "%LAB_ROOT%\launcher.py"
set "EXITCODE=%errorlevel%"
>> "%LOG%" echo [%date% %time%] launcher.py exit: %EXITCODE%

if %EXITCODE% neq 0 (
    echo.
    echo ============================================
    echo [WARN] Launcher crashed (exit %EXITCODE%)
    echo Trying fallback: main.py ...
    echo ============================================
    >> "%LOG%" echo [%date% %time%] fallback to main.py
    "%PYTHON%" "%LAB_ROOT%\main.py"
    set "EXITCODE=%errorlevel%"
)

if %EXITCODE% neq 0 (
    echo.
    echo ============================================
    echo [ERROR] All attempts failed (exit %EXITCODE%)
    echo Log: %LAB_ROOT%\startup.log
    echo ============================================
)

pause
