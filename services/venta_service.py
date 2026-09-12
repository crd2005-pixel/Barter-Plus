from sqlalchemy import select
from database.conexion import get_session
from database.models.venta import Venta, DetalleVenta
from database.models.producto import Producto
from database.models.cliente import Cliente, ClienteCuentaCorriente
from database.models.caja import Caja, MovimientoCaja
from database.models.contabilidad import AsientoDiario, LibroIVA, IngresoDiferido
from database.models.caja import Caja, MovimientoCaja
from typing import List, Dict, Optional
import datetime as dt

class VentaService:
    @staticmethod
    def procesar_venta(detalles: List[Dict], cliente_id: Optional[int] = None,
                       metodo_pago: str = "Efectivo", monto_abonado: float = 0.0,
                       descuento_global: float = 0.0, recargo_global: float = 0.0,
                       tipo_comprobante: str = "Remito", datos_tarjeta: Optional[Dict] = None) -> Venta:
        """
        Procesa una venta completa.
        `detalles` es una lista de diccionarios: {'producto_id': int, 'cantidad': float, 'precio_unitario': float, 'descuento_unitario': float}
        El precio_unitario ya debe venir calculado (ej. con el -10% de cliente si aplica).
        """
        with get_session() as session:
            try:
                nueva_venta = Venta(
                    cliente_id=cliente_id,
                    metodo_pago=metodo_pago,
                    estado="Completada",
                    tipo_comprobante=tipo_comprobante,
                    descuento=descuento_global,
                    recargo=recargo_global
                )
                session.add(nueva_venta)
                session.flush()

                subtotal_venta = 0.0

                for item in detalles:
                    producto = session.get(Producto, item['producto_id'])
                    if not producto:
                        raise ValueError(f"Producto ID {item['producto_id']} no encontrado.")

                    cantidad = item['cantidad']
                    precio = item['precio_unitario']
                    desc_unitario = item.get('descuento_unitario', 0.0)
                    precio_final_item = precio - desc_unitario

                    # Disminuir stock real, considerando fraccionamiento
                    descuento_stock = cantidad
                    if producto.es_granel and producto.divisor_granel > 0:
                        descuento_stock = cantidad / producto.divisor_granel

                    producto.stock_actual -= descuento_stock

                    subtotal_item = cantidad * precio_final_item
                    subtotal_venta += subtotal_item

                    detalle = DetalleVenta(
                        venta_id=nueva_venta.id,
                        producto_id=producto.id,
                        codigo_barras=producto.codigo_barras,
                        descripcion=producto.nombre,
                        cantidad=cantidad,
                        precio_unitario=precio,
                        descuento_unitario=desc_unitario,
                        subtotal=subtotal_item
                    )
                    session.add(detalle)

                # Calcular total final y recargos
                if datos_tarjeta and datos_tarjeta.get('interes', 0.0) > 0:
                    tasa = datos_tarjeta['interes']
                    recargo_tarjeta = (subtotal_venta - descuento_global) * (tasa / 100)
                    recargo_global += recargo_tarjeta
                    nueva_venta.recargo = recargo_global

                total_final = subtotal_venta - descuento_global + recargo_global
                nueva_venta.subtotal = subtotal_venta
                nueva_venta.total = total_final

                # Manejo de Pago y Vuelto
                if metodo_pago == "Efectivo":
                    nueva_venta.pago_efectivo = monto_abonado
                    nueva_venta.vuelto = monto_abonado - total_final if monto_abonado > total_final else 0.0
                elif metodo_pago == "Cuenta Corriente" and cliente_id:
                    nueva_venta.pago_ctacte = total_final

                    # Generar deuda en cuenta corriente
                    mov_cc = ClienteCuentaCorriente(
                        cliente_id=cliente_id,
                        concepto=f"Venta #{nueva_venta.id}",
                        debe=total_final,
                        haber=0.0,
                        venta_id=nueva_venta.id
                    )
                    # Calculamos saldo anterior
                    ultimo_mov = session.query(ClienteCuentaCorriente)\
                        .filter_by(cliente_id=cliente_id)\
                        .order_by(ClienteCuentaCorriente.id.desc()).first()
                    saldo_ant = ultimo_mov.saldo if ultimo_mov else 0.0
                    mov_cc.saldo = saldo_ant + total_final
                    session.add(mov_cc)
                else:
                    # Tarjeta, Transferencia, etc. (se abona exacto en este flujo simple)
                    nueva_venta.vuelto = 0.0

                # Calcular subtotal impositivo y de IVA (asumiendo 21% por defecto o simplificado)
                subtotal = total_final / 1.21
                iva_total = total_final - subtotal

                # Contabilidad y Fiscalidad
                if tipo_comprobante.startswith("Factura"):
                    # Libro Diario
                    asiento_venta = AsientoDiario(
                        fecha=nueva_venta.fecha,
                        cuenta="Ventas",
                        debe=0.0,
                        haber=subtotal,
                        descripcion=f"Factura Venta #{nueva_venta.id}"
                    )
                    session.add(asiento_venta)

                    asiento_iva = AsientoDiario(
                        fecha=nueva_venta.fecha,
                        cuenta="IVA Débito Fiscal",
                        debe=0.0,
                        haber=iva_total,
                        descripcion=f"IVA Factura Venta #{nueva_venta.id}"
                    )
                    session.add(asiento_iva)

                    # Libro IVA
                    libro_iva = LibroIVA(
                        fecha=nueva_venta.fecha,
                        tipo="Venta",
                        comprobante=f"{tipo_comprobante} {nueva_venta.id}",
                        neto_gravado=subtotal,
                        iva_21=iva_total,
                        total=total_final,
                        venta_id=nueva_venta.id
                    )
                    session.add(libro_iva)

