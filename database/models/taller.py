from sqlalchemy import ForeignKey, String, Integer, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
import datetime as dt
from database.conexion import Base
from typing import List, Optional
from database.models.cliente import Cliente

class Vehiculo(Base):
    __tablename__ = 'vehiculos'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey('clientes.id'), nullable=False)
    dominio: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    marca: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    modelo: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    anio: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relaciones
    cliente: Mapped['Cliente'] = relationship()
    garantias: Mapped[List['GarantiaBateria']] = relationship(back_populates='vehiculo')
    cambios_aceite: Mapped[List['CambioAceite']] = relationship(back_populates='vehiculo')


class GarantiaBateria(Base):
    __tablename__ = 'garantias_baterias'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vehiculo_id: Mapped[int] = mapped_column(ForeignKey('vehiculos.id'), nullable=False)
    producto_id: Mapped[int] = mapped_column(ForeignKey('productos.id'), nullable=False)
    fecha_instalacion: Mapped[dt.date] = mapped_column(Date, default=dt.date.today)
    meses_garantia: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_vencimiento: Mapped[dt.date] = mapped_column(Date, nullable=False)
    codigo_garantia: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    # Relaciones
    vehiculo: Mapped['Vehiculo'] = relationship(back_populates='garantias')
    producto: Mapped['Producto'] = relationship()


class CambioAceite(Base):
    __tablename__ = 'cambios_aceite'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vehiculo_id: Mapped[int] = mapped_column(ForeignKey('vehiculos.id'), nullable=False)
    fecha: Mapped[dt.date] = mapped_column(Date, default=dt.date.today)
    km_actual: Mapped[int] = mapped_column(Integer, nullable=False)
    proximo_km: Mapped[int] = mapped_column(Integer, nullable=False)

    aceite_utilizado: Mapped[str] = mapped_column(String, nullable=False)
    filtro_aceite: Mapped[bool] = mapped_column(default=False)
    filtro_aire: Mapped[bool] = mapped_column(default=False)
    filtro_combustible: Mapped[bool] = mapped_column(default=False)
    filtro_habitaculo: Mapped[bool] = mapped_column(default=False)
    observaciones: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relaciones
    vehiculo: Mapped['Vehiculo'] = relationship(back_populates='cambios_aceite')
