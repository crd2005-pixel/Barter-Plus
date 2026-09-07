from database.conexion import get_session
from database.models.proveedor import Proveedor, ProveedorCuentaCorriente
from typing import Optional

class ProveedorService:
    @staticmethod
    def crear_proveedor(nombre: str, cuit: Optional[str] = None) -> Proveedor:
        with get_session() as session:
            try:
                nuevo_proveedor = Proveedor(nombre=nombre, cuit=cuit)
                session.add(nuevo_proveedor)
                session.commit()
                session.refresh(nuevo_proveedor)
                session.expunge(nuevo_proveedor)
                return nuevo_proveedor
            except Exception as e:
                session.rollback()
                raise e

    @staticmethod
    def agregar_movimiento_cc(proveedor_id: int, concepto: str, debe: float = 0.0, haber: float = 0.0) -> ProveedorCuentaCorriente:
        with get_session() as session:
            try:
                # Calcular el nuevo saldo (asumiendo que el saldo = sum(haber) - sum(debe))
                # Buscamos el último movimiento para obtener el saldo arrastrado
                ultimo_mov = session.query(ProveedorCuentaCorriente)\
                    .filter_by(proveedor_id=proveedor_id)\
                    .order_by(ProveedorCuentaCorriente.id.desc())\
                    .first()

                saldo_anterior = ultimo_mov.saldo if ultimo_mov else 0.0
                nuevo_saldo = saldo_anterior + haber - debe

                nuevo_movimiento = ProveedorCuentaCorriente(
                    proveedor_id=proveedor_id,
                    concepto=concepto,
                    debe=debe,
                    haber=haber,
                    saldo=nuevo_saldo
                )
                session.add(nuevo_movimiento)
                session.commit()
                session.refresh(nuevo_movimiento)
                session.expunge(nuevo_movimiento)
                return nuevo_movimiento
            except Exception as e:
                session.rollback()
                raise e
