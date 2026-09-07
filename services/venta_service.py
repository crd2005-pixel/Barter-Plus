from database.conexion import get_session
from database.models.venta import Venta, DetalleVenta
from database.models.producto import Producto
from database.models.caja import Caja, MovimientoCaja
from typing import List, Dict, Optional

class VentaService:
    @staticmethod
    def procesar_venta(detalles: List[Dict], cliente_id: Optional[int] = None, metodo_pago: str = "Efectivo", monto_abonado: float = 0.0) -> Venta:
        """
        Procesa una venta completa.
        `detalles` es una lista de diccionarios con: {'producto_id': int, 'cantidad': float}
        """
        with get_session() as session:
            try:
                # Crear encabezado de venta
                nueva_venta = Venta(
                    cliente_id=cliente_id,
                    metodo_pago=metodo_pago,
                    estado="Completada"
                )
                session.add(nueva_venta)
                session.flush() # Para obtener el ID de la venta

                total_venta = 0.0

                # Procesar detalles
                for item in detalles:
                    producto = session.get(Producto, item['producto_id'])
                    if not producto:
                        raise ValueError(f"Producto con ID {item['producto_id']} no encontrado.")

                    cantidad = item['cantidad']

                    # Disminuir stock (usamos stock_maximo como placeholder temporal del test)
                    producto.stock_maximo -= cantidad

                    subtotal = cantidad * producto.precio_minorista
                    total_venta += subtotal

                    detalle = DetalleVenta(
                        venta_id=nueva_venta.id,
                        producto_id=producto.id,
                        codigo_barras=producto.codigo_barras,
                        descripcion=producto.nombre,
                        cantidad=cantidad,
                        precio_unitario=producto.precio_minorista,
                        subtotal=subtotal
                    )
                    session.add(detalle)

                nueva_venta.total = total_venta
                nueva_venta.subtotal = total_venta

                # Manejar el pago (ejemplo simplificado)
                if metodo_pago == "Efectivo":
                    nueva_venta.pago_efectivo = monto_abonado
                    nueva_venta.vuelto = monto_abonado - total_venta if monto_abonado > total_venta else 0.0

                # Registrar en Caja (ejemplo: buscamos la última caja abierta)
                caja_abierta = session.query(Caja).filter_by(estado="Abierta").order_by(Caja.id.desc()).first()
                if not caja_abierta:
                    # Crear una caja si no hay ninguna para el test
                    caja_abierta = Caja(estado="Abierta")
                    session.add(caja_abierta)
                    session.flush()

                movimiento_caja = MovimientoCaja(
                    caja_id=caja_abierta.id,
                    tipo="Ingreso",
                    concepto=f"Venta #{nueva_venta.id}",
                    monto=total_venta,
                    metodo=metodo_pago,
                    venta_id=nueva_venta.id
                )
                session.add(movimiento_caja)

                session.commit()
                session.refresh(nueva_venta)
                session.expunge(nueva_venta)
                return nueva_venta

            except Exception as e:
                session.rollback()
                raise e
