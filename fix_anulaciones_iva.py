import re
with open('services/venta_service.py', 'r') as f:
    c = f.read()

repl_anular = """                # 3. Impuestos (Revertir Débito Fiscal)
                if venta.tipo_comprobante.startswith("Factura"):
                    # El usuario pide explícitamente: "ejecuta session.delete(registro_iva) para eliminar ese asiento fiscal antes de hacer el session.commit()"
                    ivas = session.scalars(select(LibroIVA).where(LibroIVA.venta_id == venta.id)).all()
                    for iva in ivas:
                        session.delete(iva)

                venta.estado = "Anulado"
                session.commit()"""

c = re.sub(
    r'                # 3\. Impuestos \(Revertir Débito Fiscal\)\n                if venta\.tipo_comprobante\.startswith\("Factura"\):\n                    # Asentar en negativo o marcar anulado en Libro IVA\n                    ivas = session\.scalars\(select\(LibroIVA\)\.where\(LibroIVA\.venta_id == venta\.id\)\)\.all\(\)\n                    for iva in ivas:\n                        # Generamos contracomprobante\n                        contra = LibroIVA\(\n                            fecha=dt\.datetime\.utcnow\(\),\n                            tipo="Venta \(Anulación\)",\n                            comprobante=f"ANULACIÓN \{iva\.comprobante\}",\n                            neto_gravado=-iva\.neto_gravado,\n                            iva_21=-iva\.iva_21,\n                            total=-iva\.total,\n                            venta_id=venta\.id\n                        \)\n                        session\.add\(contra\)\n\n                venta\.estado = "Anulado"\n                session\.commit\(\)',
    repl_anular,
    c
)

with open('services/venta_service.py', 'w') as f:
    f.write(c)

with open('ui/views/registros_view.py', 'r') as f:
    c2 = f.read()

repl_calc = """        # Cargar Libro IVA y calcular totales
        registros_iva = RegistrosService.obtener_libro_iva(d_desde, d_hasta)
        self.tbl_iva.setRowCount(len(registros_iva))

        total_debito = 0.0
        total_credito = 0.0

        for row, r in enumerate(registros_iva):
            self.tbl_iva.setItem(row, 0, QTableWidgetItem(r.fecha.strftime("%Y-%m-%d")))
            self.tbl_iva.setItem(row, 1, QTableWidgetItem(r.tipo))
            self.tbl_iva.setItem(row, 2, QTableWidgetItem(r.comprobante))
            self.tbl_iva.setItem(row, 3, QTableWidgetItem(f"${r.neto_gravado:.2f}"))
            self.tbl_iva.setItem(row, 4, QTableWidgetItem(f"${r.iva_21:.2f}"))
            self.tbl_iva.setItem(row, 5, QTableWidgetItem(f"${r.total:.2f}"))

            if r.tipo == "Venta":
                total_debito += r.iva_21
            elif r.tipo == "Compra":
                total_credito += r.iva_21

        saldo = total_debito - total_credito

        if hasattr(self, 'lbl_iva_ventas'):
            self.lbl_iva_ventas.setText(f"Total IVA Débito (Ventas): ${total_debito:.2f}")
            self.lbl_iva_compras.setText(f"Total IVA Crédito (Compras): ${total_credito:.2f}")
            self.lbl_iva_saldo.setText(f"Saldo IVA: ${saldo:.2f}")
            if saldo > 0:
                self.lbl_iva_saldo.setStyleSheet("font-size: 18px; font-weight: bold; color: #c0392b; background: #fadbd8; padding: 10px; border-radius: 5px;")
            else:
                self.lbl_iva_saldo.setStyleSheet("font-size: 18px; font-weight: bold; color: #27ae60; background: #d5f5e3; padding: 10px; border-radius: 5px;")"""

c2 = re.sub(
    r'        # Cargar Libro IVA\n        registros_iva = RegistrosService\.obtener_libro_iva\(d_desde, d_hasta\)\n        self\.tbl_iva\.setRowCount\(len\(registros_iva\)\)\n        for row, r in enumerate\(registros_iva\):\n            self\.tbl_iva\.setItem\(row, 0, QTableWidgetItem\(r\.fecha\.strftime\("%Y-%m-%d"\)\)\)\n            self\.tbl_iva\.setItem\(row, 1, QTableWidgetItem\(r\.tipo\)\)\n            self\.tbl_iva\.setItem\(row, 2, QTableWidgetItem\(r\.comprobante\)\)\n            self\.tbl_iva\.setItem\(row, 3, QTableWidgetItem\(f"\$\{r\.neto_gravado:\.2f\}"\)\)\n            self\.tbl_iva\.setItem\(row, 4, QTableWidgetItem\(f"\$\{r\.iva_21:\.2f\}"\)\)\n            self\.tbl_iva\.setItem\(row, 5, QTableWidgetItem\(f"\$\{r\.total:\.2f\}"\)\)\n            \n            if r\.tipo == "Venta":\n                total_debito \+= r\.iva_21\n            elif r\.tipo == "Compra":\n                total_credito \+= r\.iva_21\n                \n        saldo = total_debito - total_credito\n        self\.lbl_iva_ventas\.setText\(f"Total IVA Débito \(Ventas\): \$\{total_debito:\.2f\}"\)\n        self\.lbl_iva_compras\.setText\(f"Total IVA Crédito \(Compras\): \$\{total_credito:\.2f\}"\)\n        self\.lbl_iva_saldo\.setText\(f"Saldo IVA: \$\{saldo:\.2f\}"\)\n        if saldo > 0:\n            self\.lbl_iva_saldo\.setStyleSheet\("font-size: 18px; font-weight: bold; color: #c0392b; background: #fadbd8; padding: 10px; border-radius: 5px;"\)\n        else:\n            self\.lbl_iva_saldo\.setStyleSheet\("font-size: 18px; font-weight: bold; color: #27ae60; background: #d5f5e3; padding: 10px; border-radius: 5px;"\)',
    repl_calc,
    c2
)

with open('ui/views/registros_view.py', 'w') as f:
    f.write(c2)
