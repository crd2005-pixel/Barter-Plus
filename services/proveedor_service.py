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
    def obtener_estado_cc(proveedor_id: int):
        with get_session() as session:
            movimientos = session.query(ProveedorCuentaCorriente).filter(
                ProveedorCuentaCorriente.proveedor_id == proveedor_id
            ).order_by(ProveedorCuentaCorriente.fecha.asc()).all()

            return [{
                "id": m.id,
                "fecha": m.fecha,
                "concepto": m.concepto,
                "debe": m.debe,
                "haber": m.haber,
                "saldo": m.saldo,
                "fecha_vencimiento": m.fecha_vencimiento
            } for m in movimientos]

    @staticmethod
    def obtener_deuda_total(proveedor_id: int) -> float:
        with get_session() as session:
            ultimo_mov = session.query(ProveedorCuentaCorriente)\
                .filter_by(proveedor_id=proveedor_id)\
                .order_by(ProveedorCuentaCorriente.id.desc())\
                .first()
            return ultimo_mov.saldo if ultimo_mov else 0.0

    @staticmethod
    def registrar_pago(proveedor_id: int, datos_pago: dict) -> ProveedorCuentaCorriente:
        """
        Registra un pago al proveedor (Debe) reduciendo nuestro saldo (deuda).
        Impacta dinámicamente en Caja, Cheques o Asientos según el método.
        """
        with get_session() as session:
            try:
                metodo = datos_pago["metodo"]
                monto = datos_pago["monto"]
                cheque_id = datos_pago["cheque_id"]
                observaciones = datos_pago["observaciones"]

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

                # Definir concepto basado en observaciones
                concepto_cc = f"Pago a Proveedor ({metodo})"
                if metodo == "Otros (Canje/Baterías)" and observaciones:
                    concepto_cc = f"Pago Otros: {observaciones}"
                elif observaciones:
                    concepto_cc += f" - {observaciones}"

                # Paso A: Registrar CC Proveedor (Reducir Deuda)
                mov_cc = ProveedorCuentaCorriente(
                    proveedor_id=proveedor_id,
                    concepto=concepto_cc,
                    debe=monto,
                    haber=0.0,
                    saldo=nuevo_saldo
                )
                session.add(mov_cc)

                # Paso B: Impactar Activos (Caja/Bancos/Cheques)
                if metodo == "Efectivo":
                    caja_abierta = session.scalars(select(Caja).where(Caja.estado == "Abierta")).first()
                    if not caja_abierta:
                        raise ValueError("No hay una caja abierta para extraer el pago en efectivo.")
                    mov_caja = MovimientoCaja(
                        caja_id=caja_abierta.id,
                        tipo="Egreso",
                        concepto=f"Pago Proveedor #{proveedor_id}",
                        monto=monto,
                        metodo="Efectivo"
                    )
                    session.add(mov_caja)
                elif metodo == "Transferencia":
                    caja_abierta = session.scalars(select(Caja).where(Caja.estado == "Abierta")).first()
                    if not caja_abierta:
                        raise ValueError("No hay una caja abierta para atar la transferencia.")
                    mov_caja = MovimientoCaja(
                        caja_id=caja_abierta.id,
                        tipo="Egreso",
                        concepto=f"Pago Proveedor #{proveedor_id}",
                        monto=monto,
                        metodo="Transferencia"
                    )
                    session.add(mov_caja)

                    from database.models.contabilidad import AsientoDiario
                    import datetime as dt
                    asiento = AsientoDiario(
                        fecha=dt.datetime.utcnow(),
                        cuenta="Cuenta Bancaria",
                        debe=0.0,
                        haber=monto,
                        descripcion=f"Egreso Pago Proveedor #{proveedor_id}"
                    )
                    session.add(asiento)
                elif metodo == "Cheque de Terceros":
                    from database.models.cheques import Cheque
                    if not cheque_id:
                        raise ValueError("ID de cheque no proporcionado.")
                    cheque = session.query(Cheque).get(cheque_id)
                    if not cheque:
                        raise ValueError("El cheque no existe en el sistema.")
                    if cheque.estado != "Pendiente":
                        raise ValueError(f"El cheque no se encuentra disponible (Estado actual: {cheque.estado}).")

                    # Consumir el cheque
                    cheque.estado = f"Entregado a Proveedor #{proveedor_id}"

                session.commit()
                session.refresh(mov_cc)
                session.expunge(mov_cc)
                return mov_cc
            except Exception as e:
                session.rollback()
                raise e
