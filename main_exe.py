import sys
import os
import streamlit.web.bootstrap

if __name__ == "__main__":
    # Configurar variables de entorno críticas para empaquetado
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"

    # Determinar la ruta real del script
    if getattr(sys, 'frozen', False):
        app_path = os.path.join(sys._MEIPASS, 'app.py')
    else:
        app_path = os.path.abspath('app.py')

    # Validación de existencia (evita el 404 silencioso)
    if not os.path.exists(app_path):
        print(f"ERROR CRÍTICO: No se encuentra app.py en {app_path}")
        sys.exit(1)

    # Ejecución directa del motor
    print(f"Iniciando Streamlit desde: {app_path}")
    streamlit.web.bootstrap.run(app_path, "", [], flag_options={})