# --- INTEGRACIÓN CON CUENTA CORRIENTE Y CAJA ---
                if metodo_pago == "Cuenta Corriente":
                    if not cliente_id:
                        raise ValueError("Debe especificar un cliente para ventas en Cuenta Corriente.")

                    ultimo_mov = session.query(ClienteCuentaCorriente)\
                        .filter_by(cliente_id=cliente_id)\
                        .order_by(ClienteCuentaCorriente.id.desc())\
                        .first()

                    saldo_anterior = ultimo_mov.saldo if ultimo_mov else 0.0
                    nuevo_saldo = saldo_anterior + total_final

                    mov_cc = ClienteCuentaCorriente(
                        cliente_id=cliente_id,
                        concepto=f"Venta #{nueva_venta.id}",
                        debe=total_final,
                        haber=0.0,
                        saldo=nuevo_saldo,
                        venta_id=nueva_venta.id
                    )
                    session.add(mov_cc)
                elif metodo_pago in ["Tarjeta", "Débito"] and datos_tarjeta:
                    # Registramos el Ingreso Diferido, no toca caja física
                    fecha_acred = dt.datetime.utcnow().date() + dt.timedelta(days=datos_tarjeta.get('plazo_dias', 0))

                    ingreso_dif = IngresoDiferido(
                        venta_id=nueva_venta.id,
                        fecha_venta=nueva_venta.fecha,
                        fecha_acreditacion=fecha_acred,
                        banco_tarjeta=datos_tarjeta.get('banco', 'No Especificado'),
                        cuotas=datos_tarjeta.get('cuotas', 1),
                        monto_original=subtotal_venta - descuento_global,
                        interes_aplicado=datos_tarjeta.get('interes', 0.0),
                        monto_acreditar=total_final,
                        cuenta_destino="Banco Central / Adquirente",
                        estado="Pendiente"
                    )
                    session.add(ingreso_dif)
                else:
                    caja_activa = session.scalars(select(Caja).where(Caja.estado == "Abierta")).first()
                    if not caja_activa:
                        raise ValueError("No hay una caja abierta. Debe abrir la caja antes de procesar ventas.")

                    mov_caja = MovimientoCaja(
                        caja_id=caja_activa.id,
                        tipo="Ingreso",
                        concepto=f"Venta #{nueva_venta.id} - {tipo_comprobante}",
                        monto=total_final,
                        metodo=metodo_pago,
                        venta_id=nueva_venta.id
                    )
                    session.add(mov_caja)
                # -----------------------------------------------

                session.commit()
                session.refresh(nueva_venta)
                session.expunge(nueva_venta)
                return nueva_venta

            except Exception as e:
                session.rollback()
                raise e
