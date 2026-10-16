@echo off
echo Iniciando Unificador de Listas...
python app.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo Ocurrio un error al ejecutar la aplicacion.
    pause
)