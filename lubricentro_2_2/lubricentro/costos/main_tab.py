# costos/main_tab.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QHBoxLayout, QLabel
from .fijos import CostosFijosTab
from .variables import CostosVariablesTab
from .historico import CostosHistoricoTab
from services.costo_service import CostoService
from db import SessionLocal

class CostosTab(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)

        # Barra superior: total mensual de gastos fijos (mes en curso)
        top = QHBoxLayout()
        self.lbl_total = QLabel("")
        self._refresh_total()
        top.addWidget(self.lbl_total)
        top.addStretch(1)
        root.addLayout(top)

        self.tabs = QTabWidget()
        self.tabs.addTab(CostosFijosTab(on_change=self._refresh_total), "Gastos fijos")
        self.tabs.addTab(CostosVariablesTab(), "Gastos variables")  # ahora copia de Productos/Precios
        self.tabs.addTab(CostosHistoricoTab(), "Histórico Anual")
        root.addWidget(self.tabs)

    def _refresh_total(self):
        try:
            with SessionLocal() as s:
                total = CostoService.calcular_total_fijos_mes(s)
            self.lbl_total.setText(f"Total mensual Gastos fijos (mes en curso): ${total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        except Exception:
            self.lbl_total.setText("Total: Error")

    def reload(self):
        """Called by F5 from main window."""
        self._refresh_total()
        w = self.tabs.currentWidget()
        if hasattr(w, "update_all"):
            w.update_all()
        elif hasattr(w, "reload"):
            w.reload()
