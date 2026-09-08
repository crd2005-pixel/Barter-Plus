from database.conexion import get_session
from database.models.cliente import Cliente, ClienteCuentaCorriente
from typing import Optional
from sqlalchemy import select

class ClienteService:
    @staticmethod
    def crear_cliente(nombre: str, dni: Optional[str] = None) -> Cliente:
        with get_session() as session:
            try:
                nuevo_cliente = Cliente(nombre=nombre, dni=dni)
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
