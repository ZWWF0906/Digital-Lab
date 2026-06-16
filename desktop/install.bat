@echo off
setlocal
set "LAB_ROOT=%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -LabRoot "%LAB_ROOT%"
echo.
pause