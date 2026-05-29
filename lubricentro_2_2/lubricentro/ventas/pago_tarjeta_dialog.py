from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit, QPushButton
from db import SessionLocal, TarjetaCoef

class PagoTarjetaDialog(QDialog):
    def __init__(self, total_base, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pago con Tarjeta")
        self.resize(380, 180)
        self.total_base = float(total_base)
        lay = QVBoxLayout(self)

        row1 = QHBoxLayout()
        self.cb_marca = QComboBox(); self.cb_marca.addItems(["Naranja","Visa","Mastercard","Cabal","Amex"])
        self.cb_cuotas = QComboBox(); self.cb_cuotas.addItems([str(x) for x in [1,3,6,12]])
        row1.addWidget(QLabel("Marca:")); row1.addWidget(self.cb_marca)
        row1.addWidget(QLabel("Cuotas:")); row1.addWidget(self.cb_cuotas)
        lay.addLayout(row1)

        self.lbl_recargo = QLabel("Recargo: 0%")
        self.lbl_total = QLabel(f"Total con recargo: ${self.total_base:,.2f}")
        self.lbl_cuota = QLabel(f"Valor cuota: ${self.total_base:,.2f}")
        lay.addWidget(self.lbl_recargo)
        lay.addWidget(self.lbl_total)
        lay.addWidget(self.lbl_cuota)

        btns = QHBoxLayout()
        btn_ok = QPushButton("Aceptar"); btn_ok.clicked.connect(self.accept)
        btns.addStretch(); btns.addWidget(btn_ok)
        lay.addLayout(btns)

        self.cb_marca.currentTextChanged.connect(self._recalc)
        self.cb_cuotas.currentTextChanged.connect(self._recalc)
        self._recalc()

    def _recargo_pct(self):
        with SessionLocal() as s:
            obj = s.query(TarjetaCoef).filter_by(
                marca=self.cb_marca.currentText(),
                cuotas=int(self.cb_cuotas.currentText())
            ).first()
            return float(obj.recargo_pct) if obj else 0.0

    def _recalc(self):
        r = self._recargo_pct()
        tot = self.total_base * (1.0 + r/100.0)
        ctas = int(self.cb_cuotas.currentText())
        self.lbl_recargo.setText(f"Recargo: {r:.2f}%")
        self.lbl_total.setText(f"Total con recargo: ${tot:,.2f}")
        self.lbl_cuota.setText(f"Valor cuota: ${tot/ctas:,.2f}")

    # resultados
    def result_data(self):
        r = self._recargo_pct()
        ctas = int(self.cb_cuotas.currentText())
        tot = self.total_base * (1.0 + r/100.0)
        return {
            "marca": self.cb_marca.currentText(),
            "cuotas": ctas,
            "recargo_pct": r,
            "total_tarjeta": tot,
            "valor_cuota": tot/ctas
        }
