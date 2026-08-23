# costos/variables.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from productos.precios_tab import PreciosTab

class CostosVariablesTab(QWidget):
    """Espejo de Productos/Precios para visualizar el prorrateo en tiempo real."""
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        self.precios_tab = PreciosTab(self)
        lay.addWidget(self.precios_tab)

    def update_all(self):
        # Delegate reload to the inner PreciosTab if it supports it
        if hasattr(self.precios_tab, "cargar_precios"):
            self.precios_tab.cargar_precios()
        elif hasattr(self.precios_tab, "reload"):
            self.precios_tab.reload()
