@echo off
echo Preparando entorno de compilacion...
pip install pyinstaller

echo Instalando dependencias de compilacion...
pip install Pillow

echo Convirtiendo y validando ICONO.ico...
python -c "from PIL import Image; import os; img = Image.open('ICONO.ico') if os.path.exists('ICONO.ico') else Image.new('RGB', (256, 256)); img.save('icono_limpio.ico')"

echo Limpiando compilaciones previas...
if exist "build" rmdir /s /q "build"
if exist "dist\UnificadorBarterPlus" rmdir /s /q "dist\UnificadorBarterPlus"
if exist "UnificadorBarterPlus.spec" del /q "UnificadorBarterPlus.spec"

echo Compilando Unificador de Listas...
pyinstaller --noconfirm --onedir --windowed --name "UnificadorBarterPlus" --icon="%~dp0icono_limpio.ico" --add-data "%~dp0ICONO.ico;." --collect-all customtkinter --collect-all pdfplumber --collect-all pdfminer --hidden-import sqlite3 --hidden-import openpyxl --hidden-import google.genai --hidden-import pydantic app.py

echo Compilacion finalizada. El ejecutable esta en la carpeta dist\UnificadorBarterPlus
pause