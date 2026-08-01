from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import datetime as dt
import os

# Ruta del nuevo archivo de base de datos
DB_PATH = os.path.join(os.getcwd(), "db_new.sqlite3")

Base = declarative_base()

# ------------------------------
# Modelos
# ------------------------------
class Cliente(Base):
    __tablename__ = 'clientes'
    id = Column(Integer, primary_key=True)
    nombre = Column(String, nullable=False)
    telefono = Column(String, default='')
    direccion = Column(String, default='')
    email = Column(String, default='')

    ventas = relationship("Venta", back_populates="cliente")


class Venta(Base):
    __tablename__ = 'ventas'
    id = Column(Integer, primary_key=True)
    numero = Column(Integer, index=True)
    cliente_id = Column(Integer, ForeignKey('clientes.id'), nullable=True)
    descuento = Column(Float, default=0.0)
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
    estado = Column(String, default='emitido')
    observaciones = Column(Text, default='')

    nro_comprobante = Column(String, unique=True, index=True)
    anulada = Column(Boolean, default=False)
    fecha_anulacion = Column(DateTime)
    motivo_anulacion = Column(String)

    cliente = relationship("Cliente", back_populates="ventas")


# ------------------------------
# Crear nueva base
# ------------------------------
def create_new_db():
    engine = create_engine(f"sqlite:///{DB_PATH}")
    Base.metadata.create_all(engine)
    print(f"Base creada correctamente en: {DB_PATH}")


if __name__ == "__main__":
    create_new_db()
