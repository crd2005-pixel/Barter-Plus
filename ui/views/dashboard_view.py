from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton
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
                padding: 15px;
            }
        """)
        lay = QVBoxLayout(frame)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet("color: #bdc3c7; font-size: 14px; font-weight: bold;")
        lbl_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_valor = QLabel("$ 0.00")
        lbl_valor.setStyleSheet(f"color: {color_valor}; font-size: 24px; font-weight: bold;")
        lbl_valor.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lay.addWidget(lbl_titulo)
        lay.addWidget(lbl_valor)

        return frame, lbl_valor

    def setup_ui(self):
        layout = QVBoxLayout(self)

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
        self.card_ventas_frame, self.lbl_ventas = self._crear_tarjeta_kpi("Ventas del Mes", "#3498db")
        self.card_cobrar_frame, self.lbl_cobrar = self._crear_tarjeta_kpi("Cuentas a Cobrar", "#f1c40f")
        self.card_inventario_frame, self.lbl_inventario = self._crear_tarjeta_kpi("Valor del Inventario", "#9b59b6")

        grid_kpi.addWidget(self.card_liquidez_frame, 0, 0)
        grid_kpi.addWidget(self.card_ventas_frame, 0, 1)
        grid_kpi.addWidget(self.card_cobrar_frame, 0, 2)
        grid_kpi.addWidget(self.card_inventario_frame, 0, 3)

        layout.addLayout(grid_kpi)

        # Tablas de Análisis Inferiores
        lay_tablas = QHBoxLayout()

        # Tabla A: Top 10 Productos
        frame_a = QFrame()
        lay_a = QVBoxLayout(frame_a)
        lbl_a = QLabel("Top 10 Productos Más Vendidos (Mes)")
        lbl_a.setStyleSheet("font-weight: bold; font-size: 16px;")

        self.tbl_top_productos = QTableWidget(0, 4)
        self.tbl_top_productos.setHorizontalHeaderLabels(["Código", "Producto", "Cant. Vendida", "Ingreso Generado"])
        self.tbl_top_productos.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_top_productos.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_top_productos.setAlternatingRowColors(True)

        lay_a.addWidget(lbl_a)
        lay_a.addWidget(self.tbl_top_productos)

        # Tabla B: Alertas de Stock
        frame_b = QFrame()
        lay_b = QVBoxLayout(frame_b)
        lbl_b = QLabel("Alertas de Stock y Vencimientos")
        lbl_b.setStyleSheet("font-weight: bold; font-size: 16px; color: #e74c3c;")

        self.tbl_alertas_stock = QTableWidget(0, 3)
        self.tbl_alertas_stock.setHorizontalHeaderLabels(["Producto", "Stock Actual", "Stock Mínimo"])
        self.tbl_alertas_stock.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_alertas_stock.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_alertas_stock.setAlternatingRowColors(True)

        lay_b.addWidget(lbl_b)
        lay_b.addWidget(self.tbl_alertas_stock)

        lay_tablas.addWidget(frame_a)
        lay_tablas.addWidget(frame_b)

        layout.addLayout(lay_tablas)

    def cargar_datos(self):
        # 1. Cargar KPIs
        liquidez = DashboardService.obtener_liquidez_neta()
        ventas_mes = DashboardService.obtener_ventas_del_mes()
        cuentas_cobrar = DashboardService.obtener_cuentas_a_cobrar()
        valor_inventario = DashboardService.obtener_valor_inventario()

        self.lbl_liquidez.setText(f"$ {liquidez:,.2f}")
        self.lbl_liquidez.setStyleSheet(f"color: {'#2ecc71' if liquidez >= 0 else '#e74c3c'}; font-size: 24px; font-weight: bold;")

        self.lbl_ventas.setText(f"$ {ventas_mes:,.2f}")
        self.lbl_cobrar.setText(f"$ {cuentas_cobrar:,.2f}")
        self.lbl_inventario.setText(f"$ {valor_inventario:,.2f}")

        # 2. Cargar Tabla Top Productos
        top_productos = DashboardService.obtener_top_productos_mes()
        self.tbl_top_productos.setRowCount(len(top_productos))
        for row, prod in enumerate(top_productos):
            self.tbl_top_productos.setItem(row, 0, QTableWidgetItem(prod["codigo"]))
            self.tbl_top_productos.setItem(row, 1, QTableWidgetItem(prod["producto"]))

            item_cant = QTableWidgetItem(f"{prod['cantidad']:.2f}")
            item_cant.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_top_productos.setItem(row, 2, item_cant)

            item_ing = QTableWidgetItem(f"$ {prod['ingreso']:,.2f}")
            item_ing.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tbl_top_productos.setItem(row, 3, item_ing)

        # 3. Cargar Alertas de Stock
        alertas = DashboardService.obtener_alertas_stock()
        self.tbl_alertas_stock.setRowCount(len(alertas))
        for row, alerta in enumerate(alertas):
            self.tbl_alertas_stock.setItem(row, 0, QTableWidgetItem(alerta["producto"]))

            item_act = QTableWidgetItem(f"{alerta['stock_actual']:.2f}")
            item_act.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if alerta['stock_actual'] <= 0:
                item_act.setForeground(QColor("#e74c3c")) # Rojo
            self.tbl_alertas_stock.setItem(row, 1, item_act)

            item_min = QTableWidgetItem(f"{alerta['stock_minimo']:.2f}")
            item_min.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_alertas_stock.setItem(row, 2, item_min)
