from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
import datetime as dt
from database.conexion import Base
from typing import List, Optional

class Proveedor(Base):
    __tablename__ = 'proveedores'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    cuit: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    telefono: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    direccion: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    iva_pct: Mapped[float] = mapped_column(default=0.0) # IVA por defecto para listas de este proveedor

    # Relaciones
    productos: Mapped[List['Producto']] = relationship(back_populates='proveedor')
    cuenta_corriente: Mapped[List['ProveedorCuentaCorriente']] = relationship(back_populates='proveedor')

class ProveedorCuentaCorriente(Base):
    __tablename__ = 'proveedor_cuenta_corriente'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    proveedor_id: Mapped[int] = mapped_column(ForeignKey('proveedores.id'), nullable=False)
    fecha: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)
    concepto: Mapped[str] = mapped_column(String, nullable=False)
    debe: Mapped[float] = mapped_column(default=0.0)
    haber: Mapped[float] = mapped_column(default=0.0)
    saldo: Mapped[float] = mapped_column(default=0.0) # Saldo arrastrado
    fecha_vencimiento: Mapped[Optional[dt.datetime]] = mapped_column(nullable=True)

    # Relación
    proveedor: Mapped['Proveedor'] = relationship(back_populates='cuenta_corriente')
