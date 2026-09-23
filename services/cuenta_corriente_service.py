from database.conexion import get_session
from database.models.cliente import ClienteCuentaCorriente
from database.models.proveedor import ProveedorCuentaCorriente
import datetime as dt

class CuentaCorrienteService:
    @staticmethod
    def obtener_historial_cliente(cliente_id: int):
        with get_session() as session:
            movimientos = session.query(ClienteCuentaCorriente).filter(
                ClienteCuentaCorriente.cliente_id == cliente_id
            ).order_by(ClienteCuentaCorriente.fecha.asc()).all()
            return [m for m in movimientos]

    @staticmethod
    def obtener_saldo_cliente(cliente_id: int) -> float:
        with get_session() as session:
            ultimo = session.query(ClienteCuentaCorriente).filter(
                ClienteCuentaCorriente.cliente_id == cliente_id
            ).order_by(ClienteCuentaCorriente.id.desc()).first()
            return ultimo.saldo if ultimo else 0.0

    @staticmethod
    def registrar_movimiento_cliente(cliente_id: int, concepto: str, debe: float = 0.0, haber: float = 0.0, venta_id: int = None):
        with get_session() as session:
            try:
                saldo_anterior = 0.0
                ultimo = session.query(ClienteCuentaCorriente).filter(
                    ClienteCuentaCorriente.cliente_id == cliente_id
                ).order_by(ClienteCuentaCorriente.id.desc()).first()

                if ultimo:
                    saldo_anterior = ultimo.saldo

                nuevo_saldo = saldo_anterior + debe - haber

                nuevo_mov = ClienteCuentaCorriente(
                    cliente_id=cliente_id,
                    fecha=dt.datetime.now(),
                    concepto=concepto,
                    debe=debe,
                    haber=haber,
                    saldo=nuevo_saldo,
                    venta_id=venta_id
                )
                session.add(nuevo_mov)
                session.commit()
                return nuevo_mov
            except Exception as e:
                session.rollback()
                raise e

    @staticmethod
    def obtener_historial_proveedor(proveedor_id: int):
        with get_session() as session:
            movimientos = session.query(ProveedorCuentaCorriente).filter(
                ProveedorCuentaCorriente.proveedor_id == proveedor_id
            ).order_by(ProveedorCuentaCorriente.fecha.asc()).all()
            return [m for m in movimientos]

    @staticmethod
    def obtener_saldo_proveedor(proveedor_id: int) -> float:
        with get_session() as session:
            ultimo = session.query(ProveedorCuentaCorriente).filter(
                ProveedorCuentaCorriente.proveedor_id == proveedor_id
            ).order_by(ProveedorCuentaCorriente.id.desc()).first()
            return ultimo.saldo if ultimo else 0.0

    @staticmethod
    def registrar_movimiento_proveedor(proveedor_id: int, concepto: str, debe: float = 0.0, haber: float = 0.0, fecha_vencimiento=None):
        with get_session() as session:
            try:
                saldo_anterior = 0.0
                ultimo = session.query(ProveedorCuentaCorriente).filter(
                    ProveedorCuentaCorriente.proveedor_id == proveedor_id
                ).order_by(ProveedorCuentaCorriente.id.desc()).first()

                if ultimo:
                    saldo_anterior = ultimo.saldo

                nuevo_saldo = saldo_anterior + debe - haber

                nuevo_mov = ProveedorCuentaCorriente(
                    proveedor_id=proveedor_id,
                    fecha=dt.datetime.now(),
                    concepto=concepto,
                    debe=debe,
                    haber=haber,
                    saldo=nuevo_saldo,
                    fecha_vencimiento=fecha_vencimiento
                )
                session.add(nuevo_mov)
                session.commit()
                return nuevo_mov
            except Exception as e:
                session.rollback()
                raise e
