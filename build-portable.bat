@echo off
chcp 65001 >nul
title G360 - Build Portable EXE

echo.
echo ==============================================
echo   G360 Stock Monitor - Build Portable EXE
echo   Genera un .exe standalone (sin Python)
echo ==============================================
echo.

:: --- 1. Verificar/instalar uv ---
where uv >nul 2>&1
if errorlevel 1 (
    echo [SETUP] uv no encontrado. Instalando...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 (
        echo ERROR: No se pudo instalar uv.
        pause
        exit /b 1
    )
    for /f "tokens=*" %%a in ('uv --version') do set "UV_OK=%%a"
)
echo [CHECK] uv: OK

:: --- 2. Crear .venv si no existe ---
if not exist ".venv" (
    echo [SETUP] Creando entorno virtual...
    uv venv
)
echo [VENV] .venv: OK

:: --- 3. Sincronizar dependencias ---
echo [SETUP] Sincronizando dependencias...
uv sync

:: --- 3.5. Instalar PyInstaller para el build ---
echo [SETUP] Instalando PyInstaller...
uv pip install pyinstaller

:: --- 4. Verificar archivo principal ---
if not exist "main.py" (
    echo ERROR: main.py no encontrado
    pause
    exit /b 1
)

:: --- 5. Build con PyInstaller ---
echo.
echo [BUILD] Generando ejecutable portable: g360-stock-monitor.exe
echo.

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo ERROR: No se encontro python.exe en el venv.
    pause
    exit /b 1
)

echo [BUILD] Ejecutando PyInstaller con: %PYTHON_EXE%
echo.

"%PYTHON_EXE%" -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "g360-stock-monitor" ^
    --add-data "%~dp0src;src" ^
    --add-data "%~dp0assets;assets" ^
    --add-data "%~dp0skill.json;." ^
    --add-data "%~dp0pyproject.toml;." ^
    --icon "%~dp0assets\images\cipsa.ico" ^
    --distpath "%~dp0dist" ^
    --workpath "%~dp0build\pyinstaller" ^
    --specpath "%~dp0build" ^
    --noconfirm ^
    "%~dp0main.py"

if errorlevel 1 (
    echo.
    echo ERROR: Fallo la generacion del ejecutable.
    pause
    exit /b 1
)

:: --- 6. Limpiar temporales ---
if exist "build" (
    echo [CLEAN] Limpiando archivos temporales...
    rmdir /s /q build
)

echo.
echo ==============================================
echo   BUILD EXITOSO
echo   Ejecutable: dist\g360-stock-monitor.exe
echo ==============================================
echo.

pause
