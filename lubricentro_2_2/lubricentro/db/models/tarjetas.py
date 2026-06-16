from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from .. import Base

class TarjetaCoef(Base):
    __tablename__ = "tarjeta_coef"
    id = Column(Integer, primary_key=True)
    marca = Column(String, index=True)       # "Naranja", "Visa", etc.
    cuotas = Column(Integer, index=True)     # 1,3,6,12...
    recargo_pct = Column(Float, default=0.0) # 30.0 = +30%

    def __repr__(self):
        return f"<TarjetaCoef {self.marca} {self.cuotas}x {self.recargo_pct}%>"

class VentaPago(Base):
    __tablename__ = "ventas_pagos"
    id = Column(Integer, primary_key=True)
    venta_id = Column(Integer, ForeignKey("ventas.id"), index=True)
    medio = Column(String)          # "Efectivo","Transferencia","Débito","Tarjeta","Cheque"
    monto = Column(Float, default=0)
    detalle = Column(String, default="")   # lote/tx cheque, etc.
