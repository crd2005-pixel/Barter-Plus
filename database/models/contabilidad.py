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
