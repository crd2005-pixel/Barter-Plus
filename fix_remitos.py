import re
with open('services/venta_service.py', 'r') as f:
    c = f.read()

repl_caja = """                elif metodo_pago == "Transferencia":
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
                    session.add(mov_caja)"""

c = re.sub(
    r'                elif metodo_pago == "Transferencia":\n                    # Registramos la transferencia bancaria \(no entra en la caja física\)\n                    asiento_banco = AsientoDiario\(\n                        fecha=nueva_venta\.fecha,\n                        cuenta="Cuenta Bancaria",\n                        debe=total_final,\n                        haber=0\.0,\n                        descripcion=f"Venta Transferencia #\{nueva_venta\.id\}",\n                        venta_id=nueva_venta\.id\n                    \)\n                    session\.add\(asiento_banco\)\n                else:\n                    caja_activa = session\.scalars\(select\(Caja\)\.where\(Caja\.estado == "Abierta"\)\)\.first\(\)\n                    if not caja_activa:\n                        raise ValueError\("No hay una caja abierta\. Debe abrir la caja antes de procesar ventas\."\)\n                    \n                    mov_caja = MovimientoCaja\(\n                        caja_id=caja_activa\.id,\n                        tipo="Ingreso",\n                        concepto=f"Venta #\{nueva_venta\.id\} - \{tipo_comprobante\}",\n                        monto=total_final,\n                        metodo=metodo_pago,\n                        venta_id=nueva_venta\.id\n                    \)\n                    session\.add\(mov_caja\)',
    repl_caja,
    c
)

with open('services/venta_service.py', 'w') as f:
    f.write(c)
