@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

set LOG_FILE=run_log.txt
echo [%DATE% %TIME%] Inicio Stock Monitor > %LOG_FILE%

echo.
echo === G360 Stock Monitor CIPSA - Inicio ===
echo.

REM ============================================
REM [1/5] Verificar / Instalar uv
echo [%DATE% %TIME%] [1/5] Verificando uv... >> %LOG_FILE%
echo [1/5] Verificando uv...

where uv >nul 2>&1
if errorlevel 1 (
    if exist "uv.exe" (
        echo   Usando uv.exe local...
        set "PATH=%~dp0;%PATH%"
    ) else (
        echo   uv no encontrado. Descargando e instalando...
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" >> %LOG_FILE% 2>&1
        if errorlevel 1 (
            echo [%DATE% %TIME%] [ERROR] No se pudo instalar uv >> %LOG_FILE%
            echo   ERROR: No se pudo instalar uv automaticamente.
            echo   Descargue manualmente de: https://docs.astral.sh/uv/
            msg * "G360 Stock Monitor: No se pudo instalar uv. Desinstale manualmente de https://docs.astral.sh/uv/"
            pause
            exit /b 1
        )
        echo   uv instalado correctamente.
    )
) else (
    echo   uv encontrado.
)

REM Refresh PATH to include newly installed uv
for /f "tokens=*" %%i in ('where uv 2^>nul') do set "UV_PATH=%%~dpi"
if defined UV_PATH set "PATH=%UV_PATH%;%PATH%"

REM Fallback to common install locations
where uv >nul 2>&1
if errorlevel 1 (
    if exist "%USERPROFILE%\.cargo\bin\uv.exe" (
        set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
    ) else if exist "%USERPROFILE%\.local\bin\uv.exe" (
        set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    )
)

echo.

REM ============================================
REM [2/5] Verificar / Instalar Python 3.11
echo [%DATE% %TIME%] [2/5] Verificando Python 3.11... >> %LOG_FILE%
echo [2/5] Verificando Python 3.11...

where uv >nul 2>&1
if errorlevel 1 (
    echo   ERROR: uv no disponible. No se puede instalar Python.
    pause
    exit /b 1
)

uv python list --only-installed 2>nul | find "3.11" >nul
if errorlevel 1 (
    echo   Python 3.11 no encontrado. Instalando con uv...
    uv python install 3.11 >> %LOG_FILE% 2>&1
    if errorlevel 1 (
        echo [%DATE% %TIME%] [ERROR] No se pudo instalar Python 3.11 >> %LOG_FILE%
        echo   ERROR: No se pudo instalar Python 3.11.
        msg * "G360 Stock Monitor: No se pudo instalar Python 3.11. Revise run_log.txt"
        pause
        exit /b 1
    )
    echo   Python 3.11 instalado.
) else (
    echo   Python 3.11 encontrado.
)

echo.

REM ============================================
REM [3/5] Crear entorno virtual e instalar dependencias
echo [%DATE% %TIME%] [3/5] Configurando entorno virtual... >> %LOG_FILE%
echo [3/5] Configurando entorno virtual...
if not exist ".venv\Scripts\python.exe" (
    echo   Creando entorno virtual...
    uv venv .venv --python 3.11 >> %LOG_FILE% 2>&1
    if errorlevel 1 (
        echo [%DATE% %TIME%] [ERROR] No se pudo crear el entorno virtual >> %LOG_FILE%
        echo   ERROR: No se pudo crear el entorno virtual.
        msg * "G360 Stock Monitor: No se pudo crear el entorno virtual. Revise run_log.txt"
        pause
        exit /b 1
    )
    echo   Entorno virtual creado.
)

echo   Instalando dependencias...
uv sync >> %LOG_FILE% 2>&1
if errorlevel 1 (
    echo [%DATE% %TIME%] [ERROR] Error al sincronizar dependencias >> %LOG_FILE%
    echo   ERROR: No se pudieron instalar las dependencias.
    echo   Revise %LOG_FILE% para mas detalles.
    msg * "G360 Stock Monitor: No se pudieron instalar las dependencias. Revise run_log.txt"
    pause
    exit /b 1
)
echo [%DATE% %TIME%] [3/5] Dependencias instaladas >> %LOG_FILE%
echo   Dependencias instaladas.

echo.

REM ============================================
REM [4/5] Verificar Windows Update + acceso directo
REM ============================================
echo [%DATE% %TIME%] [4/5] Verificando Windows Update... >> %LOG_FILE%
echo [4/5] Verificando actualizaciones de Windows...
powershell -NoProfile -Command "try{$u=(New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher().Search('IsInstalled=0').Updates;if($u.Count-gt0){Write-Host '  Hay '$u.Count' actualizaciones pendientes'}else{Write-Host '  Windows actualizado'}}catch{Write-Host '  No se pudo verificar (COM no disponible)'}"
echo   Creando acceso directo...

if exist "create_shortcut.vbs" (
    cscript //nologo create_shortcut.vbs >> %LOG_FILE% 2>&1
    echo [%DATE% %TIME%] [4/5] Acceso directo creado >> %LOG_FILE%
    echo   Acceso directo creado en el escritorio.
) else (
    echo   create_shortcut.vbs no encontrado - omitiendo.
)

echo.

REM ============================================
REM [5/5] Iniciar aplicacion
echo [%DATE% %TIME%] [5/5] Iniciando Stock Monitor CIPSA... >> %LOG_FILE%
echo [5/5] Iniciando Stock Monitor CIPSA...
echo.

echo [%DATE% %TIME%] [5/5] Lanzando aplicacion... >> %LOG_FILE%
.venv\Scripts\python.exe main.py
if errorlevel 1 (
    echo [%DATE% %TIME%] [ERROR] La aplicacion fallo >> %LOG_FILE%
    echo.
    echo La aplicacion fallo. Revise %LOG_FILE% para mas detalles.
    msg * "G360 Stock Monitor: La aplicacion fallo. Revise run_log.txt para mas detalles."
    echo Presione una tecla para salir...
    pause
)

echo [%DATE% %TIME%] Stock Monitor terminado normalmente >> %LOG_FILE%
echo.
echo === Stock Monitor CIPSA terminado ===
echo.
