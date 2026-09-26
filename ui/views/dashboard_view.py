from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QScrollArea, QTextBrowser
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from services.dashboard_service import DashboardService

class DashboardView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.cargar_datos()

    def _crear_tarjeta_kpi(self, titulo: str, color_valor: str) -> tuple[QFrame, QLabel]:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #2c3e50;
                border-radius: 8px;
                padding: 8px;
                min-height: 80px;
            }
        """)
        lay = QVBoxLayout(frame)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet("color: #bdc3c7; font-size: 12px;")
        lbl_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_valor = QLabel("$ 0.00")
        lbl_valor.setStyleSheet(f"color: {color_valor}; font-size: 24px; font-weight: bold;")
        lbl_valor.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lay.addWidget(lbl_titulo)
        lay.addWidget(lbl_valor)

        return frame, lbl_valor

    def setup_ui(self):
        layout = QVBoxLayout()

        # Header con botón actualizar
        header_lay = QHBoxLayout()
        lbl_header = QLabel("Dashboard Gerencial")
        lbl_header.setStyleSheet("font-size: 24px; font-weight: bold;")

        btn_actualizar = QPushButton("Actualizar Datos")
        btn_actualizar.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; padding: 8px;")
        btn_actualizar.clicked.connect(self.cargar_datos)

        header_lay.addWidget(lbl_header)
        header_lay.addStretch()
        header_lay.addWidget(btn_actualizar)
        layout.addLayout(header_lay)

        # Tarjetas KPI (Grid)
        grid_kpi = QGridLayout()

        self.card_liquidez_frame, self.lbl_liquidez = self._crear_tarjeta_kpi("Liquidez Neta", "#2ecc71")
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
        grid_kpi.addWidget(self.card_gastos_frame, 1, 4)

        layout.addLayout(grid_kpi)

        # Tablas de Análisis Inferiores (Grid 2x2)
        grid_tablas = QGridLayout()

        # Tabla 1: Top 10 Mayor Rotación
        frame_1 = QFrame()
        lay_1 = QVBoxLayout(frame_1)
        lbl_1 = QLabel("Top 10 Mayor Rotación (Mes)")
        lbl_1.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.tbl_top_rotacion = QTableWidget(0, 3)
        self.tbl_top_rotacion.setHorizontalHeaderLabels(["Código", "Producto", "Cant. Vendida"])
        self.tbl_top_rotacion.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_top_rotacion.setColumnWidth(0, 100)
        self.tbl_top_rotacion.setColumnWidth(2, 100)
        self.tbl_top_rotacion.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_top_rotacion.setAlternatingRowColors(True)
        lay_1.addWidget(lbl_1)
        lay_1.addWidget(self.tbl_top_rotacion)

        # Tabla 2: Top 10 Capital Estancado
        frame_2 = QFrame()
        lay_2 = QVBoxLayout(frame_2)
        lbl_2 = QLabel("Top 10 Capital Estancado")
        lbl_2.setStyleSheet("font-weight: bold; font-size: 14px; color: #e67e22;")
        self.tbl_peores = QTableWidget(0, 4)
        self.tbl_peores.setHorizontalHeaderLabels(["Código", "Producto", "Stock Actual", "Cant. Vendida"])
        self.tbl_peores.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_peores.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_peores.setColumnWidth(0, 100)
        self.tbl_peores.setColumnWidth(2, 80)
        self.tbl_peores.setColumnWidth(3, 80)
        self.tbl_peores.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_peores.setAlternatingRowColors(True)
        lay_2.addWidget(lbl_2)
        lay_2.addWidget(self.tbl_peores)

        # Tabla 3: Ranking de Deudores
        frame_3 = QFrame()
        lay_3 = QVBoxLayout(frame_3)
        lbl_3 = QLabel("Ranking de Deudores")
        lbl_3.setStyleSheet("font-weight: bold; font-size: 14px; color: #c0392b;")
        self.tbl_deudores = QTableWidget(0, 3)
        self.tbl_deudores.setHorizontalHeaderLabels(["Cliente", "Teléfono", "Saldo Deudor"])
        self.tbl_deudores.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_deudores.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_deudores.setAlternatingRowColors(True)
        lay_3.addWidget(lbl_3)
        lay_3.addWidget(self.tbl_deudores)

        # Tabla 4: Alerta de Quiebre de Stock
        frame_4 = QFrame()
        lay_4 = QVBoxLayout(frame_4)
        lbl_4 = QLabel("Alerta de Quiebre de Stock")
        lbl_4.setStyleSheet("font-weight: bold; font-size: 14px; color: #e74c3c;")
        self.tbl_alertas_stock = QTableWidget(0, 3)
        self.tbl_alertas_stock.setHorizontalHeaderLabels(["Producto", "Stock Actual", "Stock Mínimo"])
        self.tbl_alertas_stock.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_alertas_stock.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_alertas_stock.setAlternatingRowColors(True)
        lay_4.addWidget(lbl_4)
        lay_4.addWidget(self.tbl_alertas_stock)

        grid_tablas.addWidget(frame_1, 0, 0)
        grid_tablas.addWidget(frame_2, 0, 1)
        grid_tablas.addWidget(frame_3, 1, 0)
        grid_tablas.addWidget(frame_4, 1, 1)


        # Panel Principal Contenedor
        main_h_lay = QHBoxLayout()
        main_h_lay.addLayout(grid_tablas, stretch=4)

        # Columna de Noticias
        frame_news = QFrame()
        lay_news = QVBoxLayout(frame_news)
        lbl_news = QLabel("Contexto Económico y Sectorial")
        lbl_news.setStyleSheet("font-weight: bold; font-size: 16px; color: #2980b9;")

        self.txt_news = QTextBrowser()
        self.txt_news.setOpenExternalLinks(True)
        self.txt_news.setStyleSheet("background-color: transparent; color: white; font-size: 13px; border: 1px solid #444;")

        lay_news.addWidget(lbl_news)
        lay_news.addWidget(self.txt_news)

        main_h_lay.addWidget(frame_news, stretch=1)

        layout.addLayout(main_h_lay)

        # Configurar Scroll Area principal
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        container_widget = QWidget()
        container_widget.setLayout(layout)
        scroll_area.setWidget(container_widget)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll_area)

        self._cargar_noticias()

    def cargar_datos(self):
        # 1. Cargar KPIs
        liquidez = DashboardService.obtener_liquidez_neta()
        deuda_prov = DashboardService.obtener_deuda_proveedores()
        valor_inventario = DashboardService.obtener_valor_inventario()
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
        self.lbl_utilidad.setText(f"$ {utilidad_bruta:,.2f}")

        # Nuevos KPIs Fugas/Gastos
        desc_data = DashboardService.obtener_analisis_descuentos()
        gastos_data = DashboardService.obtener_incidencia_gastos()

        texto_desc = f"$ {desc_data['total_dinero_descontado']:,.2f}\n({desc_data['cantidad_operaciones']} ops | {desc_data['porcentaje_sobre_ventas']:.1f}%)"
        self.lbl_descuentos.setText(texto_desc)
        self.lbl_descuentos.setStyleSheet("color: #e67e22; font-size: 18px; font-weight: bold;")

        texto_gasto = f"$ {gastos_data['total_gastos']:,.2f}\n({gastos_data['incidencia_operativa']:.1f}% vs Ventas)"
        self.lbl_gastos.setText(texto_gasto)
        self.lbl_gastos.setStyleSheet("color: #e74c3c; font-size: 18px; font-weight: bold;")

        # 2. Cargar Tabla 1: Top Rotacion
        top_productos = DashboardService.obtener_top_productos_mes()
        self.tbl_top_rotacion.setRowCount(len(top_productos))
        for row, prod in enumerate(top_productos):
            self.tbl_top_rotacion.setItem(row, 0, QTableWidgetItem(prod["codigo"]))
            self.tbl_top_rotacion.setItem(row, 1, QTableWidgetItem(prod["producto"]))
            item_cant = QTableWidgetItem(f"{prod['cantidad']:.2f}")
            item_cant.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_top_rotacion.setItem(row, 2, item_cant)

        # 3. Cargar Tabla 2: Peores Productos
        peores = DashboardService.obtener_peores_productos()
        self.tbl_peores.setRowCount(len(peores))
        for row, p in enumerate(peores):
            self.tbl_peores.setItem(row, 0, QTableWidgetItem(p["codigo"]))
            self.tbl_peores.setItem(row, 1, QTableWidgetItem(p["producto"]))
            item_stk = QTableWidgetItem(f"{p['stock']:.2f}")
            item_stk.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_peores.setItem(row, 2, item_stk)
            item_vnd = QTableWidgetItem(f"{p['vendido']:.2f}")
            item_vnd.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_peores.setItem(row, 3, item_vnd)

        # 4. Cargar Tabla 3: Deudores
        deudores = DashboardService.obtener_ranking_deudores()
        self.tbl_deudores.setRowCount(len(deudores))
        for row, d in enumerate(deudores):
            self.tbl_deudores.setItem(row, 0, QTableWidgetItem(d["cliente"]))
            self.tbl_deudores.setItem(row, 1, QTableWidgetItem(d["telefono"]))
            item_saldo = QTableWidgetItem(f"$ {d['saldo']:,.2f}")
            item_saldo.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tbl_deudores.setItem(row, 2, item_saldo)

        # 5. Cargar Tabla 4: Alertas de Stock
        alertas = DashboardService.obtener_alertas_stock()
        self.tbl_alertas_stock.setRowCount(len(alertas))
        for row, alerta in enumerate(alertas):
            self.tbl_alertas_stock.setItem(row, 0, QTableWidgetItem(alerta["producto"]))

            item_act = QTableWidgetItem(f"{alerta['stock_actual']:.2f}")
            item_act.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if alerta['stock_actual'] <= 0:
                item_act.setForeground(QColor("#e74c3c"))
            self.tbl_alertas_stock.setItem(row, 1, item_act)

            item_min = QTableWidgetItem(f"{alerta['stock_minimo']:.2f}")
            item_min.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_alertas_stock.setItem(row, 2, item_min)

    def _cargar_noticias(self):
        import threading
        def fetch():
            import urllib.request
            import xml.etree.ElementTree as ET

            html = ""
            try:
                # Usamos Ambito Financiero Economía
                req = urllib.request.Request('https://www.ambito.com/rss/economia.xml', headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    xml_data = response.read()

                root = ET.fromstring(xml_data)
                items = root.findall('.//item')[:5]

                for item in items:
                    title = item.find('title').text if item.find('title') is not None else 'Sin título'
                    link = item.find('link').text if item.find('link') is not None else '#'
                    pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ''

                    html += f"<h3><a href='{link}' style='color: #2980b9; text-decoration: none;'>{title}</a></h3>"
                    html += f"<p style='color: #7f8c8d; font-size: 11px; margin-top: -10px;'>{pub_date}</p><hr>"
            except Exception as e:
                html = f"<p style='color: red;'>Sin conexión para noticias.<br>({str(e)})</p>"

            # Actualizar GUI de forma segura (aunque en PyQt estricto deberia ser por señales, QTextBrowser tolera setText si no hay mucha concurrencia, pero lo haremos con un QTimer para ser pulcros)
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.txt_news.setHtml(html))

        threading.Thread(target=fetch, daemon=True).start()
