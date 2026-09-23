import datetime as dt
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from .. import Base

class Cliente(Base):
    __tablename__ = 'clientes'
    id = Column(Integer, primary_key=True)
    nombre = Column(String)
    tipo = Column(String, default='minorista')
    cuit_dni = Column(String, index=True)
    condicion_iva = Column(String, default='Consumidor Final')
    telefono = Column(String)
    email = Column(String)
    direccion = Column(String)

class CuentaCorrienteCliente(Base):
    __tablename__ = "cuentas_corriente_clientes"
    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"))
    fecha = Column(DateTime, default=dt.datetime.utcnow)
    concepto = Column(String)
    monto = Column(Float, default=0.0)  # +deuda / -pago
