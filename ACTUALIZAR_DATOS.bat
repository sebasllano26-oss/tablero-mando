@echo off
cd /d "%~dp0"
python "%~dp0actualizar_planes.py" %*
if errorlevel 1 (
    echo.
    echo No se publico una nueva carga. Los datos anteriores se conservan.
) else (
    echo.
    echo Carga publicada. Pulsa Recargar datos en el tablero.
)
pause
