from database.conexion import get_session
from database.models.proveedor import Proveedor, ProveedorCuentaCorriente
from database.models.caja import Caja, MovimientoCaja
from typing import Optional, List
from sqlalchemy import select

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
    def listar_todos() -> List[Proveedor]:
        with get_session() as session:
            provs = session.scalars(select(Proveedor)).all()
            for p in provs:
                session.expunge(p)
            return list(provs)

    @staticmethod
    def agregar_movimiento_cc(proveedor_id: int, concepto: str, debe: float = 0.0, haber: float = 0.0) -> ProveedorCuentaCorriente:
        with get_session() as session:
            try:
                # Debe = Salidas de dinero al proveedor (Cancelación deuda)
                # Haber = Facturas del proveedor (Nos endeudamos)
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

    @staticmethod
    def obtener_estado_cc(proveedor_id: int) -> List[ProveedorCuentaCorriente]:
        with get_session() as session:
            movimientos = session.scalars(
                select(ProveedorCuentaCorriente)
                .where(ProveedorCuentaCorriente.proveedor_id == proveedor_id)
                .order_by(ProveedorCuentaCorriente.fecha.asc())
            ).all()
            for m in movimientos:
                session.expunge(m)
            return list(movimientos)

    @staticmethod
    def obtener_deuda_total(proveedor_id: int) -> float:
        with get_session() as session:
            ultimo_mov = session.query(ProveedorCuentaCorriente)\
                .filter_by(proveedor_id=proveedor_id)\
                .order_by(ProveedorCuentaCorriente.id.desc())\
                .first()
            return ultimo_mov.saldo if ultimo_mov else 0.0

    @staticmethod
    def registrar_pago(proveedor_id: int, monto: float, metodo: str = "Efectivo", origen_caja: bool = True) -> ProveedorCuentaCorriente:
        """
        Registra un pago al proveedor (Debe) reduciendo nuestro saldo (deuda).
        Opcionalmente extrae dinero de la caja activa.
        """
        with get_session() as session:
            try:
                ultimo_mov = session.query(ProveedorCuentaCorriente)\
                    .filter_by(proveedor_id=proveedor_id)\
                    .order_by(ProveedorCuentaCorriente.id.desc())\
                    .first()

                saldo_anterior = ultimo_mov.saldo if ultimo_mov else 0.0
                if saldo_anterior <= 0:
                    raise ValueError("No se registra deuda con este proveedor.")
                if monto > saldo_anterior:
                    raise ValueError(f"El monto supera la deuda actual (${saldo_anterior:.2f}).")

                nuevo_saldo = saldo_anterior - monto

                mov_cc = ProveedorCuentaCorriente(
                    proveedor_id=proveedor_id,
                    concepto=f"Pago a Proveedor ({metodo})",
                    debe=monto,
                    haber=0.0,
                    saldo=nuevo_saldo
                )
                session.add(mov_cc)

                if origen_caja:
                    caja_abierta = session.scalars(select(Caja).where(Caja.estado == "Abierta")).first()
                    if not caja_abierta:
                        raise ValueError("No hay una caja abierta para extraer el pago.")

                    mov_caja = MovimientoCaja(
                        caja_id=caja_abierta.id,
                        tipo="Egreso",
                        concepto=f"Pago Proveedor #{proveedor_id} - CC",
                        monto=monto,
                        metodo=metodo
                    )
                    session.add(mov_caja)

                session.commit()
                session.refresh(mov_cc)
                session.expunge(mov_cc)
                return mov_cc
            except Exception as e:
                session.rollback()
                raise e
