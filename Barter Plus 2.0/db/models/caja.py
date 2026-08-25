# -*- coding: utf-8 -*-
import datetime as dt
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .. import Base, engine

class CierreCaja(Base):
    __tablename__ = "cierre_caja"
    id = Column(Integer, primary_key=True)

    fecha_desde = Column(DateTime, nullable=False)
    fecha_hasta = Column(DateTime, nullable=False)

    # totales sistema (snapshot)
    total = Column(Float, default=0.0)
    total_efectivo = Column(Float, default=0.0)
    total_transferencia = Column(Float, default=0.0)
    total_debito = Column(Float, default=0.0)
    total_credito = Column(Float, default=0.0)
    total_ctacte = Column(Float, default=0.0)

    # conteos físicos (usuario)
    contado_efectivo = Column(Float, default=0.0)
    contado_transferencia = Column(Float, default=0.0)
    contado_debito = Column(Float, default=0.0)
    contado_credito = Column(Float, default=0.0)
    contado_ctacte = Column(Float, default=0.0)

    # diferencias por medio (contado - sistema)
    dif_efectivo = Column(Float, default=0.0)
    dif_transferencia = Column(Float, default=0.0)
    dif_debito = Column(Float, default=0.0)
    dif_credito = Column(Float, default=0.0)
    dif_ctacte = Column(Float, default=0.0)

    estado = Column(String, default="PREC")         # PREC | FINAL
    motivo_diferencia = Column(String, default="")  # texto libre
    observacion = Column(String, default="")
    creado_en = Column(DateTime, default=dt.datetime.now)

    items = relationship("CierreCajaItem", backref="cierre", cascade="all, delete-orphan")
    pagos = relationship("CierreCajaPago", backref="cierre", cascade="all, delete-orphan")
    ajustes = relationship("CierreCajaAjuste", backref="cierre", cascade="all, delete-orphan")

class CierreCajaItem(Base):
    __tablename__ = "cierre_caja_item"
    id = Column(Integer, primary_key=True)
    cierre_id = Column(Integer, ForeignKey("cierre_caja.id"), nullable=False)
    numero = Column(String)
    fecha_txt = Column(String)
    cliente = Column(String)
    forma = Column(String)
    total = Column(Float, default=0.0)
    estado = Column(String)

class CierreCajaPago(Base):
    __tablename__ = "cierre_caja_pago"
    id = Column(Integer, primary_key=True)
    cierre_id = Column(Integer, ForeignKey("cierre_caja.id"), nullable=False)
    medio = Column(String)   # Efectivo/Transferencia/Débito/Tarjeta/Cuenta Corriente
    monto = Column(Float, default=0.0)

class CierreCajaAjuste(Base):
    __tablename__ = "cierre_caja_ajuste"
    id = Column(Integer, primary_key=True)
    cierre_id = Column(Integer, ForeignKey("cierre_caja.id"), nullable=False)
    monto = Column(Float, default=0.0)
    nota = Column(String, default="")
    creado_en = Column(DateTime, default=dt.datetime.now)

def ensure_caja_columns():
    """Migración simple: agrega columnas nuevas si faltan."""
    conn = engine.raw_connection()
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info('cierre_caja')")
        cols = {row[1] for row in cur.fetchall()}
        def add(name, typ, default="0.0"):
            if name not in cols:
                cur.execute(f"ALTER TABLE cierre_caja ADD COLUMN {name} {typ} DEFAULT {default}")
        # anteriores
        add("contado_efectivo", "REAL")
        add("dif_efectivo", "REAL")
        if "estado" not in cols:
            cur.execute("ALTER TABLE cierre_caja ADD COLUMN estado TEXT DEFAULT 'PREC'")
        if "motivo_diferencia" not in cols:
            cur.execute("ALTER TABLE cierre_caja ADD COLUMN motivo_diferencia TEXT DEFAULT ''")
        # nuevos por medio
        add("contado_transferencia", "REAL")
        add("contado_debito", "REAL")
        add("contado_credito", "REAL")
        add("contado_ctacte", "REAL")
        add("dif_transferencia", "REAL")
        add("dif_debito", "REAL")
        add("dif_credito", "REAL")
        add("dif_ctacte", "REAL")
        conn.commit()
    finally:
        conn.close()
