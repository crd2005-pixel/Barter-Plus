from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
import datetime as dt
from database.conexion import Base
from typing import List, Optional

class Venta(Base):
    __tablename__ = 'ventas'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fecha: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow, index=True)
    cliente_id: Mapped[Optional[int]] = mapped_column(ForeignKey('clientes.id'), nullable=True)

    # Totales
    subtotal: Mapped[float] = mapped_column(default=0.0)
    descuento: Mapped[float] = mapped_column(default=0.0)
    recargo: Mapped[float] = mapped_column(default=0.0)
    total: Mapped[float] = mapped_column(default=0.0)

    # Detalles de Pago
    metodo_pago: Mapped[str] = mapped_column(String, default="Efectivo") # Efectivo, Tarjeta, Mixto, CtaCte
    pago_efectivo: Mapped[float] = mapped_column(default=0.0)
    pago_tarjeta: Mapped[float] = mapped_column(default=0.0)
    pago_transferencia: Mapped[float] = mapped_column(default=0.0)
    pago_ctacte: Mapped[float] = mapped_column(default=0.0)

    vuelto: Mapped[float] = mapped_column(default=0.0)
    estado: Mapped[str] = mapped_column(String, default="Completada") # Completada, Anulada, Presupuesto
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relaciones
    cliente: Mapped[Optional['Cliente']] = relationship(back_populates='ventas')
    detalles: Mapped[List['DetalleVenta']] = relationship(back_populates='venta', cascade="all, delete-orphan")
    movimientos_cc: Mapped[List['ClienteCuentaCorriente']] = relationship(back_populates='venta')

class DetalleVenta(Base):
    __tablename__ = 'detalle_ventas'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    venta_id: Mapped[int] = mapped_column(ForeignKey('ventas.id'), nullable=False)
    producto_id: Mapped[Optional[int]] = mapped_column(ForeignKey('productos.id'), nullable=True)

    # Datos guardados en el momento de la venta (para inmutabilidad histórica)
    codigo_barras: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    descripcion: Mapped[str] = mapped_column(String, nullable=False)

    cantidad: Mapped[float] = mapped_column(default=1.0)
    precio_unitario: Mapped[float] = mapped_column(default=0.0)
    subtotal: Mapped[float] = mapped_column(default=0.0)

    # Relaciones
    venta: Mapped['Venta'] = relationship(back_populates='detalles')
    # No cascada a producto para que si se borra producto quede el historial
    producto: Mapped[Optional['Producto']] = relationship()
