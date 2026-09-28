from PyQt6.QtWidgets import QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QApplication
from PyQt6.QtCore import Qt
from ui.views.productos_view import ProductosTab
from ui.views.precios_view import PreciosTab
from ui.views.proveedores_view import ProveedoresView
from ui.views.ventas_view import VentasTab
from ui.views.caja_view import CajaView
from ui.views.taller_view import TallerView
from ui.views.registros_view import RegistrosView
from ui.views.gastos_view import GastosView
from ui.views.clientes_view import ClientesView
from ui.views.dashboard_view import DashboardView
from ui.views.configuracion_view import ConfiguracionView
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
        # Pestañas reales
        self.ventas_tab = VentasTab()
        self.productos_tab = ProductosTab()
        self.precios_tab = PreciosTab()
        self.proveedores_tab = ProveedoresView()
        self.dashboard_view = DashboardView()

        # Añadir pestañas al QTabWidget
        self.tabs.addTab(self.ventas_tab, "POS")

        self.caja_view = CajaView()
        self.tabs.addTab(self.caja_view, "Caja")

        self.gastos_view = GastosView()
        self.tabs.addTab(self.gastos_view, "Egresos")

        self.taller_view = TallerView()
        self.tabs.addTab(self.taller_view, "Taller")

        self.registros_view = RegistrosView()
        self.tabs.addTab(self.registros_view, "Finanzas")

        self.clientes_view = ClientesView()
        self.tabs.addTab(self.clientes_view, "Clientes")

        self.tabs.addTab(self.productos_tab, "Productos")
        self.tabs.addTab(self.precios_tab, "Precios")
        self.tabs.addTab(self.proveedores_tab, "Proveedores")

        self.configuracion_view = ConfiguracionView()
        self.tabs.addTab(self.configuracion_view, "Configuración")

        # Dashboard Principal movido al final
        self.tabs.addTab(self.dashboard_view, "Métricas")


# Hacer las pestañas movibles
        self.tabs.setMovable(True)

        # Seleccionar por defecto la pestaña Dashboard
        self.tabs.setCurrentWidget(self.ventas_tab)


    def _aplicar_permisos(self, rol, permisos_string):
        import json
        self.rol_actual = rol
        if rol == 'Administrador':
            return # Todo visible

        # Parse JSON o fallback a lista separada por comas
        try:
            permisos_lista = json.loads(permisos_string) if permisos_string else []
        except:
            permisos_lista = [p.strip() for p in permisos_string.split(',')] if permisos_string else []

        # Nivel 1: Ocultar pestañas principales
        for i in range(self.tabs.count()):
            tab_text = self.tabs.tabText(i)
            if tab_text == "Configuración":
                self.tabs.setTabVisible(i, False)
                continue

            # Verifica si la pestaña principal o alguno de sus hijos está en la lista
            padre_ok = tab_text in permisos_lista
            hijo_ok = any(p.startswith(f"{tab_text}:") for p in permisos_lista)

            if not (padre_ok or hijo_ok):
                self.tabs.setTabVisible(i, False)
            else:
                # Nivel 2: Ocultar subpestañas dentro de los módulos
                widget = self.tabs.widget(i)
                if hasattr(widget, 'tabs'):
                    sub_tabs = widget.tabs
                    for j in range(sub_tabs.count()):
                        sub_text = sub_tabs.tabText(j)
                        sub_full = f"{tab_text}:{sub_text}"
                        if sub_full not in permisos_lista and sub_text not in permisos_lista and not padre_ok:
                            sub_tabs.setTabVisible(j, False)

        # Seguridad Activa: Seleccionar primera pestaña visible
        for i in range(self.tabs.count()):
            if self.tabs.isTabVisible(i):
                self.tabs.setCurrentIndex(i)
                break
            elif tab_text not in permisos_lista:
                self.tabs.setTabVisible(i, False)

    def change_theme(self, theme_name: str):
        app = QApplication.instance()
        if app:
            if theme_name == "Tema Oscuro":
                app.setStyleSheet(DARK_THEME)
            else:
                app.setStyleSheet(LIGHT_THEME)
