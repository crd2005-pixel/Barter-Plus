from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
import datetime as dt
from database.conexion import Base
from typing import Optional

class AsientoDiario(Base):
    __tablename__ = 'asientos_diarios'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fecha: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow, index=True)
    descripcion: Mapped[str] = mapped_column(String, nullable=False)
    debe: Mapped[float] = mapped_column(default=0.0)
    haber: Mapped[float] = mapped_column(default=0.0)
    cuenta: Mapped[str] = mapped_column(String, nullable=False) # ej: "Caja", "Ventas", "Costo Mercadería"

    venta_id: Mapped[Optional[int]] = mapped_column(ForeignKey('ventas.id'), nullable=True)

class LibroIVA(Base):
    __tablename__ = 'libro_iva'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fecha: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow, index=True)
    tipo: Mapped[str] = mapped_column(String, nullable=False) # "Venta" (Débito) o "Compra" (Crédito)
    comprobante: Mapped[str] = mapped_column(String, nullable=False) # "Factura A 0001-00000001"

    neto_gravado: Mapped[float] = mapped_column(default=0.0)
    iva_21: Mapped[float] = mapped_column(default=0.0)
    iva_105: Mapped[float] = mapped_column(default=0.0)
    total: Mapped[float] = mapped_column(default=0.0)

    venta_id: Mapped[Optional[int]] = mapped_column(ForeignKey('ventas.id'), nullable=True)

class PedidoManual(Base):
    __tablename__ = 'pedidos_manuales'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fecha: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)
    detalle: Mapped[str] = mapped_column(String, nullable=False)
    estado: Mapped[str] = mapped_column(String, default="Pendiente")


class GastoOperativo(Base):
    __tablename__ = 'gastos_operativos'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fecha: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow, index=True)
    categoria: Mapped[str] = mapped_column(String, nullable=False)
    descripcion: Mapped[str] = mapped_column(String, nullable=False)
    monto: Mapped[float] = mapped_column(default=0.0)
    origen_fondos: Mapped[Optional[str]] = mapped_column(String, nullable=True, default='Caja del Día (Mostrador)')


class IngresoDiferido(Base):
    __tablename__ = 'ingresos_diferidos'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    venta_id: Mapped[Optional[int]] = mapped_column(ForeignKey('ventas.id'), nullable=True)
    fecha_venta: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)
    fecha_acreditacion: Mapped[dt.date] = mapped_column(nullable=False)

    banco_tarjeta: Mapped[str] = mapped_column(String, nullable=False)
    cuotas: Mapped[int] = mapped_column(Integer, default=1)
    monto_original: Mapped[float] = mapped_column(default=0.0)
    interes_aplicado: Mapped[float] = mapped_column(default=0.0)
    monto_acreditar: Mapped[float] = mapped_column(default=0.0)

    cuenta_destino: Mapped[str] = mapped_column(String, nullable=False)
    estado: Mapped[str] = mapped_column(String, default="Pendiente") # Pendiente, Acreditado
