from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QLineEdit, QComboBox, QMessageBox
from db import SessionLocal
from db import TarjetaCoef

class CuotasConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Coeficientes de Tarjetas")
        self.resize(520, 400)
        lay = QVBoxLayout(self)

        # Inputs
        row = QHBoxLayout()
        self.cb_marca = QComboBox(); self.cb_marca.addItems(["Naranja","Visa","Mastercard","Cabal","Amex"])
        self.cb_cuotas = QComboBox(); self.cb_cuotas.addItems([str(x) for x in [1,3,6,12]])
        self.inp_recargo = QLineEdit(); self.inp_recargo.setPlaceholderText("Recargo % (ej 30)")

        btn_add = QPushButton("Guardar / Agregar")
        btn_add.clicked.connect(self._guardar)

        row.addWidget(self.cb_marca); row.addWidget(self.cb_cuotas); row.addWidget(self.inp_recargo); row.addWidget(btn_add)
        lay.addLayout(row)

        # Tabla
        self.tbl = QTableWidget(0, 3)
        self.tbl.setHorizontalHeaderLabels(["Marca","Cuotas","Recargo %"])
        lay.addWidget(self.tbl)

        # Botones
        h = QHBoxLayout()
        btn_del = QPushButton("Eliminar seleccionado")
        btn_del.clicked.connect(self._eliminar)
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        h.addStretch(); h.addWidget(btn_del); h.addWidget(btn_close)
        lay.addLayout(h)

        self._cargar()

    def _cargar(self):
        self.tbl.setRowCount(0)
        with SessionLocal() as s:
            for c in s.query(TarjetaCoef).order_by(TarjetaCoef.marca, TarjetaCoef.cuotas):
                r = self.tbl.rowCount(); self.tbl.insertRow(r)
                self.tbl.setItem(r, 0, QTableWidgetItem(c.marca))
                self.tbl.setItem(r, 1, QTableWidgetItem(str(c.cuotas)))
                self.tbl.setItem(r, 2, QTableWidgetItem(f"{c.recargo_pct:.2f}"))

    def _guardar(self):
        try:
            marca = self.cb_marca.currentText()
            cuotas = int(self.cb_cuotas.currentText())
            rec = float(self.inp_recargo.text())
        except Exception:
            QMessageBox.warning(self,"Datos","Valores inválidos"); return
        with SessionLocal() as s:
            obj = s.query(TarjetaCoef).filter_by(marca=marca, cuotas=cuotas).first()
            if not obj:
                obj = TarjetaCoef(marca=marca, cuotas=cuotas, recargo_pct=rec)
                s.add(obj)
            else:
                obj.recargo_pct = rec
            s.commit()
        self._cargar()
        self.inp_recargo.clear()

    def _eliminar(self):
        r = self.tbl.currentRow()
        if r < 0: return
        marca = self.tbl.item(r,0).text()
        cuotas = int(self.tbl.item(r,1).text())
        with SessionLocal() as s:
            obj = s.query(TarjetaCoef).filter_by(marca=marca, cuotas=cuotas).first()
            if obj:
                s.delete(obj); s.commit()
        self._cargar()
