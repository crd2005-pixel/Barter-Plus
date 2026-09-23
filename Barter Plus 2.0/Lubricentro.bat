@echo off
title Barter Plus - AUTOSETUP COMPLETO
color 1f
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
set "MAIN=main.py"
set "VENV=%ROOT%.venv"
set "PYTHON=%VENV%\Scripts\python.exe"
set "REQ=requirements.txt"
set "LOGDIR=%ROOT%logs"
set "ERRLOG=%LOGDIR%\errores_BarterPlus.log"
set "RUNLOG=%LOGDIR%\run.log"

if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>&1

cls
echo ==========================================================
echo          BARTER PLUS - INICIO AUTOMATICO COMPLETO
echo ==========================================================
echo.
echo   1) Abrir el programa directamente
echo   2) Reparar entorno, instalar todo y abrir
echo.
set /p "opcion=Elige una opcion [1-2]: "
echo.

if "%opcion%"=="1" goto ejecutar
if "%opcion%"=="2" goto reparar
echo Opcion no valida.
pause
exit /b

:buscar_python
if exist "%PYTHON%" (
    set "PYCMD=%PYTHON%"
    goto :eof
)
for /f "delims=" %%p in ('where python 2^>nul') do (
    set "PYCMD=%%p"
    goto :eof
)
echo No se encontro Python instalado.
echo Instala Python 3.10 o superior y reintenta.
pause
exit /b

:reparar
call :buscar_python

echo ----------------------------------------------------------
echo Creando entorno virtual si falta...
echo ----------------------------------------------------------
if not exist "%PYTHON%" "%PYCMD%" -m venv "%VENV%"

rem asegurar que a partir de aqui se use el python del venv
set "PYTHON=%VENV%\Scripts\python.exe"

echo ----------------------------------------------------------
echo Actualizando pip/setuptools (silencioso)...
echo ----------------------------------------------------------
"%PYTHON%" -m pip install --upgrade -q pip setuptools wheel >> "%RUNLOG%" 2>>"%ERRLOG%"

echo ----------------------------------------------------------
echo Instalando dependencias (silencioso)...
echo ----------------------------------------------------------
if exist "%REQ%" (
    "%PYTHON%" -m pip install -q -r "%REQ%" >> "%RUNLOG%" 2>>"%ERRLOG%"
) else (
    "%PYTHON%" -m pip install -q PyQt5 SQLAlchemy reportlab openpyxl pandas >> "%RUNLOG%" 2>>"%ERRLOG%"
)

echo ----------------------------------------------------------
echo Limpiando caches...
echo ----------------------------------------------------------
for /r "%ROOT%" %%i in (*.pyc) do del /f /q "%%i" >nul 2>&1
for /f "delims=" %%d in ('dir /b /s /ad "%ROOT%__pycache__" 2^>nul') do rmdir /s /q "%%d" >nul 2>&1

echo ----------------------------------------------------------
echo Creando/verificando metadata...
echo ----------------------------------------------------------
"%PYTHON%" -c "from db import Base, engine; import db.models  # noqa: F401; Base.metadata.create_all(engine)" >> "%RUNLOG%" 2>>"%ERRLOG%"

echo ----------------------------------------------------------
echo Ejecutando migraciones...
echo ----------------------------------------------------------
if exist "%ROOT%migrar_db.py" (
    "%PYTHON%" "%ROOT%migrar_db.py" >> "%RUNLOG%" 2>>"%ERRLOG%"
) else (
    echo ATENCION: migrar_db.py no encontrado. >> "%ERRLOG%"
)

goto ejecutar

:ejecutar
call :buscar_python

if not exist "%MAIN%" (
    echo No se encontro %MAIN%.
    pause
    exit /b
)

echo ---------------------------------------------------------- >> "%ERRLOG%"
echo [Inicio: %date% %time%] >> "%ERRLOG%"
echo ---------------------------------------------------------- >> "%ERRLOG%"

echo Iniciando Barter Plus...
"%PYTHON%" "%MAIN%" 2>>"%ERRLOG%"

if errorlevel 1 (
    echo.
    echo ==========================================================
    echo Se detecto un error al ejecutar el programa.
    echo Intentando corregir dependencias automaticamente...
    echo ==========================================================
    "%PYTHON%" -m pip install -q PyQt5 SQLAlchemy reportlab openpyxl pandas >> "%RUNLOG%" 2>>"%ERRLOG%"
    echo Reintentando ejecucion...
    "%PYTHON%" "%MAIN%" 2>>"%ERRLOG%"
    if errorlevel 1 (
        echo Error persistente. Revisa el log:
        echo %ERRLOG%
        pause
    ) else (
        echo Programa iniciado correctamente tras reparacion.
        pause
    )
) else (
    echo Programa finalizado correctamente.
    pause
)
exit /b
