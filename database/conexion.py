import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# 1. Obtener la ruta de %APPDATA%
appdata_dir = os.environ.get('APPDATA')
if not appdata_dir:
    # Fallback si no está definida la variable (ej. en Mac/Linux o entornos raros)
    appdata_dir = os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming')

# 2. Configurar la carpeta específica del sistema
APP_DIR = os.path.join(appdata_dir, "BarterPlus")

# 3. Crear el directorio si no existe ANTES de conectar la base de datos
os.makedirs(APP_DIR, exist_ok=True)

# 4. Definir la ruta final de la base de datos
DB_PATH = os.path.join(APP_DIR, "barterplus.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Configuración del motor (engine)
# echo=False para evitar loggear todas las queries en producción
engine = create_engine(DATABASE_URL, echo=False)

# Configuración de la sesión
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Clase base declarativa para los modelos (Sintaxis SQLAlchemy 2.0)
class Base(DeclarativeBase):
    pass

def get_session():
    """Genera una nueva sesión para interactuar con la base de datos."""
    return SessionLocal()
