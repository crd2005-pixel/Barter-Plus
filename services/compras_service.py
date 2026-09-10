from database.conexion import get_session
from database.models.producto import Producto
from database.models.proveedor import Proveedor, ProveedorCuentaCorriente
from sqlalchemy import select, and_
from typing import List, Dict

class ComprasService:

    @staticmethod
    def obtener_sugerencias_pedido() -> List[dict]:
        """
        Retorna productos donde stock_actual <= 0 o stock_actual <= stock_minimo.
        Incluye sugerencia de pedido = (stock_minimo - stock_actual) o 1 si stock_minimo es 0.
        """
        from sqlalchemy.orm import joinedload
        with get_session() as session:
            # Productos con stock critico
            productos = session.scalars(
                select(Producto)
                .options(joinedload(Producto.proveedor))
                .where((Producto.stock_actual <= 0) | (Producto.stock_actual <= Producto.stock_minimo))
                .order_by(Producto.stock_actual.asc())
            ).all()

            sugerencias = []
            for p in productos:
                # Calcular cantidad a pedir
                if p.stock_minimo > 0:
                    cant = p.stock_minimo - p.stock_actual
                else:
                    cant = abs(p.stock_actual) + 5 # Sugerir cubrir el negativo + 5 de margen
                    if cant <= 0: cant = 1

                # Para evitar problemas de serialización UI, mandamos diccionarios o objetos desconectados
                session.expunge(p)
                sugerencias.append({
                    'producto': p,
                    'cantidad_sugerida': cant
                })

            return sugerencias

    @staticmethod
    def ingresar_factura_compra(proveedor_id: int, num_factura: str, detalles: List[Dict], total_factura: float):
        """
        Ingresa una factura.
        `detalles` es lista de dicts: {'producto_id': int, 'cantidad': float, 'nuevo_costo': float}
        Reglas:
        - Sumar cantidad al stock_actual.
        - Sobrescribir costo base.
        - Registrar deuda en proveedor_cuenta_corriente.
        """
        with get_session() as session:
            try:
                # 1. Actualizar Stock y Costos
                for item in detalles:
                    prod = session.get(Producto, item['producto_id'])
                    if not prod:
                        raise ValueError(f"Producto ID {item['producto_id']} no encontrado.")

                    prod.stock_actual += item['cantidad']

                    # El nuevo costo sobreescribe el costo base
                    if item['nuevo_costo'] > 0:
                        prod.costo = item['nuevo_costo']
                        # Si tiene margen asignado, deberíamos recalcular el precio público?
                        # Por ahora mantenemos solo la actualización del costo.

                # 2. Cuenta Corriente del Proveedor
                ultimo_mov = session.query(ProveedorCuentaCorriente)\
                    .filter_by(proveedor_id=proveedor_id)\
                    .order_by(ProveedorCuentaCorriente.id.desc())\
                    .first()

                saldo_anterior = ultimo_mov.saldo if ultimo_mov else 0.0
                # Cuando compramos, nos endeudamos: aumenta nuestro Haber hacia él.
                # (debe = pagos que le hacemos, haber = deuda que tomamos)
                nuevo_saldo = saldo_anterior + total_factura

                mov_cc = ProveedorCuentaCorriente(
                    proveedor_id=proveedor_id,
                    concepto=f"Factura Compra #{num_factura}",
                    debe=0.0,
                    haber=total_factura,
                    saldo=nuevo_saldo
                )
                session.add(mov_cc)

                session.commit()
            except Exception as e:
                session.rollback()
                raise e
