@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

set LOG_FILE=run_log.txt
echo [%DATE% %TIME%] Inicio Stock Monitor >> %LOG_FILE%
echo.
echo === G360 Stock Monitor CIPSA - Inicio ===
echo.

REM --- Quick path: skip full setup if venv already exists ---
if exist ".venv\Scripts\python.exe" (
    echo Entorno ya configurado. Iniciando rapidamente...
    echo [%DATE% %TIME%] Quick-start activado >> %LOG_FILE%
    where uv >nul 2>&1 && uv sync >> %LOG_FILE% 2>&1
    goto :launch_app
)

REM ============================================
REM [PRE] Verificar conectividad a internet
echo [%DATE% %TIME%] [PRE] Verificando conexion a internet... >> %LOG_FILE%
echo [PRE] Verificando conexion a internet...

set "INTERNET_OK=0"
for /f "delims=" %%p in ('powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'https://astral.sh' -UseBasicParsing -TimeoutSec 5).StatusCode } catch { 500 }" 2^>nul') do set "INTERNET_OK=%%p"

if "!INTERNET_OK!"=="200" (
    echo   Conexion a internet OK.
) else (
    echo [%DATE% %TIME%] [ERROR] Sin conexion a internet >> %LOG_FILE%
    echo   ERROR: No se detecto conexion a internet.
    echo   Revise su conexion y vuelva a intentar.
    pause
    exit /b 1
)
echo.

REM ============================================
REM [1/5] Verificar / Instalar uv (local al portable)
echo [%DATE% %TIME%] [1/5] Verificando uv... >> %LOG_FILE%
echo [1/5] Verificando uv...

set "UV_EXE=%~dp0uv.exe"
set "UV_OK=0"

where uv >nul 2>&1
if not errorlevel 1 (
    echo   uv encontrado en PATH.
    set "UV_OK=1"
    goto :uv_done
)

if exist "%UV_EXE%" (
    echo   Usando uv.exe local...
    set "PATH=%~dp0;%PATH%"
    set "UV_OK=1"
    goto :uv_done
)

echo   uv no encontrado. Descargando...
call :download_uv
if not "!UV_OK!"=="1" (
    echo [%DATE% %TIME%] [ERROR] No se pudo instalar uv >> %LOG_FILE%
    echo   ERROR: No se pudo instalar uv despues de 3 intentos.
    echo   Descargue manualmente de: https://docs.astral.sh/uv/
    pause
    exit /b 1
)

:uv_done
echo [%DATE% %TIME%] [1/5] uv OK >> %LOG_FILE%
echo.

REM ============================================
REM [2/5] Verificar / Instalar Python 3.11
echo [%DATE% %TIME%] [2/5] Verificando Python 3.11... >> %LOG_FILE%
echo [2/5] Verificando Python 3.11...

set "PYTHON_OK=0"
uv python list --only-installed 2>nul | find "3.11" >nul
if not errorlevel 1 (
    echo   Python 3.11 encontrado.
    set "PYTHON_OK=1"
    goto :python_done
)

echo   Python 3.11 no encontrado. Instalando con uv (puede tardar 1-2 minutos)...
call :install_python
if not "!PYTHON_OK!"=="1" (
    echo [%DATE% %TIME%] [ERROR] No se pudo instalar Python 3.11 >> %LOG_FILE%
    echo   ERROR: No se pudo instalar Python 3.11 despues de 2 intentos.
    echo   Revise %LOG_FILE% para mas detalles.
    pause
    exit /b 1
)

:python_done
echo [%DATE% %TIME%] [2/5] Python OK >> %LOG_FILE%
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
        pause
        exit /b 1
    )
    echo   Entorno virtual creado.
)

echo   Instalando dependencias (puede tardar 1-2 minutos en primera ejecucion)...
uv sync >> %LOG_FILE% 2>&1
if errorlevel 1 (
    echo [%DATE% %TIME%] [ERROR] Error al sincronizar dependencias >> %LOG_FILE%
    echo   ERROR: No se pudieron instalar las dependencias.
    echo   Revise %LOG_FILE% para mas detalles.
    pause
    exit /b 1
)
echo [%DATE% %TIME%] [3/5] Dependencias instaladas >> %LOG_FILE%
echo   Dependencias instaladas.
echo.

REM ============================================
REM [4/5] Crear acceso directo con icono CIPSA
echo [%DATE% %TIME%] [4/5] Creando acceso directo... >> %LOG_FILE%
echo [4/5] Creando acceso directo...

if exist "create_shortcut.vbs" (
    cscript //nologo create_shortcut.vbs >> %LOG_FILE% 2>&1
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

:launch_app
echo [%DATE% %TIME%] Lanzando aplicacion... >> %LOG_FILE%
.venv\Scripts\python.exe main.py
if errorlevel 1 (
    echo [%DATE% %TIME%] [ERROR] La aplicacion fallo >> %LOG_FILE%
    echo.
    echo La aplicacion fallo. Revise %LOG_FILE% para mas detalles.
    echo Presione una tecla para salir...
    pause
)

echo [%DATE% %TIME%] Stock Monitor terminado normalmente >> %LOG_FILE%
echo.
echo === Stock Monitor CIPSA terminado ===
echo.
exit /b

REM --- Subroutines ---

:download_uv
echo   Descargando uv (instalador)...
powershell -ExecutionPolicy ByPass -NoProfile -Command "try { Invoke-WebRequest -Uri 'https://astral.sh/uv/install.ps1' -OutFile '%~dp0uv-install.ps1' -UseBasicParsing; exit 0 } catch { exit 1 }"
if errorlevel 1 (
    echo   Error al descargar uv. Reintentando...
    timeout /t 3 /nobreak >nul
    exit /b 1
)
echo   Instalando uv localmente...
powershell -ExecutionPolicy ByPass -NoProfile -c ". '%~dp0uv-install.ps1'" >> %LOG_FILE% 2>&1
del /f /q "%~dp0uv-install.ps1" >nul 2>&1
if exist "%UV_EXE%" (
    echo   uv instalado localmente.
    set "PATH=%~dp0;%PATH%"
    set "UV_OK=1"
    exit /b 0
)
echo   uv no se encontro despues de la instalacion.
exit /b 1

:install_python
for /l %%i in (1,1,2) do (
    echo   Intento %%i: Instalando Python 3.11...
    uv python install 3.11 >> %LOG_FILE% 2>&1
    if not errorlevel 1 (
        set "PYTHON_OK=1"
        exit /b 0
    )
    echo   Intento %%i fallido. Reintentando en 5s...
    timeout /t 5 /nobreak >nul
)
exit /b 1
