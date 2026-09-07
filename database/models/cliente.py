from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
import datetime as dt
from database.conexion import Base
from typing import List, Optional

class Cliente(Base):
    __tablename__ = 'clientes'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False, index=True)
    dni: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    telefono: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    direccion: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    limite_credito: Mapped[float] = mapped_column(default=0.0) # Límite para cuenta corriente

    # Relaciones
    ventas: Mapped[List['Venta']] = relationship(back_populates='cliente')
    cuenta_corriente: Mapped[List['ClienteCuentaCorriente']] = relationship(back_populates='cliente')

class ClienteCuentaCorriente(Base):
    __tablename__ = 'cliente_cuenta_corriente'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey('clientes.id'), nullable=False)
    fecha: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)
    concepto: Mapped[str] = mapped_column(String, nullable=False)
    debe: Mapped[float] = mapped_column(default=0.0) # Lo que nos deben
    haber: Mapped[float] = mapped_column(default=0.0) # Lo que pagan
    saldo: Mapped[float] = mapped_column(default=0.0) # Saldo arrastrado

    # Referencia cruzada opcional a una venta
    venta_id: Mapped[Optional[int]] = mapped_column(ForeignKey('ventas.id'), nullable=True)

    # Relación
    cliente: Mapped['Cliente'] = relationship(back_populates='cuenta_corriente')
    venta: Mapped[Optional['Venta']] = relationship(back_populates='movimientos_cc')
