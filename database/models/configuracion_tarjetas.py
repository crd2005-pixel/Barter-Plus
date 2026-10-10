from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.orm import Mapped, mapped_column
from database.conexion import Base

class ConfiguracionTarjeta(Base):
    __tablename__ = 'configuracion_tarjetas'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    banco_tarjeta: Mapped[str] = mapped_column(String, nullable=False)
    cuotas: Mapped[int] = mapped_column(Integer, default=1)
    porcentaje_interes: Mapped[float] = mapped_column(default=0.0)
    dias_acreditacion: Mapped[int] = mapped_column(Integer, default=0)
