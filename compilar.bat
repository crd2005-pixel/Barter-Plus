@echo off
echo Limpiando builds anteriores...
rmdir /s /q build
rmdir /s /q dist

echo Compilando Unificador de Listas...
pyinstaller --noconfirm --onedir --windowed --noconsole --icon="icono_unificador.ico" ^
--name "Unificador de Listas" ^
--add-data "icono_unificador.ico;." ^
--hidden-import=pandas ^
--hidden-import=openpyxl ^
--hidden-import=PyPDF2 ^
--hidden-import=tabula ^
--hidden-import=streamlit ^
--hidden-import=sqlite3 ^
--hidden-import=requests ^
--hidden-import=json ^
--hidden-import=io ^
--hidden-import=time ^
--hidden-import=datetime ^
--hidden-import=re ^
--hidden-import=hashlib ^
app.py

echo Proceso terminado.
pause
