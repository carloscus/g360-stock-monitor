@echo off
setlocal
cd /d "%~dp0"

REM Check if Python venv exists
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo ========================================
    echo  G360 Stock Monitor - Primera ejecucion
    echo ========================================
    echo.
    echo Iniciando instalacion automatica...
    echo.
    call run.bat
    exit /b
)

REM If venv exists, run minimized using PowerShell
powershell -NoProfile -Command "Start-Process -FilePath '%~dp0.venv\Scripts\python.exe' -ArgumentList 'main.py' -WorkingDirectory '%~dp0' -WindowStyle Hidden"
