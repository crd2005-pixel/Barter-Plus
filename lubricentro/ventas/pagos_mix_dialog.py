from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QComboBox
from .pago_tarjeta_dialog import PagoTarjetaDialog

class PagosMixtosDialog(QDialog):
    def __init__(self, total_base, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pagos combinados")
        self.resize(420, 240)
        self.total_base = float(total_base)
        lay = QVBoxLayout(self)

        lay.addWidget(QLabel(f"Total base: ${self.total_base:,.2f}"))

        # montos por medio
        self.inp_efectivo = QLineEdit("0")
        self.inp_transf   = QLineEdit("0")
        self.inp_debito   = QLineEdit("0")
        self.inp_cheque   = QLineEdit("0")
        self.inp_tarjeta  = QLineEdit("0"); self.inp_tarjeta.setReadOnly(True)

        for lbl, w in [("Efectivo",self.inp_efectivo),("Transferencia",self.inp_transf),
                       ("Débito",self.inp_debito),("Cheque",self.inp_cheque),("Tarjeta",self.inp_tarjeta)]:
            row = QHBoxLayout()
            row.addWidget(QLabel(lbl)); row.addWidget(w)
            if lbl=="Tarjeta":
                b = QPushButton("Configurar…")
                b.clicked.connect(self._cfg_tarjeta)
                row.addWidget(b)
            lay.addLayout(row)

        self.lbl_restante = QLabel(f"Restante: ${self.total_base:,.2f}")
        lay.addWidget(self.lbl_restante)

        btns = QHBoxLayout()
        btn_ok = QPushButton("Aceptar"); btn_ok.clicked.connect(self._ok)
        btns.addStretch(); btns.addWidget(btn_ok)
        lay.addLayout(btns)

        self._resync()

    def _float(self, w):
        try: return float(w.text() or 0)
        except: return 0.0

    def _resync(self):
        pagado = self._float(self.inp_efectivo)+self._float(self.inp_transf)+self._float(self.inp_debito)+self._float(self.inp_cheque)+self._float(self.inp_tarjeta)
        self.lbl_restante.setText(f"Restante: ${max(self.total_base - pagado, 0):,.2f}")

    def _cfg_tarjeta(self):
        dlg = PagoTarjetaDialog(self.total_base, self)
        if dlg.exec_():
            data = dlg.result_data()
            self._tarjeta_data = data
            self.inp_tarjeta.setText(f"{data['total_tarjeta']:.2f}")
            self._resync()

    def _ok(self):
        pagado = self._float(self.inp_efectivo)+self._float(self.inp_transf)+self._float(self.inp_debito)+self._float(self.inp_cheque)+self._float(self.inp_tarjeta)
        if abs(pagado - self.total_base) > 0.01:
            QMessageBox.warning(self,"Pagos","La suma de medios debe igualar el total.")
            return
        self.accept()

    def result_data(self):
        data = {
            "Efectivo": self._float(self.inp_efectivo),
            "Transferencia": self._float(self.inp_transf),
            "Débito": self._float(self.inp_debito),
            "Cheque": self._float(self.inp_cheque),
        }
        tdata = getattr(self, "_tarjeta_data", None)
        if tdata:
            data["Tarjeta"] = tdata
        else:
            data["Tarjeta"] = None
        return data
