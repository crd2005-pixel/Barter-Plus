# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from .stock.base_stock import StockRubroGroup
from .promociones.base_promos import PromocionesRubroGroup
from .precios_tab import PreciosTab
from .codigos_barra import CodigosBarraTab

class ProductosTab(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        tabs = QTabWidget()
        lay.addWidget(tabs)

        tabs.addTab(StockRubroGroup(), "Stock")
        tabs.addTab(PromocionesRubroGroup(), "Promociones")
        tabs.addTab(PreciosTab(), "Precios")
        tabs.addTab(CodigosBarraTab(), "Códigos de Barra")
