import datetime as dt
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from .. import Base

class Venta(Base):
    __tablename__ = 'ventas'
    id = Column(Integer, primary_key=True)
    numero = Column(Integer, index=True)
    cliente_id = Column(Integer, ForeignKey('clientes.id'), nullable=True)
    fecha = Column(DateTime, default=dt.datetime.utcnow)
    rubro = Column(String, index=True)
    forma_pago = Column(String, default='Efectivo')

    tarjeta_nombre = Column(String, default='')
    tarjeta_cuotas = Column(Integer, default=1)
    tarjeta_interes_pct = Column(Float, default=0.0)
    tarjeta_total_con_interes = Column(Float, default=0.0)
    tarjeta_valor_cuota = Column(Float, default=0.0)
    efectivo_entrega = Column(Float, default=0.0)

    total_neto = Column(Float, default=0)
    total_iva = Column(Float, default=0)
    total = Column(Float, default=0)

    descuento = Column(Float, default=0.0)
    motivo_descuento = Column(String, default='')

    estado = Column(String, default='emitido')
    observaciones = Column(Text, default='')

    cliente = relationship("Cliente")
    items = relationship('VentaItem', back_populates='venta', cascade='all, delete-orphan')

class VentaItem(Base):
    __tablename__ = 'ventas_items'
    id = Column(Integer, primary_key=True)
    venta_id = Column(Integer, ForeignKey('ventas.id'))
    producto_id = Column(Integer, ForeignKey('productos.id'))
    cantidad = Column(Float, default=1)
    precio_unitario = Column(Float, default=0)
    subtotal = Column(Float, default=0)
    iva = Column(Float, default=21.0)
    venta = relationship('Venta', back_populates='items')
    producto = relationship('Producto')

class CajaMovimiento(Base):
    __tablename__ = 'caja_movimientos'
    id = Column(Integer, primary_key=True)
    fecha = Column(DateTime, default=dt.datetime.utcnow)
    concepto = Column(String)
    rubro = Column(String, default='General')
    ingreso = Column(Float, default=0)
    egreso = Column(Float, default=0)
    venta_id = Column(Integer, ForeignKey('ventas.id'), nullable=True)
    cliente_id = Column(Integer, ForeignKey('clientes.id'), nullable=True)

class BancoMovimiento(Base):
    __tablename__ = 'banco_movimientos'
    id = Column(Integer, primary_key=True)
    fecha = Column(DateTime, default=dt.datetime.utcnow)
    banco = Column(String)
    concepto = Column(String)
    ingreso = Column(Float, default=0)
    egreso = Column(Float, default=0)

class Asiento(Base):
    __tablename__ = 'asientos'
    id = Column(Integer, primary_key=True)
    fecha = Column(DateTime, default=dt.datetime.utcnow)
    debe = Column(Float, default=0)
    haber = Column(Float, default=0)
    cuenta = Column(String)
    detalle = Column(String)
