import re

with open('services/venta_service.py', 'r') as f:
    content = f.read()

repl_transfer = """                    session.add(ingreso_dif)
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
                else:"""

content = re.sub(
    r'                    session\.add\(ingreso_dif\)\n                else:',
    repl_transfer,
    content
)

with open('services/venta_service.py', 'w') as f:
    f.write(content)

print("done")
