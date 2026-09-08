from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
import datetime as dt
from database.conexion import Base
from typing import List, Optional

class Categoria(Base):
    __tablename__ = 'categorias'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    productos: Mapped[List['Producto']] = relationship(back_populates='categoria')

class Marca(Base):
    __tablename__ = 'marcas'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    productos: Mapped[List['Producto']] = relationship(back_populates='marca')

class Producto(Base):
    __tablename__ = 'productos'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sku: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True) # SKU interno
    codigo_barras: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True, nullable=True)
    nombre: Mapped[str] = mapped_column(String, index=True, nullable=False)

    rubro: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True) # Clasificación principal
    subrubro: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    categoria_id: Mapped[Optional[int]] = mapped_column(ForeignKey('categorias.id'), nullable=True)
    marca_id: Mapped[Optional[int]] = mapped_column(ForeignKey('marcas.id'), nullable=True)

    # Vinculación externa opcional
    proveedor_id: Mapped[Optional[int]] = mapped_column(ForeignKey('proveedores.id'), nullable=True)
    codigo_proveedor: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    codigo_equivalencia: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)

    # Precios y Costos
    costo: Mapped[float] = mapped_column(default=0.0)
    precio_mayorista: Mapped[float] = mapped_column(default=0.0)
    precio_minorista: Mapped[float] = mapped_column(default=0.0)
    precio_manual: Mapped[float] = mapped_column(default=0.0)
    iva: Mapped[float] = mapped_column(default=21.0)

    # Inventario
    stock_actual: Mapped[float] = mapped_column(default=0.0)
    stock_minimo: Mapped[float] = mapped_column(default=0.0)
    stock_maximo: Mapped[float] = mapped_column(default=0.0)

    # Fraccionamiento y Granel
    es_granel: Mapped[bool] = mapped_column(default=False)
    divisor_granel: Mapped[float] = mapped_column(default=1.0)

    # Detalles para presentación (Legacy/Auxiliar)
    venta_granel: Mapped[bool] = mapped_column(default=False)
    presentacion_cantidad: Mapped[float] = mapped_column(default=1.0)
    presentacion_unidad: Mapped[str] = mapped_column(String, default="Unidad")

    activo: Mapped[bool] = mapped_column(default=True)
    creado_en: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)
    actualizado_en: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

    # Relaciones
    categoria: Mapped[Optional['Categoria']] = relationship(back_populates='productos')
    marca: Mapped[Optional['Marca']] = relationship(back_populates='productos')
    proveedor: Mapped[Optional['Proveedor']] = relationship(back_populates='productos')
