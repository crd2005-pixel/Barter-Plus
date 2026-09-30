import re

with open("ui/views/dashboard_view.py", "r") as f:
    content = f.read()

# Replace the specific block creating the cards
old_cards_block = """        self.card_liquidez_frame, self.lbl_liquidez = self._crear_tarjeta_kpi("Liquidez Neta", "#2ecc71")
        self.card_deuda_prov_frame, self.lbl_deuda_prov = self._crear_tarjeta_kpi("Deuda a Proveedores", "#e74c3c")
        self.card_inventario_frame, self.lbl_inventario = self._crear_tarjeta_kpi("Valor del Inventario", "#9b59b6")
        self.card_ventas_frame, self.lbl_ventas = self._crear_tarjeta_kpi("Ventas del Mes", "#3498db")
        self.card_ticket_prom_frame, self.lbl_ticket_prom = self._crear_tarjeta_kpi("Ticket Promedio", "#1abc9c")
        self.card_cobrar_frame, self.lbl_cobrar = self._crear_tarjeta_kpi("Cuentas a Cobrar", "#f1c40f")

        # Reordenamos a un layout más amigable (3x3 o 2 filas extensas)
        grid_kpi.addWidget(self.card_liquidez_frame, 0, 0)
        grid_kpi.addWidget(self.card_deuda_prov_frame, 0, 1)
        grid_kpi.addWidget(self.card_cobrar_frame, 0, 2)
        grid_kpi.addWidget(self.card_inventario_frame, 0, 3)

        self.card_utilidad_frame, self.lbl_utilidad = self._crear_tarjeta_kpi("Utilidad Bruta Est.", "#f39c12")
        grid_kpi.addWidget(self.card_ventas_frame, 1, 0)
        grid_kpi.addWidget(self.card_utilidad_frame, 1, 1)
        grid_kpi.addWidget(self.card_ticket_prom_frame, 1, 2)

        self.card_descuentos_frame, self.lbl_descuentos = self._crear_tarjeta_kpi("Fuga por Descuentos", "#e67e22")
        self.card_gastos_frame, self.lbl_gastos = self._crear_tarjeta_kpi("Incidencia Operativa (Gastos)", "#e74c3c")

        grid_kpi.addWidget(self.card_descuentos_frame, 1, 3)
        grid_kpi.addWidget(self.card_gastos_frame, 1, 4)"""


new_cards_block = """        self.card_liquidez_frame, self.lbl_liquidez = self._crear_tarjeta_kpi("Liquidez Neta", "#2ecc71")
        self.card_deuda_prov_frame, self.lbl_deuda_prov = self._crear_tarjeta_kpi("Deuda a Proveedores", "#e74c3c")
        self.card_cobrar_frame, self.lbl_cobrar = self._crear_tarjeta_kpi("Cuentas a Cobrar", "#f1c40f")

        # Nuevos de Inventario
        self.card_inventario_costo, self.lbl_inventario_costo = self._crear_tarjeta_kpi("Cap. Inmov. (Costo)", "#e67e22")
        self.card_inventario_venta, self.lbl_inventario_venta = self._crear_tarjeta_kpi("Valor Potencial (Venta)", "#2980b9")
        self.card_inventario_ganancia, self.lbl_inventario_ganancia = self._crear_tarjeta_kpi("Ganancia Latente", "#8e44ad")

        self.card_ventas_frame, self.lbl_ventas = self._crear_tarjeta_kpi("Ventas del Mes", "#3498db")
        self.card_ticket_prom_frame, self.lbl_ticket_prom = self._crear_tarjeta_kpi("Ticket Promedio", "#1abc9c")
        self.card_utilidad_frame, self.lbl_utilidad = self._crear_tarjeta_kpi("Utilidad Bruta Est.", "#f39c12")
        self.card_descuentos_frame, self.lbl_descuentos = self._crear_tarjeta_kpi("Fuga por Descuentos", "#e67e22")
        self.card_gastos_frame, self.lbl_gastos = self._crear_tarjeta_kpi("Incidencia Op. (Gastos)", "#e74c3c")

        # Fila 0
        grid_kpi.addWidget(self.card_liquidez_frame, 0, 0)
        grid_kpi.addWidget(self.card_deuda_prov_frame, 0, 1)
        grid_kpi.addWidget(self.card_cobrar_frame, 0, 2)
        grid_kpi.addWidget(self.card_inventario_costo, 0, 3)

        # Fila 1
        grid_kpi.addWidget(self.card_inventario_venta, 1, 0)
        grid_kpi.addWidget(self.card_inventario_ganancia, 1, 1)
        grid_kpi.addWidget(self.card_ventas_frame, 1, 2)
        grid_kpi.addWidget(self.card_utilidad_frame, 1, 3)

        # Fila 2
        grid_kpi.addWidget(self.card_ticket_prom_frame, 2, 0)
        grid_kpi.addWidget(self.card_descuentos_frame, 2, 1)
        grid_kpi.addWidget(self.card_gastos_frame, 2, 2)"""

content = content.replace(old_cards_block, new_cards_block)

with open("ui/views/dashboard_view.py", "w") as f:
    f.write(content)
