from database.conexion import get_session
from database.models.caja import Caja, MovimientoCaja
from sqlalchemy import select
from typing import Optional, List
import datetime as dt

class CajaService:

    @staticmethod
    def obtener_caja_activa() -> Optional[Caja]:
        with get_session() as session:
            caja = session.scalars(select(Caja).where(Caja.estado == "Abierta")).first()
            if caja:
                session.expunge(caja)
            return caja

    @staticmethod
    def abrir_caja(saldo_inicial: float) -> Caja:
        with get_session() as session:
            activa = session.scalars(select(Caja).where(Caja.estado == "Abierta")).first()
            if activa:
                raise ValueError("Ya existe una caja abierta. Debe cerrarla primero.")

            nueva_caja = Caja(
                saldo_inicial=saldo_inicial,
                estado="Abierta"
            )
            session.add(nueva_caja)
            session.flush()

            # Movimiento de apertura
            mov_apertura = MovimientoCaja(
                caja_id=nueva_caja.id,
                tipo="Ingreso",
                concepto="Apertura de Caja",
                monto=saldo_inicial,
                metodo="Efectivo"
            )
            session.add(mov_apertura)
            session.commit()

            session.refresh(nueva_caja)
            session.expunge(nueva_caja)
            return nueva_caja

    @staticmethod
    def registrar_movimiento(caja_id: int, tipo: str, concepto: str, monto: float, metodo: str, venta_id: Optional[int] = None) -> MovimientoCaja:
        with get_session() as session:
            try:
                mov = MovimientoCaja(
                    caja_id=caja_id,
                    tipo=tipo,
                    concepto=concepto,
                    monto=monto,
                    metodo=metodo,
                    venta_id=venta_id
                )
                session.add(mov)
                session.commit()
                session.refresh(mov)
                session.expunge(mov)
                return mov
            except Exception as e:
                session.rollback()
                raise e

    @staticmethod
    def obtener_movimientos(caja_id: int) -> List[MovimientoCaja]:
        with get_session() as session:
            movimientos = session.scalars(
                select(MovimientoCaja)
                .where(MovimientoCaja.caja_id == caja_id)
                .order_by(MovimientoCaja.fecha.asc())
            ).all()
            for m in movimientos:
                session.expunge(m)
            return list(movimientos)

    @staticmethod
    def calcular_saldo_efectivo(caja_id: int) -> float:
        with get_session() as session:
            movs = session.scalars(
                select(MovimientoCaja)
                .where(MovimientoCaja.caja_id == caja_id, MovimientoCaja.metodo == "Efectivo")
            ).all()

            saldo = 0.0
            for m in movs:
                if m.tipo == "Ingreso":
                    saldo += m.monto
                else:
                    saldo -= m.monto
            return saldo

    @staticmethod
    def cerrar_caja(caja_id: int, saldo_real: float) -> Caja:
        with get_session() as session:
            try:
                caja = session.get(Caja, caja_id)
                if not caja or caja.estado == "Cerrada":
                    raise ValueError("La caja no existe o ya está cerrada.")

                # Calcular el saldo esperado solo en efectivo (los otros métodos no están en la caja física)
                movs = session.scalars(
                    select(MovimientoCaja)
                    .where(MovimientoCaja.caja_id == caja_id, MovimientoCaja.metodo == "Efectivo")
                ).all()

                saldo_esperado = 0.0
                for m in movs:
                    if m.tipo == "Ingreso":
                        saldo_esperado += m.monto
                    else:
                        saldo_esperado -= m.monto

                diferencia = saldo_real - saldo_esperado

                if diferencia < 0:
                    mov_faltante = MovimientoCaja(
                        caja_id=caja.id,
                        tipo="Egreso",
                        concepto="Faltante de Caja (Ajuste)",
                        monto=abs(diferencia),
                        metodo="Efectivo"
                    )
                    session.add(mov_faltante)
                elif diferencia > 0:
                    mov_sobrante = MovimientoCaja(
                        caja_id=caja.id,
                        tipo="Ingreso",
                        concepto="Sobrante de Caja (Ajuste)",
                        monto=abs(diferencia),
                        metodo="Efectivo"
                    )
                    session.add(mov_sobrante)

                caja.saldo_final_esperado = saldo_esperado
                caja.saldo_final_real = saldo_real
                caja.diferencia = diferencia
                caja.estado = "Cerrada"
                caja.fecha_cierre = dt.datetime.utcnow()

                session.commit()
                session.refresh(caja)
                session.expunge(caja)
                return caja
            except Exception as e:
                session.rollback()
                raise e

    @staticmethod
    def obtener_historial_cajas() -> List[Caja]:
        with get_session() as session:
            cajas = session.scalars(select(Caja).order_by(Caja.fecha_apertura.desc())).all()
            for c in cajas:
                session.expunge(c)
            return list(cajas)
