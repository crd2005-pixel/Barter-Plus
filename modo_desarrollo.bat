
@echo off
title Barter Plus - Entorno de Desarrollo
color 0F

echo ===================================================
echo Iniciando Modulo Barter Plus...
echo ===================================================
echo.

:: Ejecuta el script de Python.
:: Cuando pases a la fase final, cambia "init_db.py" por "main.py" o el nombre de tu archivo principal.
python main.py

echo.
echo ===================================================
echo Proceso finalizado. Si hay errores, revisa arriba.
echo ===================================================
pause