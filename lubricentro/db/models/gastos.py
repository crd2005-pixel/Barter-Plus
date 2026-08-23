# -*- coding: utf-8 -*-
# db/models/gastos.py
import datetime as dt
from sqlalchemy import Column, Integer, Float, String, DateTime, Index
from .. import Base

class Gasto(Base):
    __tablename__ = "gastos"

    id = Column(Integer, primary_key=True)
    fecha = Column(DateTime, default=dt.datetime.utcnow, nullable=False)
    medio = Column(String(40), default="efectivo", nullable=False)
    concepto = Column(String(120), default="", nullable=False)
    observacion = Column(String(400), default="", nullable=False)
    tipo = Column(String(40), default="gasto", nullable=False)  # "fiscal" | "negocio" | "proveedor" | "otro"
    monto = Column(Float, default=0.0, nullable=False)
    creado_en = Column(DateTime, default=dt.datetime.utcnow, nullable=False)

Index("ix_gastos_fecha", Gasto.fecha)
Index("ix_gastos_medio", Gasto.medio)
Index("ix_gastos_tipo", Gasto.tipo)
