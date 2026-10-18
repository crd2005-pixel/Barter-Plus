from sqlalchemy import Column, Integer, String
from .. import Base

class ConfigParam(Base):
    __tablename__ = 'config_params'
    id = Column(Integer, primary_key=True)
    clave = Column(String, unique=True, index=True)
    valor = Column(String, default='')
