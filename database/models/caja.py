from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
import datetime as dt
from database.conexion import Base
from typing import List, Optional

class Caja(Base):
    __tablename__ = 'cajas'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fecha_apertura: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow, nullable=False)
    fecha_cierre: Mapped[Optional[dt.datetime]] = mapped_column(nullable=True)
    saldo_inicial: Mapped[float] = mapped_column(default=0.0)
    saldo_final_esperado: Mapped[float] = mapped_column(default=0.0)
    saldo_final_real: Mapped[float] = mapped_column(default=0.0)
    diferencia: Mapped[float] = mapped_column(default=0.0)
    estado: Mapped[str] = mapped_column(String, default="Abierta") # Abierta, Cerrada
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relaciones
    movimientos: Mapped[List['MovimientoCaja']] = relationship(back_populates='caja')

class MovimientoCaja(Base):
    __tablename__ = 'movimientos_caja'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    caja_id: Mapped[int] = mapped_column(ForeignKey('cajas.id'), nullable=False)
    fecha: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)
    tipo: Mapped[str] = mapped_column(String, nullable=False) # 'Ingreso' o 'Egreso'
    concepto: Mapped[str] = mapped_column(String, nullable=False)
    monto: Mapped[float] = mapped_column(nullable=False)
    metodo: Mapped[str] = mapped_column(String, default="Efectivo") # Efectivo, Tarjeta, Transferencia

    # Referencia opcional a una venta
    venta_id: Mapped[Optional[int]] = mapped_column(ForeignKey('ventas.id'), nullable=True)

    # Relaciones
    caja: Mapped['Caja'] = relationship(back_populates='movimientos')
    venta: Mapped[Optional['Venta']] = relationship()
