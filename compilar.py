import os
import streamlit
import PyInstaller.__main__

streamlit_dir = os.path.dirname(streamlit.__file__)
static_dir = os.path.join(streamlit_dir, 'static')
runtime_dir = os.path.join(streamlit_dir, 'runtime')

PyInstaller.__main__.run([
    'main_exe.py', # El entry point
    '--name=Unificador_BarterPlus',
    '--onedir',
    '--windowed',
    '--noconsole',
    f'--add-data={static_dir};streamlit/static',
    f'--add-data={runtime_dir};streamlit/runtime',
    '--add-data=app.py;.',
    '--copy-metadata=streamlit',
    '--icon=ICONO.ico',
    '--noconfirm'
])
