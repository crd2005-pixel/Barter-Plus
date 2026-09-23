from sqlalchemy import Column, Integer, String
from .. import Base

class Configuracion(Base):
    __tablename__ = 'configuracion'
    id = Column(Integer, primary_key=True)
    clave_admin = Column(String)
    nombre_negocio = Column(String)
