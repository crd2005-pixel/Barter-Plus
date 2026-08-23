import datetime as dt
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from .. import Base

class Garantia(Base):
    __tablename__ = 'garantias'
    id = Column(Integer, primary_key=True)
    venta_id = Column(Integer, ForeignKey('ventas.id'))
    producto_id = Column(Integer, ForeignKey('productos.id'))
    fecha = Column(DateTime, default=dt.datetime.utcnow)
    observaciones = Column(Text, default='')

class ReclamoGarantia(Base):
    __tablename__ = 'reclamos_garantia'
    id = Column(Integer, primary_key=True)
    garantia_id = Column(Integer, ForeignKey('garantias.id'))
    fecha = Column(DateTime, default=dt.datetime.utcnow)
    estado = Column(String, default='abierto')
    detalle = Column(Text, default='')
