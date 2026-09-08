from PyQt6.QtWidgets import QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from ui.views.productos_view import ProductosTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Barter Plus - Sistema de Gestión")
        self.resize(1024, 768)

        # Central widget y layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Título principal / Header
        self.header_label = QLabel("Barter Plus")
        self.header_label.setStyleSheet("font-size: 24px; font-weight: bold; margin: 10px;")
        self.header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.header_label)

        # Contenedor de Pestañas
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # Inicializar pestañas
        self.setup_tabs()

    def setup_tabs(self):
        # Placeholder para otras pestañas
        self.ventas_tab = QWidget()
        self.ventas_tab.setLayout(QVBoxLayout())
        self.ventas_tab.layout().addWidget(QLabel("Módulo de Ventas (En construcción)"))

        self.proveedores_tab = QWidget()
        self.proveedores_tab.setLayout(QVBoxLayout())
        self.proveedores_tab.layout().addWidget(QLabel("Módulo de Proveedores (En construcción)"))

        self.caja_tab = QWidget()
        self.caja_tab.setLayout(QVBoxLayout())
        self.caja_tab.layout().addWidget(QLabel("Módulo de Caja (En construcción)"))

        # Pestaña real de Productos
        self.productos_tab = ProductosTab()

        # Añadir pestañas al QTabWidget
        self.tabs.addTab(self.ventas_tab, "Ventas")
        self.tabs.addTab(self.productos_tab, "Productos")
        self.tabs.addTab(self.proveedores_tab, "Proveedores")
        self.tabs.addTab(self.caja_tab, "Caja")

        # Seleccionar por defecto la pestaña de Productos para testear
        self.tabs.setCurrentWidget(self.productos_tab)
