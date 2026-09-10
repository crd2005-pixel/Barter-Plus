from PyQt6.QtWidgets import QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QApplication
from PyQt6.QtCore import Qt
from ui.views.productos_view import ProductosTab
from ui.views.precios_view import PreciosTab
from ui.views.proveedores_view import ProveedoresView
from ui.views.ventas_view import VentasTab
from ui.views.caja_view import CajaView
from ui.views.taller_view import TallerView
from ui.views.registros_view import RegistrosView
from ui.styles import LIGHT_THEME, DARK_THEME

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Barter Plus - Sistema de Gestión")
        self.resize(1024, 768)

        # Central widget y layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # --- HEADER CON TÍTULO Y SELECTOR DE TEMA ---
        self.header_layout = QHBoxLayout()

        self.header_label = QLabel("Barter Plus")
        self.header_label.setStyleSheet("font-size: 24px; font-weight: bold; margin: 10px;")

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Tema Oscuro", "Tema Claro"])
        self.theme_combo.currentTextChanged.connect(self.change_theme)

        self.header_layout.addWidget(self.header_label)
        self.header_layout.addStretch()
        self.header_layout.addWidget(QLabel("Apariencia:"))
        self.header_layout.addWidget(self.theme_combo)

        self.layout.addLayout(self.header_layout)

        # Aplicar tema inicial (Oscuro)
        self.change_theme("Tema Oscuro")

        # Contenedor de Pestañas
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # Inicializar pestañas
        self.setup_tabs()

    def setup_tabs(self):
        # Placeholder para otras pestañas


        # Pestañas reales
        self.ventas_tab = VentasTab()
        self.productos_tab = ProductosTab()
        self.precios_tab = PreciosTab()
        self.proveedores_tab = ProveedoresView()

        # Añadir pestañas al QTabWidget
        self.tabs.addTab(self.ventas_tab, "Punto de Venta")

        self.caja_view = CajaView()
        self.tabs.addTab(self.caja_view, "Caja / Tesorería")

        self.taller_view = TallerView()
        self.tabs.addTab(self.taller_view, "Taller / Servicios")

        self.registros_view = RegistrosView()
        self.tabs.addTab(self.registros_view, "Registros y Finanzas")


        self.tabs.addTab(self.productos_tab, "Productos")
        self.tabs.addTab(self.precios_tab, "Remarcación (Precios)")
        self.tabs.addTab(self.proveedores_tab, "Proveedores y Compras")


        # Seleccionar por defecto la pestaña Ventas
        self.tabs.setCurrentWidget(self.ventas_tab)

    def change_theme(self, theme_name: str):
        app = QApplication.instance()
        if app:
            if theme_name == "Tema Oscuro":
                app.setStyleSheet(DARK_THEME)
            else:
                app.setStyleSheet(LIGHT_THEME)
