@echo off
cd /d "%~dp0"
python "%~dp0preparar_repo_streamlit.py"
if errorlevel 1 (
    echo.
    echo No se pudo preparar el paquete. Revisa el mensaje anterior.
) else (
    echo.
    echo Sube el contenido de repo_streamlit a la raiz del repositorio privado.
    echo Tambien esta disponible tablero_streamlit_repo.zip.
)
pause
