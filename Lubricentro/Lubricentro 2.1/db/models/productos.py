# db/models/productos.py
import datetime as dt
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Date
from sqlalchemy.orm import relationship
from .. import Base

class Categoria(Base):
    __tablename__ = 'categorias'
    id = Column(Integer, primary_key=True)
    nombre = Column(String, unique=True)
    productos = relationship('Producto')

class Marca(Base):
    __tablename__ = 'marcas'
    id = Column(Integer, primary_key=True)
    nombre = Column(String, unique=True)
    productos = relationship('Producto')

class Producto(Base):
    __tablename__ = 'productos'
    id = Column(Integer, primary_key=True)
    sku = Column(String, unique=True, nullable=True)
    codigo_barras = Column(String, unique=True, index=True)
    nombre = Column(String, index=True)
    rubro = Column(String, index=True)  # Baterias | Lubricantes | Filtros | Otro
    categoria_id = Column(Integer, ForeignKey('categorias.id'), nullable=True)
    marca_id = Column(Integer, ForeignKey('marcas.id'), nullable=True)
    proveedor_id = Column(Integer, ForeignKey('proveedores.id'), nullable=True) # NUEVO: Relación directa
    codigo_proveedor = Column(String, index=True, nullable=True) # Código del producto en la lista del proveedor
    precio_minorista = Column(Float, default=0)
    precio_mayorista = Column(Float, default=0)
    stock_minimo = Column(Float, default=0)
    stock_maximo = Column(Float, default=0) # NUEVO
    precio_manual = Column(Float, default=0) # NUEVO: Precio manual fijo (override)

    # Soporte para granel
    venta_granel = Column(Integer, default=0) # 0=Unidad, 1=Granel
    presentacion_cantidad = Column(Float, default=1.0) # Ej 200 para tambor de 200L
    presentacion_unidad = Column(String, default="Unidad") # L, kg, etc.
    subrubro = Column(String, nullable=True)

    costo = Column(Float, default=0)  # costo manual
    iva = Column(Float, default=21.0) # IVA propio si se define, si no se usa el del rubro
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime, default=dt.datetime.utcnow)
    actualizado_en = Column(DateTime, default=dt.datetime.utcnow)

class Deposito(Base):
    __tablename__ = 'depositos'
    id = Column(Integer, primary_key=True)
    nombre = Column(String, unique=True)

class Stock(Base):
    __tablename__ = 'stocks'
    id = Column(Integer, primary_key=True)
    producto_id = Column(Integer, ForeignKey('productos.id'))
    deposito_id = Column(Integer, ForeignKey('depositos.id'))
    cantidad = Column(Float, default=0)

class PromocionProducto(Base):
    __tablename__ = 'promociones_productos'
    id = Column(Integer, primary_key=True)
    producto_id = Column(Integer, ForeignKey('productos.id'))
    tipo = Column(String, default='porcentaje')  # 'porcentaje' | 'fijo'
    valor = Column(Float, default=0.0)          # % si porcentaje, precio final si fijo
    fecha_inicio = Column(Date, nullable=False)
    fecha_fin = Column(Date, nullable=False)
    activo = Column(Boolean, default=True)
