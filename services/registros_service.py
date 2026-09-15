from database.conexion import get_session
from database.models.venta import Venta
from database.models.cliente import ClienteCuentaCorriente, Cliente
from database.models.contabilidad import AsientoDiario, LibroIVA
from sqlalchemy import select, and_
from typing import List, Optional
import datetime as dt

class RegistrosService:

    @staticmethod
    def obtener_ventas(fecha_desde: dt.date, fecha_hasta: dt.date, comprobante: str = "Todos") -> List[Venta]:
        from sqlalchemy.orm import joinedload
        with get_session() as session:
            # Add time boundary to until end of the day for fecha_hasta
            dt_desde = dt.datetime.combine(fecha_desde, dt.time.min)
            dt_hasta = dt.datetime.combine(fecha_hasta, dt.time.max)

            stmt = select(Venta).options(joinedload(Venta.cliente)).where(
                and_(Venta.fecha >= dt_desde, Venta.fecha <= dt_hasta)
            ).order_by(Venta.fecha.desc())

            if comprobante != "Todos":
                stmt = stmt.where(Venta.tipo_comprobante == comprobante)

            ventas = session.scalars(stmt).all()
            for v in ventas:
                session.expunge(v)
            return list(ventas)

    @staticmethod
    def obtener_estado_cc(cliente_id: int) -> List[ClienteCuentaCorriente]:
        with get_session() as session:
            movimientos = session.scalars(
                select(ClienteCuentaCorriente)
                .where(ClienteCuentaCorriente.cliente_id == cliente_id)
                .order_by(ClienteCuentaCorriente.fecha.asc())
            ).all()
            for m in movimientos:
                session.expunge(m)
            return list(movimientos)

    @staticmethod
    def obtener_asientos_diarios(fecha_desde: dt.date, fecha_hasta: dt.date) -> List[AsientoDiario]:
        with get_session() as session:
            dt_desde = dt.datetime.combine(fecha_desde, dt.time.min)
            dt_hasta = dt.datetime.combine(fecha_hasta, dt.time.max)

            asientos = session.scalars(
                select(AsientoDiario)
                .where(and_(AsientoDiario.fecha >= dt_desde, AsientoDiario.fecha <= dt_hasta))
                .order_by(AsientoDiario.fecha.asc())
            ).all()
            for a in asientos:
                session.expunge(a)
            return list(asientos)

    @staticmethod
    def obtener_libro_iva(fecha_desde: dt.date, fecha_hasta: dt.date) -> List[LibroIVA]:
        with get_session() as session:
            dt_desde = dt.datetime.combine(fecha_desde, dt.time.min)
            dt_hasta = dt.datetime.combine(fecha_hasta, dt.time.max)

            registros = session.scalars(
                select(LibroIVA)
                .where(and_(LibroIVA.fecha >= dt_desde, LibroIVA.fecha <= dt_hasta))
                .order_by(LibroIVA.fecha.asc())
            ).all()
            for r in registros:
                session.expunge(r)
            return list(registros)


    @staticmethod
    def obtener_liquidez_actual() -> dict:
        from database.models.caja import Caja
        from database.models.contabilidad import IngresoDiferido
        with get_session() as session:
            # 1. Caja Física
            caja = session.scalars(select(Caja).where(Caja.estado == "Abierta")).first()
            if caja:
                # We need CajaService here to accurately compute effective balance but we'll approximate if we must.
                # Actually, I'll import it inside:
                from services.caja_service import CajaService
                efectivo_fuerte = CajaService.calcular_saldo_efectivo(caja.id)
            else:
                efectivo_fuerte = 0.0

            # 2. Valores a Cobrar (Tarjetas Pendientes)
            pendientes = session.scalars(select(IngresoDiferido).where(IngresoDiferido.estado == "Pendiente")).all()
            total_tarjetas = sum(p.monto_acreditar for p in pendientes)

            # 3. Bancos (Calculado desde Asientos Diarios)
            # Todo el debe a "Cuenta Bancaria" - Todo el haber de "Cuenta Bancaria"
            asientos_banco = session.scalars(select(AsientoDiario).where(AsientoDiario.cuenta == "Cuenta Bancaria")).all()
            total_bancos = sum(a.debe for a in asientos_banco) - sum(a.haber for a in asientos_banco)

            return {
                "efectivo": efectivo_fuerte,
                "tarjetas": total_tarjetas,
                "bancos": total_bancos
            }

    @staticmethod
    def obtener_ingresos_diferidos_pendientes() -> List[dict]:
        from database.models.contabilidad import IngresoDiferido
        with get_session() as session:
            ingresos = session.scalars(
                select(IngresoDiferido)
                .where(IngresoDiferido.estado == "Pendiente")
                .order_by(IngresoDiferido.fecha_acreditacion.asc())
            ).all()

            # Convert to dict to avoid detached instance issues since we don't strictly need relationships here
            resultado = []
            for i in ingresos:
                resultado.append({
                    "id": i.id,
                    "fecha_venta": i.fecha_venta,
                    "fecha_acreditacion": i.fecha_acreditacion,
                    "banco": i.banco_tarjeta,
                    "cuotas": i.cuotas,
                    "monto": i.monto_acreditar,
                    "destino": i.cuenta_destino
                })
            return resultado
