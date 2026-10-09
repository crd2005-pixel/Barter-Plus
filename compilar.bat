@echo off
echo Instalando dependencias y PyInstaller...
python -m pip install pyinstaller
echo Compilando Unificador de Listas...
python -m pyinstaller --noconfirm --onedir --windowed --noconsole --name "Unificador_BarterPlus" --icon=ICONO.ico --copy-metadata streamlit --add-data "app.py;." --hidden-import streamlit --hidden-import pandas --hidden-import openpyxl --hidden-import requests --hidden-import PyPDF2 --hidden-import sqlite3 run_streamlit.py
echo Compilacion finalizada.
pause
