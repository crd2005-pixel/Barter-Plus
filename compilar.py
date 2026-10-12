import PyInstaller.__main__

PyInstaller.__main__.run([
    'main_exe.py',
    '--name=Unificador_BarterPlus',
    '--onedir',
    '--collect-all=streamlit',
    '--add-data=app.py;.',
    '--copy-metadata=streamlit',
    '--icon=ICONO.ico',
    '--noconfirm'
])
