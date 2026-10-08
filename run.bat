@echo off
:: Ejecucion Unificador (32-bit compat / Local Streamlit)
echo Iniciando Unificador de Listas... >> error_log.txt
python -m streamlit run app.py >> error_log.txt 2>&1
