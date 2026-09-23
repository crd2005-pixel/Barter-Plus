# -*- coding: utf-8 -*-
import datetime as dt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QSpinBox, QPushButton
)
from PyQt5.QtCore import Qt
from db import SessionLocal
from services.costo_service import CostoService

class CostosHistoricoTab(QWidget):
    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Controles superiores
        h = QHBoxLayout()
        h.addWidget(QLabel("Año:"))
        self.sp_anio = QSpinBox()
        self.sp_anio.setRange(2000, 2100)
        self.sp_anio.setValue(dt.date.today().year)
        self.sp_anio.valueChanged.connect(self._load_data)
        h.addWidget(self.sp_anio)

        self.btn_refresh = QPushButton("Actualizar")
        self.btn_refresh.clicked.connect(self._load_data)
        h.addWidget(self.btn_refresh)
        h.addStretch()
        layout.addLayout(h)

        # Tabla
        self.tbl = QTableWidget()
        self.tbl.setColumnCount(2)
        self.tbl.setHorizontalHeaderLabels(["Mes", "Total Gastos Fijos"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.tbl)

    def update_all(self):
        self._load_data()

    def _load_data(self):
        year = self.sp_anio.value()
        self.tbl.setRowCount(0)

        try:
            with SessionLocal() as s:
                data = CostoService.get_monthly_costs(s, year)

            # data es lista de (mes, total)
            # Meses nombres
            nombres_mes = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                           "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

            self.tbl.setRowCount(len(data))
            for r, (mes_num, total) in enumerate(data):
                nm = nombres_mes[mes_num] if 1 <= mes_num <= 12 else str(mes_num)

                it_mes = QTableWidgetItem(nm)
                it_mes.setTextAlignment(Qt.AlignCenter)

                it_total = QTableWidgetItem(f"${total:,.2f}")
                it_total.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                self.tbl.setItem(r, 0, it_mes)
                self.tbl.setItem(r, 1, it_total)

        except Exception as e:
            print(f"Error cargando historico costos: {e}")
