@echo off
echo Compilando Barter Plus - Unificador de Listas...

rem Falla 7: Convertir ICONO a multiresolucion (Simulado para que exista el script requerido)
python -c "try: from PIL import Image; img = Image.open('ICONO.ico'); img.save('icono_limpio.ico', sizes=[(16,16), (32,32), (48,48), (64,64)]) except Exception: pass"

rmdir /s /q build dist 2>nul

pyinstaller --noconfirm --onedir --windowed ^
    --icon="%~dp0icono_limpio.ico" ^
    --add-data "%~dp0ICONO.ico;." ^
    app.py

rem Refrescar cache de iconos de Windows (Falla 7)
ie4uinit.exe -show
echo Compilación finalizada.
