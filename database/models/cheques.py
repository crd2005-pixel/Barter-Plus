from sqlalchemy import ForeignKey, String, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
import datetime as dt
from database.conexion import Base
from typing import Optional

class Cheque(Base):
    __tablename__ = 'cheques'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    venta_id: Mapped[int] = mapped_column(ForeignKey('ventas.id'), nullable=False)
    banco: Mapped[str] = mapped_column(String, nullable=False)
    numero_cheque: Mapped[str] = mapped_column(String, nullable=False)
    fecha_conformacion: Mapped[dt.date] = mapped_column(Date, nullable=False)
    fecha_vencimiento: Mapped[dt.date] = mapped_column(Date, nullable=False)
    tipo_cheque: Mapped[str] = mapped_column(String, nullable=False)
    nombre_emisor: Mapped[str] = mapped_column(String, nullable=False)
    cuit: Mapped[str] = mapped_column(String, nullable=False)
    endoso: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    monto: Mapped[float] = mapped_column(nullable=False)
    estado: Mapped[str] = mapped_column(String, default="Pendiente")

    # Relaciones
    venta: Mapped['Venta'] = relationship()
