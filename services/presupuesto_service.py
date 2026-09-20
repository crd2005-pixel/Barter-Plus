from database.conexion import get_session
from database.models.presupuestos import Presupuesto, DetallePresupuesto
from database.models.producto import Producto
from typing import List, Dict, Optional
import datetime as dt

class PresupuestoService:
    @staticmethod
    def obtener_por_fecha(fecha_desde: dt.date, fecha_hasta: dt.date) -> List[Presupuesto]:
        from sqlalchemy.orm import joinedload
        from sqlalchemy import select, and_
        with get_session() as session:
            dt_desde = dt.datetime.combine(fecha_desde, dt.time.min)
            dt_hasta = dt.datetime.combine(fecha_hasta, dt.time.max)
            stmt = select(Presupuesto).options(joinedload(Presupuesto.cliente)).where(
                and_(Presupuesto.fecha >= dt_desde, Presupuesto.fecha <= dt_hasta)
            ).order_by(Presupuesto.fecha.desc())
            res = session.scalars(stmt).all()
            for p in res:
                session.expunge(p)
            return list(res)

    @staticmethod
    def guardar_presupuesto(detalles: List[Dict], cliente_id: Optional[int] = None,
                            descuento_global: float = 0.0, recargo_global: float = 0.0) -> Presupuesto:
        """
        Bypass estricto: Guarda un presupuesto sin afectar caja ni cuenta corriente.
        Tampoco descuenta stock.
        """
        with get_session() as session:
            try:
                nuevo_presupuesto = Presupuesto(
                    cliente_id=cliente_id,
                    estado="Pendiente",
                    descuento=descuento_global,
                    recargo=recargo_global
                )
                session.add(nuevo_presupuesto)
                session.flush()

                subtotal_general = 0.0

                for item in detalles:
                    cantidad = item['cantidad']
                    precio = item['precio_unitario']
                    desc_unitario = item.get('descuento_unitario', 0.0)
                    precio_final_item = precio - desc_unitario
                    subtotal_item = cantidad * precio_final_item
                    subtotal_general += subtotal_item

                    if item.get('producto_id'):
                        producto = session.get(Producto, item['producto_id'])
                        if not producto:
                            raise ValueError(f"Producto ID {item['producto_id']} no existe.")
                        codigo = producto.codigo_barras
                        desc = producto.nombre
                    else:
                        codigo = None
                        desc = item.get('nombre', 'Artículo genérico')

                    det_obj = DetallePresupuesto(
                        presupuesto_id=nuevo_presupuesto.id,
                        producto_id=item.get('producto_id'),
                        codigo_barras=codigo,
                        descripcion=desc,
                        cantidad=cantidad,
                        precio_unitario=precio,
                        descuento_unitario=desc_unitario,
                        subtotal=subtotal_item
                    )
                    session.add(det_obj)

                total_final = subtotal_general - descuento_global + recargo_global
                nuevo_presupuesto.subtotal = subtotal_general
                nuevo_presupuesto.total = total_final

                session.commit()
                session.refresh(nuevo_presupuesto)
                session.expunge(nuevo_presupuesto)
                return nuevo_presupuesto

            except Exception as e:
                session.rollback()
                raise e

    @staticmethod
    def obtener_recientes(limite: int = 50) -> List[dict]:
        from sqlalchemy import select
        with get_session() as session:
            presupuestos = session.scalars(
                select(Presupuesto)
                .order_by(Presupuesto.fecha.desc())
                .limit(limite)
            ).all()

            return [{
                "id": p.id,
                "fecha": p.fecha,
                "cliente_id": p.cliente_id,
                "total": p.total,
                "estado": p.estado
            } for p in presupuestos]

    @staticmethod
    def obtener_detalle(presupuesto_id: int) -> List[dict]:
        from sqlalchemy import select
        with get_session() as session:
            detalles = session.scalars(
                select(DetallePresupuesto)
                .where(DetallePresupuesto.presupuesto_id == presupuesto_id)
            ).all()
            return [{
                "producto_id": d.producto_id,
                "codigo": d.codigo_barras or "",
                "nombre": d.descripcion,
                "cantidad": d.cantidad,
                "precio_base": d.precio_unitario,
                "descuento_unit": d.descuento_unitario,
                "subtotal": d.subtotal
            } for d in detalles]
