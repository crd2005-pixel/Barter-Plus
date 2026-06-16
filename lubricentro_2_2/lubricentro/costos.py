# db/models/costos.py
import datetime as _dt
from sqlalchemy import Column, Integer, String, Float, Date, Boolean, ForeignKey, UniqueConstraint
from .. import Base

class Impuesto(Base):
    __tablename__ = 'impuestos'
    id = Column(Integer, primary_key=True)
    nombre = Column(String, unique=True, index=True)
    periodicidad = Column(String, default='MENSUAL')  # MENSUAL|BIMESTRAL|TRIMESTRAL|ANUAL
    activo = Column(Boolean, default=True)

class ImpuestoPeriodo(Base):
    __tablename__ = 'impuestos_periodos'
    id = Column(Integer, primary_key=True)
    impuesto_id = Column(Integer, ForeignKey('impuestos.id'))
    periodo_label = Column(String, index=True)         # 2025-11, 2025-B06, 2025-T04, 2025
    fecha_inicio = Column(Date)
    fecha_fin = Column(Date)
    monto = Column(Float, default=0.0)
    pagado = Column(Boolean, default=False)
    fecha_pago = Column(Date, nullable=True)
    periodicidad = Column(String, default='MENSUAL')
    __table_args__ = (UniqueConstraint('impuesto_id', 'periodo_label', name='uix_impuesto_periodo'),)

class GastoNegocio(Base):
    __tablename__ = 'gastos_negocio'
    id = Column(Integer, primary_key=True)
    fecha = Column(Date, default=lambda: _dt.datetime.utcnow().date(), nullable=False)
    categoria = Column(String, index=True)
    descripcion = Column(String, default='')
    monto = Column(Float, default=0.0, nullable=False)
    pagado = Column(Boolean, default=False, nullable=False)  # NUEVO
    credito_id = Column(Integer, ForeignKey("creditos_negocio.id"), nullable=True)  # NUEVO

class Empleado(Base):
    __tablename__ = 'empleados'
    id = Column(Integer, primary_key=True)
    nombre = Column(String, index=True)
    cuil = Column(String, nullable=True)
    activo = Column(Boolean, default=True)

class SueldoLiquidacion(Base):
    __tablename__ = 'sueldos_liquidaciones'
    id = Column(Integer, primary_key=True)
    empleado_id = Column(Integer, ForeignKey('empleados.id'))
    periodo_label = Column(String, index=True)  # YYYY-MM
    fecha_pago = Column(Date, nullable=True)    # None = no pagado
    bruto = Column(Float, default=0.0)
    descuentos = Column(Float, default=0.0)
    neto = Column(Float, default=0.0)
    __table_args__ = (UniqueConstraint('empleado_id', 'periodo_label', name='uix_empleado_periodo'),)
