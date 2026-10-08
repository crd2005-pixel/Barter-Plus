@echo off
:: Ejecucion Unificador (32-bit compat / Local Streamlit)
cd /d "%~dp0"
echo Iniciando Unificador de Listas... >> "%~dp0error_log.txt" 2>nul
python -m streamlit run app.py >> "%~dp0error_log.txt" 2>&1
