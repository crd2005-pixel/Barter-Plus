import datetime as dt
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from .. import Base

class Service(Base):
    __tablename__ = 'services'
    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey('clientes.id'))
    vehiculo = Column(String)
    kilometros = Column(Integer, default=0)
    fecha = Column(DateTime, default=dt.datetime.utcnow)

class ServiceHistorial(Base):
    __tablename__ = 'services_historial'
    id = Column(Integer, primary_key=True)
    service_id = Column(Integer, ForeignKey('services.id'))
    fecha = Column(DateTime, default=dt.datetime.utcnow)
    detalle = Column(Text, default='')
