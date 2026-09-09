from database.conexion import get_session
from database.models.cliente import Cliente, ClienteCuentaCorriente
from typing import Optional
from sqlalchemy import select

class ClienteService:
    @staticmethod
    def crear_cliente(nombre: str, dni: Optional[str] = None, es_especial: bool = False) -> Cliente:
        with get_session() as session:
            try:
                nuevo_cliente = Cliente(nombre=nombre, dni=dni, es_especial=es_especial)
                session.add(nuevo_cliente)
                session.commit()
                session.refresh(nuevo_cliente)
                session.expunge(nuevo_cliente)
                return nuevo_cliente
            except Exception as e:
                session.rollback()
                raise e

    @staticmethod
    def agregar_movimiento_cc(cliente_id: int, concepto: str, debe: float = 0.0, haber: float = 0.0, venta_id: Optional[int] = None) -> ClienteCuentaCorriente:
        with get_session() as session:
            try:
                # Calcular el nuevo saldo (asumiendo que el saldo = sum(debe) - sum(haber))
                # Buscamos el último movimiento para obtener el saldo arrastrado
                ultimo_mov = session.query(ClienteCuentaCorriente)\
                    .filter_by(cliente_id=cliente_id)\
                    .order_by(ClienteCuentaCorriente.id.desc())\
                    .first()

                saldo_anterior = ultimo_mov.saldo if ultimo_mov else 0.0
                nuevo_saldo = saldo_anterior + debe - haber

                nuevo_movimiento = ClienteCuentaCorriente(
                    cliente_id=cliente_id,
                    concepto=concepto,
                    debe=debe,
                    haber=haber,
                    saldo=nuevo_saldo,
                    venta_id=venta_id
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
    def listar_todos() -> list[Cliente]:
        with get_session() as session:
            clientes = session.scalars(select(Cliente)).all()
            for c in clientes:
                session.expunge(c)
            return list(clientes)

    @staticmethod
    def registrar_pago_cc(cliente_id: int, monto: float) -> tuple[float, float]:
        """
        Registra un pago a la cuenta corriente del cliente de forma atómica.
        Retorna (deuda_anterior, nueva_deuda).
        """
        from database.models.caja import Caja, MovimientoCaja
        with get_session() as session:
            try:
                # 1. Obtener deuda actual
                ultimo_mov = session.query(ClienteCuentaCorriente)\
                    .filter_by(cliente_id=cliente_id)\
                    .order_by(ClienteCuentaCorriente.id.desc())\
                    .first()

                deuda_anterior = ultimo_mov.saldo if ultimo_mov else 0.0
                if deuda_anterior <= 0:
                    raise ValueError("El cliente no registra deuda.")

                if monto > deuda_anterior:
                    raise ValueError("El monto supera la deuda actual.")

                nuevo_saldo = deuda_anterior - monto

                # 2. Registrar pago en CC
                nuevo_mov_cc = ClienteCuentaCorriente(
                    cliente_id=cliente_id,
                    concepto="Pago a Cuenta (POS)",
                    debe=0.0,
                    haber=monto,
                    saldo=nuevo_saldo
                )
                session.add(nuevo_mov_cc)

                # 3. Impactar en Caja
                caja_abierta = session.query(Caja).filter_by(estado="Abierta").order_by(Caja.id.desc()).first()
                if not caja_abierta:
                    caja_abierta = Caja(estado="Abierta")
                    session.add(caja_abierta)
                    session.flush()

                mov_caja = MovimientoCaja(
                    caja_id=caja_abierta.id,
                    tipo="Ingreso",
                    concepto=f"Pago CC Cliente #{cliente_id}",
                    monto=monto,
                    metodo="Efectivo"
                )
                session.add(mov_caja)

                session.commit()
                return deuda_anterior, nuevo_saldo
            except Exception as e:
                session.rollback()
                raise e

    @staticmethod
    def obtener_deuda(cliente_id: int) -> float:
        with get_session() as session:
            ultimo_mov = session.query(ClienteCuentaCorriente)\
                .filter_by(cliente_id=cliente_id)\
                .order_by(ClienteCuentaCorriente.id.desc())\
                .first()
            return ultimo_mov.saldo if ultimo_mov else 0.0
