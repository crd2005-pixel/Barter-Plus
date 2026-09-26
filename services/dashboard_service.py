from database.conexion import get_session
from database.models.producto import Producto
from database.models.venta import Venta, DetalleVenta
from database.models.cliente import ClienteCuentaCorriente
from database.models.proveedor import ProveedorCuentaCorriente
from sqlalchemy import select, func, and_
import datetime as dt

class DashboardService:
    @staticmethod
    def obtener_liquidez_neta() -> float:
        from services.registros_service import RegistrosService
        # (Caja + Bancos + Cheques Pendientes) - Deudas a Proveedores.
        liquidez = RegistrosService.obtener_liquidez_actual()
        activos = liquidez["efectivo"] + liquidez["tarjetas"] + liquidez["bancos"]

        # Obtener deudas a proveedores
        deuda_proveedores = 0.0
        with get_session() as session:
            # Aggregate last saldo per proveedor
            subq = session.query(
                ProveedorCuentaCorriente.proveedor_id,
                func.max(ProveedorCuentaCorriente.id).label('max_id')
            ).group_by(ProveedorCuentaCorriente.proveedor_id).subquery()

            ultimos_movs = session.query(ProveedorCuentaCorriente).join(
                subq, ProveedorCuentaCorriente.id == subq.c.max_id
            ).all()

            deuda_proveedores = sum(m.saldo for m in ultimos_movs if m.saldo > 0)

        return activos - deuda_proveedores

    @staticmethod
    def obtener_ventas_del_mes() -> float:
        hoy = dt.date.today()
        inicio_mes = hoy.replace(day=1)
        with get_session() as session:
            dt_desde = dt.datetime.combine(inicio_mes, dt.time.min)
            dt_hasta = dt.datetime.combine(hoy, dt.time.max)
            total = session.scalar(
                select(func.sum(Venta.total))
                .where(and_(Venta.fecha >= dt_desde, Venta.fecha <= dt_hasta, Venta.estado == "Completado"))
            )
            return total or 0.0

    @staticmethod
    def obtener_cuentas_a_cobrar() -> float:
        with get_session() as session:
            subq = session.query(
                ClienteCuentaCorriente.cliente_id,
                func.max(ClienteCuentaCorriente.id).label('max_id')
            ).group_by(ClienteCuentaCorriente.cliente_id).subquery()

            ultimos_movs = session.query(ClienteCuentaCorriente).join(
                subq, ClienteCuentaCorriente.id == subq.c.max_id
            ).all()

            deuda_clientes = sum(m.saldo for m in ultimos_movs if m.saldo > 0)
            return deuda_clientes

    @staticmethod
    def obtener_valor_inventario() -> float:
        with get_session() as session:
            # Sumatoria de (costo * stock)
            valor = session.scalar(
                select(func.sum(Producto.costo * Producto.stock_actual))
                .where(Producto.stock_actual > 0)
            )
            return valor or 0.0

    @staticmethod
    def obtener_top_productos_mes(limite: int = 10) -> list[dict]:
        hoy = dt.date.today()
        inicio_mes = hoy.replace(day=1)
        with get_session() as session:
            dt_desde = dt.datetime.combine(inicio_mes, dt.time.min)
            dt_hasta = dt.datetime.combine(hoy, dt.time.max)

            stmt = (
                select(
                    Producto.codigo_barras,
                    Producto.sku,
                    Producto.nombre,
                    func.sum(DetalleVenta.cantidad).label("total_cantidad"),
                    func.sum(DetalleVenta.subtotal).label("total_ingreso")
                )
                .join(DetalleVenta, DetalleVenta.producto_id == Producto.id)
                .join(Venta, Venta.id == DetalleVenta.venta_id)
                .where(and_(Venta.fecha >= dt_desde, Venta.fecha <= dt_hasta, Venta.estado == "Completado"))
                .group_by(Producto.id)
                .order_by(func.sum(DetalleVenta.cantidad).desc())
                .limit(limite)
            )
            resultados = session.execute(stmt).all()

            lista = []
            for r in resultados:
                lista.append({
                    "codigo": r.codigo_barras or r.sku or "-",
                    "producto": r.nombre,
                    "cantidad": r.total_cantidad,
                    "ingreso": r.total_ingreso
                })
            return lista

    @staticmethod
    def obtener_alertas_stock() -> list[dict]:
        with get_session() as session:
            # Productos donde stock actual es <= al stock mínimo (y mínimo configurado > 0) o stock <= 0
            stmt = select(Producto).where(
                (Producto.stock_actual <= 0) |
                (and_(Producto.stock_minimo > 0, Producto.stock_actual <= Producto.stock_minimo))
            ).order_by(Producto.stock_actual.asc())

            productos = session.scalars(stmt).all()

            lista = []
            for p in productos:
                lista.append({
                    "producto": p.nombre,
                    "stock_actual": p.stock_actual,
                    "stock_minimo": p.stock_minimo
                })
            return lista
