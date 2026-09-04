@echo off
echo =========================================================
echo Compilando BarterPlus a un Ejecutable (.exe)
echo =========================================================
echo.
echo Asegurate de tener pyinstaller instalado: pip install pyinstaller
echo.

:: El flag --noconsole (o -w) oculta la ventana de CMD al ejecutar el programa
:: El flag --onefile genera un solo archivo .exe en la carpeta dist/

pyinstaller --noconsole --onefile --name "BarterPlus" main.py

echo.
echo =========================================================
echo Compilacion terminada. Revisa la carpeta "dist\"
echo para encontrar BarterPlus.exe
echo =========================================================
pause
