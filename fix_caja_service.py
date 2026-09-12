import re
with open('services/caja_service.py', 'r') as f:
    content = f.read()

repl_caja = """    @staticmethod
    def registrar_movimiento(caja_id: int, tipo: str, concepto: str, monto: float, metodo: str, venta_id: Optional[int] = None) -> MovimientoCaja:
        with get_session() as session:
            try:
                # If Transferencia, we also need to create a journal entry so it reflects in liquidity
                if metodo == "Transferencia":
                    from database.models.contabilidad import AsientoDiario
                    import datetime as dt
                    asiento_banco = AsientoDiario(
                        fecha=dt.datetime.utcnow(),
                        cuenta="Cuenta Bancaria",
                        debe=monto if tipo == "Ingreso" else 0.0,
                        haber=monto if tipo == "Egreso" else 0.0,
                        descripcion=concepto,
                        venta_id=venta_id
                    )
                    session.add(asiento_banco)

                mov = MovimientoCaja(
                    caja_id=caja_id,
                    tipo=tipo,
                    concepto=concepto,
                    monto=monto,
                    metodo=metodo,
                    venta_id=venta_id
                )
                session.add(mov)"""

content = re.sub(
    r'    @staticmethod\n    def registrar_movimiento.*?session\.add\(mov\)',
    repl_caja,
    content,
    flags=re.DOTALL
)

with open('services/caja_service.py', 'w') as f:
    f.write(content)
