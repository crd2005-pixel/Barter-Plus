import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Configuramos la ruta absoluta de la base de datos para evitar problemas
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "barterplus.db")
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
