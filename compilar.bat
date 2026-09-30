@echo off
echo Limpiando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo Empaquetando Barter Plus...
pyinstaller --noconsole --noconfirm --name="Barter Plus" --icon="logo.ico" main.py

echo.
echo Compilacion terminada.
pause