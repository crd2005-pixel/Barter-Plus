import os
import streamlit
import PyInstaller.__main__

# Obtener la ruta física exacta de la librería instalada
streamlit_dir = os.path.dirname(streamlit.__file__)

PyInstaller.__main__.run([
    'main_exe.py',
    '--name=Unificador_BarterPlus',
    '--onedir',
    '--noconsole',  # Ocultamos la consola nuevamente
    f'--add-data={streamlit_dir};streamlit', # Clona la librería entera (incluye static/)
    '--add-data=app.py;.',
    '--copy-metadata=streamlit',
    '--hidden-import=streamlit',
    '--icon=ICONO.ico',
    '--noconfirm'
])
