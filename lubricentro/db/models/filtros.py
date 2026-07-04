from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from .. import Base

class Filtro(Base):
    __tablename__ = 'filtros'
    id = Column(Integer, primary_key=True)
    codigo = Column(String, index=True, unique=True)
    marca = Column(String, index=True)
    modelo = Column(String, index=True)
    equivalencias = relationship("EquivalenciaFiltro", back_populates="filtro", cascade="all, delete-orphan")

class EquivalenciaFiltro(Base):
    __tablename__ = 'equivalencias_filtros'
    id = Column(Integer, primary_key=True)
    filtro_id = Column(Integer, ForeignKey('filtros.id'))
    marca = Column(String)
    codigo = Column(String)
    filtro = relationship("Filtro", back_populates="equivalencias")
