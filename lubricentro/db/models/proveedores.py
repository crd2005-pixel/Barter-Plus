# db/models/proveedores.py
import datetime as dt
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from .. import Base

class Proveedor(Base):
    __tablename__ = 'proveedores'
    id = Column(Integer, primary_key=True)
    nombre = Column(String, unique=True)
    cuit = Column(String, unique=True, nullable=True)
    telefono = Column(String)
    email = Column(String)
    direccion = Column(String)
    iva_pct = Column(Float, default=0.0)  # IVA que aplica este proveedor a sus precios de lista

class ProveedorPrecio(Base):
    __tablename__ = 'proveedores_precios'
    id = Column(Integer, primary_key=True)
    proveedor_id = Column(Integer, ForeignKey('proveedores.id'))
    producto_id = Column(Integer, ForeignKey('productos.id'))
    precio = Column(Float, default=0.0)       # precio de lista del proveedor (sin IVA)
    iva_pct = Column(Float, nullable=True)    # opcional: IVA específico de esta línea; si None usa proveedor.iva_pct
    proveedor = relationship('Proveedor')
    # producto = relationship('Producto')  # no es estrictamente necesario aquí
    __table_args__ = (UniqueConstraint('proveedor_id', 'producto_id', name='uix_prov_prod'),)

class FacturaProveedor(Base):
    __tablename__ = 'facturas_proveedores'
    id = Column(Integer, primary_key=True)
    proveedor_id = Column(Integer, ForeignKey('proveedores.id'))
    fecha = Column(DateTime, default=dt.datetime.utcnow)
    total = Column(Float, default=0.0)
    proveedor = relationship('Proveedor')

class Pasivo(Base):
    __tablename__ = 'pasivos'
    id = Column(Integer, primary_key=True)
    concepto = Column(String)
    monto = Column(Float, default=0.0)
    fecha = Column(DateTime, default=dt.datetime.utcnow)
