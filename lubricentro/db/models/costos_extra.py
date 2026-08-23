# db/models/costos_extra.py
import datetime as dt
from sqlalchemy import Column, Integer, String, Float, Date, Boolean, ForeignKey
from .. import Base

class CreditoNegocio(Base):
    __tablename__ = "creditos_negocio"
    id = Column(Integer, primary_key=True)
    descripcion = Column(String, nullable=False)
    monto_total = Column(Float, default=0.0, nullable=False)
    monto_cuota = Column(Float, default=0.0, nullable=False)
    cant_cuotas = Column(Integer, default=1, nullable=False)
    fecha_inicio = Column(Date, nullable=False, default=dt.date.today)
    dia_vencimiento = Column(Integer, default=1, nullable=False)

class CreditoCuota(Base):
    __tablename__ = "creditos_cuotas"
    id = Column(Integer, primary_key=True)
    credito_id = Column(Integer, ForeignKey("creditos_negocio.id"), nullable=False)
    fecha_venc = Column(Date, nullable=False)
    monto = Column(Float, default=0.0, nullable=False)
    pagado = Column(Boolean, default=False, nullable=False)

class AdelantoSueldo(Base):
    __tablename__ = "sueldos_adelantos"
    id = Column(Integer, primary_key=True)
    empleado_id = Column(Integer, ForeignKey("empleados.id"), nullable=False)
    fecha = Column(Date, nullable=False, default=dt.date.today)
    monto = Column(Float, default=0.0, nullable=False)
    pagado = Column(Boolean, default=False, nullable=False)
