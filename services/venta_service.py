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
    def _calcular_fecha_habil(dias_habiles: int) -> dt.date:
        fecha_actual = dt.datetime.utcnow().date()
        dias_agregados = 0
        while dias_agregados < dias_habiles:
            fecha_actual += dt.timedelta(days=1)
            # 0=Lunes, 1=Martes, ..., 4=Viernes, 5=Sábado, 6=Domingo
            if fecha_actual.weekday() < 5:
                dias_agregados += 1
        return fecha_actual

    @staticmethod
    def procesar_venta(detalles: List[Dict], cliente_id: Optional[int] = None,
                       metodo_pago: str = "Efectivo", monto_abonado: float = 0.0,
                       descuento_global: float = 0.0, recargo_global: float = 0.0,
                       tipo_comprobante: str = "Remito", datos_tarjeta: Optional[Dict] = None,
                       presupuesto_id: Optional[int] = None, datos_cheque: Optional[Dict] = None,
                       desglose_pagos: Optional[Dict] = None) -> Venta:
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
                    cantidad = item['cantidad']
                    precio = item['precio_unitario']
                    desc_unitario = item.get('descuento_unitario', 0.0)
                    precio_final_item = precio - desc_unitario
                    subtotal_item = cantidad * precio_final_item
                    subtotal_venta += subtotal_item

                    if item.get('producto_id'):
                        producto = session.get(Producto, item['producto_id'])
                        if not producto:
                            raise ValueError(f"Producto ID {item['producto_id']} no encontrado.")

                        descuento_stock = cantidad
                        if producto.es_granel and producto.divisor_granel > 0:
                            descuento_stock = cantidad / producto.divisor_granel

                        producto.stock_actual -= descuento_stock

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
                    else:
                        # Item Manual / Libre
                        detalle = DetalleVenta(
                            venta_id=nueva_venta.id,
                            producto_id=None,
                            codigo_barras="MAN-001",
                            descripcion=item.get('nombre', 'Ítem Manual'),
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
                if metodo_pago == "Combinado":
                    pass # Handled below in the desglose loop
                elif metodo_pago == "Cuenta Corriente":
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
                elif metodo_pago in ["Tarjeta", "Débito"] or (metodo_pago == "Combinado" and desglose_pagos and desglose_pagos.get("Tarjeta de Crédito", 0) > 0):
                    # We might have `datos_tarjeta` directly (normal flow) or inside the desglose.
                    tarjeta_metadata = datos_tarjeta if metodo_pago != "Combinado" else desglose_pagos.get("datos_tarjeta")
                    monto_cred_neto = total_final if metodo_pago != "Combinado" else desglose_pagos.get("Tarjeta de Crédito", 0)
                    monto_cred_bruto = monto_cred_neto # By default

                    if not tarjeta_metadata or not tarjeta_metadata.get('lote') or not tarjeta_metadata.get('cupon'):
                        raise ValueError("El número de Lote y Cupón son obligatorios para pagos con Tarjeta.")

                    dias_habiles = tarjeta_metadata.get('plazo_dias', 0)
                    fecha_acred = VentaService._calcular_fecha_habil(dias_habiles)
                    tasa = tarjeta_metadata.get('interes', 0.0)
                    monto_cred_bruto = monto_cred_neto * (1 + (tasa/100))

                    ingreso_dif = IngresoDiferido(
                        venta_id=nueva_venta.id,
                        fecha_venta=nueva_venta.fecha,
                        fecha_acreditacion=fecha_acred,
                        banco_tarjeta=tarjeta_metadata.get('banco', 'No Especificado'),
                        cuotas=tarjeta_metadata.get('cuotas', 1),
                        monto_original=monto_cred_neto,
                        interes_aplicado=tasa,
                        monto_acreditar=monto_cred_bruto,
                        lote=tarjeta_metadata.get('lote'),
                        cupon=tarjeta_metadata.get('cupon'),
                        cuenta_destino="Banco Central / Adquirente",
                        estado="Pendiente"
                    )
                    session.add(ingreso_dif)
                elif metodo_pago == "Transferencia":
                    # Registramos la transferencia bancaria (no entra en la caja física)
                    asiento_banco = AsientoDiario(
                        fecha=nueva_venta.fecha,
                        cuenta="Cuenta Bancaria",
                        debe=total_final,
                        haber=0.0,
                        descripcion=f"Venta Transferencia #{nueva_venta.id}",
                        venta_id=nueva_venta.id
                    )
                    session.add(asiento_banco)
                elif metodo_pago == "Cheque":
                    if not datos_cheque:
                        raise ValueError("Los datos del cheque son obligatorios si el método de pago es 'Cheque'.")

                    from database.models.cheques import Cheque
                    nuevo_cheque = Cheque(
                        venta_id=nueva_venta.id,
                        banco=datos_cheque.get('banco', ''),
                        numero_cheque=datos_cheque.get('numero_cheque', ''),
                        fecha_conformacion=datos_cheque.get('fecha_conformacion'),
                        fecha_vencimiento=datos_cheque.get('fecha_vencimiento'),
                        tipo_cheque=datos_cheque.get('tipo_cheque', ''),
                        nombre_emisor=datos_cheque.get('nombre_emisor', ''),
                        cuit=datos_cheque.get('cuit', ''),
                        endoso=datos_cheque.get('endoso', ''),
                        monto=datos_cheque.get('monto', total_final),
                        estado="Pendiente"
                    )
                    session.add(nuevo_cheque)


                # REGLA: Toda venta genera un movimiento de caja (sea efectivo, tarjeta o cuenta corriente)
                caja_activa = session.scalars(select(Caja).where(Caja.estado == "Abierta")).first()
                if not caja_activa:
                    raise ValueError("No hay una caja abierta. Debe abrir la caja antes de procesar ventas.")

                concepto_caja = f"Venta #{nueva_venta.id} - {tipo_comprobante}"

                if desglose_pagos:
                    # Extraer metadata anidada si existe
                    datos_cheque_comb = desglose_pagos.pop('datos_cheque', datos_cheque)
                    datos_tarjeta_comb = desglose_pagos.pop('datos_tarjeta', None)

                    # PERSISTENCIA DEL CHEQUE FÍSICO EN COMBINADO (CRÍTICO)
                    if datos_cheque_comb:
                        from database.models.cheques import Cheque
                        nuevo_cheque_comb = Cheque(
                            venta_id=nueva_venta.id,
                            banco=datos_cheque_comb.get("banco", ""),
                            numero_cheque=datos_cheque_comb.get("numero_cheque", ""),
                            fecha_conformacion=datos_cheque_comb.get("fecha_conformacion"),
                            fecha_vencimiento=datos_cheque_comb.get("fecha_vencimiento"),
                            tipo_cheque=datos_cheque_comb.get("tipo_cheque", ""),
                            nombre_emisor=datos_cheque_comb.get("nombre_emisor", ""),
                            cuit=datos_cheque_comb.get("cuit", ""),
                            endoso=datos_cheque_comb.get("endoso", ""),
                            monto=datos_cheque_comb.get("monto", desglose_pagos.get("Cheque", 0.0)),
                            estado="Pendiente"
                        )
                        session.add(nuevo_cheque_comb)

                    for metodo, monto in desglose_pagos.items():
                        if isinstance(monto, (int, float)) and monto > 0:
                            concepto_extra = concepto_caja
                            metodo_final = "Tarjeta" if metodo == "Tarjeta de Crédito" else metodo

                            if metodo == "Cheque" and datos_cheque_comb:
                                concepto_extra += f" (Cheque {datos_cheque_comb.get('numero_cheque', '')})"

                            if metodo == "Tarjeta de Crédito":
                                metodo_final = "Tarjeta" # Normalizar para reportes
                                if datos_tarjeta_comb:
                                    concepto_extra += f" ({datos_tarjeta_comb.get('tarjeta', '')} - {datos_tarjeta_comb.get('plan', '')}) Lote: {datos_tarjeta_comb.get('lote', '')} Cupón: {datos_tarjeta_comb.get('cupon', '')}"

                            # Si es CC combinada, generar la deuda para esa parte
                            if metodo == "Cuenta Corriente":
                                if not cliente_id:
                                    raise ValueError("Debe especificar un cliente para cobrar con Cuenta Corriente.")
                                ultimo_mov = session.query(ClienteCuentaCorriente).filter_by(cliente_id=cliente_id).order_by(ClienteCuentaCorriente.id.desc()).first()
                                saldo_anterior = ultimo_mov.saldo if ultimo_mov else 0.0
                                nuevo_saldo = saldo_anterior + monto
                                mov_cc = ClienteCuentaCorriente(
                                    cliente_id=cliente_id, concepto=f"Venta #{nueva_venta.id} (Combinado)",
                                    debe=monto, haber=0.0, saldo=nuevo_saldo, venta_id=nueva_venta.id
                                )
                                session.add(mov_cc)

                            mov_caja = MovimientoCaja(
                                caja_id=caja_activa.id,
                                tipo="Ingreso",
                                concepto=concepto_extra,
                                monto=monto,
                                metodo=metodo_final,
                                venta_id=nueva_venta.id
                            )
                            session.add(mov_caja)
                else:
                    # Flujo estándar único
                    if metodo_pago == "Cheque" and datos_cheque:
                        concepto_caja += f" (Cheque {datos_cheque.get('numero_cheque', '')})"

                    mov_caja = MovimientoCaja(
                        caja_id=caja_activa.id,
                        tipo="Ingreso",
                        concepto=concepto_caja,
                        monto=total_final,
                        metodo=metodo_pago,
                        venta_id=nueva_venta.id
                    )
                    session.add(mov_caja)
                # -----------------------------------------------

                # Cerrar Presupuesto si se originó de uno
                if presupuesto_id:
                    from database.models.presupuestos import Presupuesto
                    pres = session.get(Presupuesto, presupuesto_id)
                    if pres:
                        pres.estado = "Cerrado"

                session.commit()
                session.refresh(nueva_venta)
                session.expunge(nueva_venta)
                return nueva_venta

            except Exception as e:
                session.rollback()
                raise e

    @staticmethod
    def anular_venta(venta_id: int):
        with get_session() as session:
            try:
                venta = session.get(Venta, venta_id)
                if not venta:
                    raise ValueError(f"Venta ID {venta_id} no encontrada.")
                if venta.estado == "Anulado":
                    raise ValueError("Esta venta ya se encuentra anulada.")

                # 1. Devolver Stock (solo items de catalogo)
                for detalle in venta.detalles:
                    if detalle.producto_id:
                        prod = session.get(Producto, detalle.producto_id)
                        if prod:
                            aumento_stock = detalle.cantidad
                            if prod.es_granel and prod.divisor_granel > 0:
                                aumento_stock = detalle.cantidad / prod.divisor_granel
                            prod.stock_actual += aumento_stock

                # 2. Revertir Finanzas
                if venta.metodo_pago == "Efectivo":
                    caja_activa = session.scalars(select(Caja).where(Caja.estado == "Abierta")).first()
                    if caja_activa:
                        mov = MovimientoCaja(
                            caja_id=caja_activa.id,
                            tipo="Egreso",
                            concepto=f"Anulación Venta #{venta.id}",
                            monto=venta.total,
                            metodo="Efectivo"
                        )
                        session.add(mov)
                elif venta.metodo_pago == "Cuenta Corriente" and venta.cliente_id:
                    ultimo_mov = session.query(ClienteCuentaCorriente)\
                        .filter_by(cliente_id=venta.cliente_id)\
                        .order_by(ClienteCuentaCorriente.id.desc()).first()
                    saldo_ant = ultimo_mov.saldo if ultimo_mov else 0.0
                    mov_cc = ClienteCuentaCorriente(
                        cliente_id=venta.cliente_id,
                        concepto=f"Anulación Venta #{venta.id}",
                        debe=0.0,
                        haber=venta.total,
                        saldo=saldo_ant - venta.total
                    )
                    session.add(mov_cc)
                # (Para tarjetas, dependeria del procesador. El sistema local marca la venta como anulada nomas y no acredita el diferido si controlamos eso. Por ahora cancelamos fiscalmente y marcamos.)
                from database.models.contabilidad import IngresoDiferido
                if venta.metodo_pago in ["Tarjeta", "Débito"]:
                    difs = session.scalars(select(IngresoDiferido).where(IngresoDiferido.venta_id == venta.id)).all()
                    for d in difs:
                        d.estado = "Anulado"

                # 3. Impuestos (Revertir Débito Fiscal)
                if venta.tipo_comprobante.startswith("Factura"):
                    # El usuario pide explícitamente: "ejecuta session.delete(registro_iva) para eliminar ese asiento fiscal antes de hacer el session.commit()"
                    ivas = session.scalars(select(LibroIVA).where(LibroIVA.venta_id == venta.id)).all()
                    for iva in ivas:
                        session.delete(iva)

                venta.estado = "Anulado"
                session.commit()
            except Exception as e:
                session.rollback()
                raise e
