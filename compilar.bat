@echo off
echo Limpiando directorios antiguos...
rmdir /s /q build
rmdir /s /q dist

echo Compilando Unificador de Listas...
pyinstaller --noconfirm --onedir --windowed --noconsole --name "Unificador_BarterPlus" --copy-metadata streamlit --add-data "app.py;." --hidden-import streamlit --hidden-import pandas --hidden-import openpyxl --hidden-import requests --hidden-import PyPDF2 --hidden-import sqlite3 run_streamlit.py

echo Compilación finalizada.
pause
