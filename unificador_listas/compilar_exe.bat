@echo off
echo Preparando entorno de compilacion...
pip install pyinstaller

echo Limpiando compilaciones previas...
if exist "build" rmdir /s /q "build"
if exist "dist\UnificadorBarterPlus" rmdir /s /q "dist\UnificadorBarterPlus"

echo Compilando Unificador de Listas...
pyinstaller --noconfirm --onedir --windowed --name "UnificadorBarterPlus" --collect-all customtkinter --hidden-import sqlite3 --hidden-import openpyxl --hidden-import pdfplumber --hidden-import google.genai --hidden-import pydantic app.py

echo Compilacion finalizada. El ejecutable esta en la carpeta dist\UnificadorBarterPlus
pause