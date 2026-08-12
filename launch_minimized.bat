@echo off
setlocal
cd /d "%~dp0"

REM Always delegate to run.bat for proper error handling.
REM run.bat has a quick-path: if .venv exists, skips all setup and launches
REM directly with visible error messages on failure.
REM If .venv doesn't exist, run.bat does full first-time setup with progress.
call run.bat
exit /b
