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
    def obtener_estado_cc(cliente_id: int):
        with get_session() as session:
            movimientos = session.query(ClienteCuentaCorriente).filter(
                ClienteCuentaCorriente.cliente_id == cliente_id
            ).order_by(ClienteCuentaCorriente.fecha.asc()).all()

            return [{
                "id": m.id,
                "fecha": m.fecha,
                "concepto": m.concepto,
                "debe": m.debe,
                "haber": m.haber,
                "saldo": m.saldo,
                "venta_id": m.venta_id
            } for m in movimientos]

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

            # 2. Valores a Cobrar (Tarjetas Pendientes + Cheques Netos)
            from database.models.cheques import Cheque
            pendientes = session.scalars(select(IngresoDiferido).where(IngresoDiferido.estado == "Pendiente")).all()
            cheques = session.scalars(select(Cheque).where(Cheque.estado.notin_(["Cobrado", "Rechazado"]))).all()

            total_tarjetas = sum(p.monto_original for p in pendientes) + sum(c.monto for c in cheques)

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
    def obtener_proximas_acreditaciones() -> list[dict]:
        from database.models.caja import MovimientoCaja
        from database.models.venta import Venta
        from database.models.cheques import Cheque
        import datetime as dt
        from sqlalchemy import select, or_
        from datetime import timedelta

        with get_session() as session:
            # 1. Tarjetas (Neto extraido de MovimientoCaja directo)
            movimientos_tarjeta = session.scalars(
                select(MovimientoCaja)
                .join(Venta, MovimientoCaja.venta_id == Venta.id)
                .where(
                    MovimientoCaja.tipo == "Ingreso",
                    or_(
                        MovimientoCaja.metodo.ilike('%Tarjeta%'),
                        MovimientoCaja.metodo.ilike('%Crédito%')
                    )
                )
            ).all()

            # 2. Cheques en cartera
            cheques = session.scalars(
                select(Cheque)
                .where(Cheque.estado.notin_(["Cobrado", "Rechazado"]))
            ).all()

            resultado = []

            for mov in movimientos_tarjeta:
                venta_asociada = session.get(Venta, mov.venta_id) if mov.venta_id else None
                fecha_base = venta_asociada.fecha if venta_asociada else mov.fecha
                fecha_acreditacion = fecha_base + timedelta(days=14)

                concepto = mov.concepto or ""

                resultado.append({
                    "fecha": fecha_acreditacion.date() if isinstance(fecha_acreditacion, dt.datetime) else fecha_acreditacion,
                    "origen": "[BANCARIO] Tarjeta",
                    "cuotas": concepto,
                    "monto_neto": mov.monto,
                    "estado": "Pendiente"
                })

            for c in cheques:
                resultado.append({
                    "fecha": c.fecha_vencimiento if c.fecha_vencimiento else (c.fecha_conformacion or dt.date.today()),
                    "origen": "Físico - Cheque Circulante",
                    "tipo": "Cheque",
                    "monto_neto": c.monto,
                    "estado": c.estado
                })

            # Sort by ascending date
            resultado.sort(key=lambda x: x["fecha"])
            return resultado
