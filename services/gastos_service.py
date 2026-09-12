from database.conexion import get_session
from database.models.contabilidad import GastoOperativo, AsientoDiario
from database.models.caja import Caja, MovimientoCaja
from sqlalchemy import select
from typing import List
import datetime as dt

class GastosService:
    @staticmethod
    def registrar_gasto(categoria: str, descripcion: str, monto: float, origen_fondos: str = "Caja del Día (Mostrador)") -> GastoOperativo:
        """
        Registra un gasto operativo. Inyecta el egreso en la Caja Activa y genera el Asiento Diario.
        No toca la cuenta corriente de proveedores.
        """
        with get_session() as session:
            try:
                if monto <= 0:
                    raise ValueError("El monto del gasto debe ser mayor a cero.")

                # 1. Crear registro base de gasto
                gasto = GastoOperativo(
                    categoria=categoria,
                    descripcion=descripcion,
                    monto=monto,
                    origen_fondos=origen_fondos
                )
                session.add(gasto)
                session.flush()

                # 2. Asentar origen de fondos
                if origen_fondos == "Caja del Día (Mostrador)":
                    caja_activa = session.scalars(select(Caja).where(Caja.estado == "Abierta")).first()
                    if not caja_activa:
                        raise ValueError("No hay una caja abierta para registrar el egreso de dinero en la Caja del Día.")

                    mov_caja = MovimientoCaja(
                        caja_id=caja_activa.id,
                        tipo="Egreso",
                        concepto=f"Gasto OP: {categoria} - {descripcion}",
                        monto=monto,
                        metodo="Efectivo"
                    )
                    session.add(mov_caja)
                else:
                    # Registramos el origen contablemente
                    asiento_origen = AsientoDiario(
                        fecha=dt.datetime.utcnow(),
                        cuenta=origen_fondos,
                        debe=0.0,
                        haber=monto,
                        descripcion=f"Egreso para Gasto OP: {descripcion}"
                    )
                    session.add(asiento_origen)

                # 3. Asentar en Libro Diario
                asiento = AsientoDiario(
                    fecha=dt.datetime.utcnow(),
                    cuenta=f"Gastos Operativos - {categoria}",
                    debe=monto,
                    haber=0.0,
                    descripcion=f"Gasto #{gasto.id}: {descripcion}"
                )
                session.add(asiento)

                session.commit()
                session.refresh(gasto)
                session.expunge(gasto)
                return gasto
            except Exception as e:
                session.rollback()
                raise e

    @staticmethod
    def obtener_gastos_del_mes() -> List[GastoOperativo]:
        """Obtiene los gastos operativos del mes en curso."""
        hoy = dt.date.today()
        primer_dia = dt.datetime(hoy.year, hoy.month, 1)

        with get_session() as session:
            gastos = session.scalars(
                select(GastoOperativo)
                .where(GastoOperativo.fecha >= primer_dia)
                .order_by(GastoOperativo.fecha.desc())
            ).all()
            for g in gastos:
                session.expunge(g)
            return list(gastos)
