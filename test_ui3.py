from unificador_listas.app import App
import tkinter as tk

app = App()

# Ensure we have the new buttons and no "Aplicar Cambios en Base de Datos"
# Oh wait, we just updated the text to "Guardar en Historial del Unificador (Base Propia)"

btn_apply = app.btn_apply_db.cget("text")
btn_export = app.btn_export_excel.cget("text")
print(f"Apply Button: {btn_apply}")
print(f"Export Button: {btn_export}")
