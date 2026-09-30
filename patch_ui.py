import re

with open("ui/views/dashboard_view.py", "r") as f:
    content = f.read()

# Update UI to reflect the two inventory values and latent profit
# We will create two labels for inventory: capital invertido and valor venta publico, and one for ganancia bruta latente.

# First, modify the structure in __init__ where lbl_inventario is created
old_init_block = """        # Segunda Fila
        row2_layout = QHBoxLayout()
        self.lbl_inventario = self._crear_tarjeta_kpi(row2_layout, "Valor Inventario (Costo)", "$ 0.00", "#e67e22")
        self.lbl_ventas = self._crear_tarjeta_kpi(row2_layout, "Ventas del Mes", "$ 0.00", "#2ecc71")
        self.lbl_utilidad = self._crear_tarjeta_kpi(row2_layout, "Utilidad Bruta Mes", "$ 0.00", "#f1c40f")
        kpi_layout.addLayout(row2_layout)"""

new_init_block = """        # Segunda Fila
        row2_layout = QHBoxLayout()
        self.lbl_inventario_costo = self._crear_tarjeta_kpi(row2_layout, "Capital Inmovilizado (Costo)", "$ 0.00", "#e67e22")
        self.lbl_inventario_venta = self._crear_tarjeta_kpi(row2_layout, "Valor Potencial (Venta)", "$ 0.00", "#2980b9")
        self.lbl_inventario_ganancia = self._crear_tarjeta_kpi(row2_layout, "Ganancia Bruta Latente", "$ 0.00", "#8e44ad")
        kpi_layout.addLayout(row2_layout)

        # Tercera Fila (movida de la segunda)
        row3_layout = QHBoxLayout()
        self.lbl_ventas = self._crear_tarjeta_kpi(row3_layout, "Ventas del Mes", "$ 0.00", "#2ecc71")
        self.lbl_utilidad = self._crear_tarjeta_kpi(row3_layout, "Utilidad Bruta Mes", "$ 0.00", "#f1c40f")
        kpi_layout.addLayout(row3_layout)"""

content = content.replace(old_init_block, new_init_block)


# Now update cargar_datos
old_cargar_block = """        valor_inventario = DashboardService.obtener_valor_inventario()
        ventas_mes = DashboardService.obtener_ventas_del_mes()
        ticket_prom = DashboardService.obtener_ticket_promedio()
        cuentas_cobrar = DashboardService.obtener_cuentas_a_cobrar()
        utilidad_bruta = DashboardService.obtener_utilidad_bruta_mes()

        self.lbl_liquidez.setText(f"$ {liquidez:,.2f}")
        self.lbl_liquidez.setStyleSheet(f"color: {'#2ecc71' if liquidez >= 0 else '#e74c3c'}; font-size: 24px; font-weight: bold;")

        self.lbl_deuda_prov.setText(f"$ {deuda_prov:,.2f}")

        self.lbl_inventario.setText(f"$ {valor_inventario:,.2f}")
        self.lbl_ventas.setText(f"$ {ventas_mes:,.2f}")
        self.lbl_ticket_prom.setText(f"$ {ticket_prom:,.2f}")
        self.lbl_cobrar.setText(f"$ {cuentas_cobrar:,.2f}")
        self.lbl_utilidad.setText(f"$ {utilidad_bruta:,.2f}")"""

new_cargar_block = """        valores_inventario = DashboardService.obtener_valor_inventario()
        ventas_mes = DashboardService.obtener_ventas_del_mes()
        ticket_prom = DashboardService.obtener_ticket_promedio()
        cuentas_cobrar = DashboardService.obtener_cuentas_a_cobrar()
        utilidad_bruta = DashboardService.obtener_utilidad_bruta_mes()

        self.lbl_liquidez.setText(f"$ {liquidez:,.2f}")
        self.lbl_liquidez.setStyleSheet(f"color: {'#2ecc71' if liquidez >= 0 else '#e74c3c'}; font-size: 24px; font-weight: bold;")

        self.lbl_deuda_prov.setText(f"$ {deuda_prov:,.2f}")

        cap_inv = valores_inventario["capital_invertido"]
        val_ven = valores_inventario["valor_venta_publico"]
        ganancia_latente = val_ven - cap_inv

        self.lbl_inventario_costo.setText(f"$ {cap_inv:,.2f}")
        self.lbl_inventario_venta.setText(f"$ {val_ven:,.2f}")
        self.lbl_inventario_ganancia.setText(f"$ {ganancia_latente:,.2f}")

        self.lbl_ventas.setText(f"$ {ventas_mes:,.2f}")
        self.lbl_ticket_prom.setText(f"$ {ticket_prom:,.2f}")
        self.lbl_cobrar.setText(f"$ {cuentas_cobrar:,.2f}")
        self.lbl_utilidad.setText(f"$ {utilidad_bruta:,.2f}")"""

# Need to escape curly braces in regex or just use replace, replacing exact blocks
content = content.replace(old_cargar_block, new_cargar_block)

with open("ui/views/dashboard_view.py", "w") as f:
    f.write(content)
