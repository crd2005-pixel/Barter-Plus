from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
import datetime as dt
from database.conexion import Base
from typing import List, Optional

class Presupuesto(Base):
    __tablename__ = 'presupuestos'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fecha: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow, index=True)
    cliente_id: Mapped[Optional[int]] = mapped_column(ForeignKey('clientes.id'), nullable=True)

    # Totales (Idéntica estructura a Venta para análisis)
    subtotal: Mapped[float] = mapped_column(default=0.0)
    descuento: Mapped[float] = mapped_column(default=0.0)
    recargo: Mapped[float] = mapped_column(default=0.0)
    total: Mapped[float] = mapped_column(default=0.0)

    estado: Mapped[str] = mapped_column(String, default="Pendiente") # Pendiente, Aprobado, Vencido
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relaciones
    cliente: Mapped[Optional['Cliente']] = relationship()
    detalles: Mapped[List['DetallePresupuesto']] = relationship(back_populates='presupuesto', cascade="all, delete-orphan")

class DetallePresupuesto(Base):
    __tablename__ = 'detalle_presupuestos'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    presupuesto_id: Mapped[int] = mapped_column(ForeignKey('presupuestos.id'), nullable=False)
    producto_id: Mapped[Optional[int]] = mapped_column(ForeignKey('productos.id'), nullable=True)

    codigo_barras: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    descripcion: Mapped[str] = mapped_column(String, nullable=False)

    cantidad: Mapped[float] = mapped_column(default=1.0)
    precio_unitario: Mapped[float] = mapped_column(default=0.0)
    descuento_unitario: Mapped[float] = mapped_column(default=0.0)
    subtotal: Mapped[float] = mapped_column(default=0.0)

    # Relaciones
    presupuesto: Mapped['Presupuesto'] = relationship(back_populates='detalles')
    producto: Mapped[Optional['Producto']] = relationship()
