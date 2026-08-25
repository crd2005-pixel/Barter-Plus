from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from .facturas import FacturasTab
from .ctas import CuentasCorrientesTab
from .import_maestro import ImportadorMaestroTab
from proveedores.pedidos import PedidosTab

class ProveedoresTab(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        tabs = QTabWidget(); lay.addWidget(tabs)
        tabs.addTab(FacturasTab(on_after_save=self._after_change), "Facturas")
        tabs.addTab(CuentasCorrientesTab(), "Cuentas corrientes")
        tabs.addTab(ImportadorMaestroTab(on_after_import=self._after_change), "Importar Maestro")

        self.pedidos_tab = PedidosTab()
        tabs.addTab(self.pedidos_tab, "Pedidos")
        self.tabs = tabs # guardamos referencia

    def _after_change(self): pass

    def refresh(self):
        # Propagar refresh a la sub-pestaña activa
        current = self.tabs.currentWidget()
        if hasattr(current, "refresh"):
            current.refresh()
        elif hasattr(current, "reload"):
            current.reload()
