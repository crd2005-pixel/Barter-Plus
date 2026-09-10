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
