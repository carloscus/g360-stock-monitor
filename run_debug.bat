@echo off
setlocal
cd /d "%~dp0"

echo ======================================== > run_debug.log
echo G360 Stock Monitor - Diagnostico >> run_debug.log
echo Fecha: %DATE% %TIME% >> run_debug.log
echo ======================================== >> run_debug.log
echo. >> run_debug.log

echo [1] Verificando .venv... >> run_debug.log
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: No existe .venv\Scripts\python.exe >> run_debug.log
    echo. >> run_debug.log
    echo ERROR: No se encontro el entorno virtual. >> run_debug.log
    echo Ejecuta run.bat primero para instalar dependencias. >> run_debug.log
    goto :end
)

echo [2] Ejecutando main.py... >> run_debug.log
.venv\Scripts\python.exe main.py >> run_debug.log 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

echo. >> run_debug.log
echo [3] Codigo de salida: %EXIT_CODE% >> run_debug.log

:end
echo ======================================== >> run_debug.log
echo Fin del diagnostico >> run_debug.log
echo ======================================== >> run_debug.log

if %EXIT_CODE% NEQ 0 (
    echo.
    echo ========================================
    echo  G360 Stock Monitor - Error detectado
    echo ========================================
    echo.
    echo Se encontro un error durante la ejecucion.
    echo Revisa el archivo run_debug.log para mas detalles.
    echo.
    echo Contenido del log:
    echo ----------------------------------------
    type run_debug.log
    echo ----------------------------------------
    echo.
    pause
)
