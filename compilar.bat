@echo off
echo Instalando PyInstaller...
pip install pyinstaller
echo Empaquetando Barter Plus...
pyinstaller --noconsole --noconfirm --name="Barter Plus" --add-data "core;core" --add-data "database;database" --add-data "services;services" --add-data "src;src" --add-data "ui;ui" --add-data "utils;utils" main.py
echo.
echo Compilacion terminada. Revisa la carpeta "dist\Barter Plus".
pause