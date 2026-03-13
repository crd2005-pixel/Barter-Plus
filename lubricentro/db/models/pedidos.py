import datetime as dt
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from .. import Base

class Pedido(Base):
    __tablename__ = 'pedidos'
    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey('clientes.id'))
    fecha = Column(DateTime, default=dt.datetime.utcnow)
    estado = Column(String, default='abierto')

class PedidoItem(Base):
    __tablename__ = 'pedidos_items'
    id = Column(Integer, primary_key=True)
    pedido_id = Column(Integer, ForeignKey('pedidos.id'))
    producto_id = Column(Integer, ForeignKey('productos.id'))
    cantidad = Column(Float, default=1)

class SolicitudProducto(Base):
    __tablename__ = 'solicitudes_productos'
    id = Column(Integer, primary_key=True)
    producto_texto = Column(String, nullable=False)
    cliente_id = Column(Integer, ForeignKey('clientes.id'), nullable=True)
    fecha = Column(DateTime, default=dt.datetime.utcnow)
    estado = Column(String, default='pendiente') # pendiente, ordenado, ignorado
    observacion = Column(String, default='')
