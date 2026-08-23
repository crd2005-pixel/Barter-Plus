# -*- coding: utf-8 -*-
import inspect
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem
)

from db import SessionLocal

# ==== descubrimiento y helpers (mismo criterio que la pestaña) ====
def _discover_cc_models():
    modelos = []
    try:
        import db as _db
        for name, obj in _db.__dict__.items():
            if not inspect.isclass(obj): continue
            lname = name.lower()
            if ("cta" in lname or "corrient" in lname) and name not in ("Cliente",):
                modelos.append(obj)
    except Exception:
        pass
    pref = ("CuentaCorriente", "CtaCorriente", "CtaCte", "MovimientoCuenta", "CuentaCorrienteMov")
    modelos.sort(key=lambda c: (0 if c.__name__ in pref else 1, c.__name__))
    return modelos

CC_MODELOS = _discover_cc_models()

def _get_field(obj, names):
    for n in names:
        if hasattr(obj, n):
            try:
                return n, getattr(obj, n)
            except Exception:
                pass
    return None, None

def _as_float(v, d=0.0):
    try:
        return float(v or 0.0)
    except Exception:
        return d

def _fmt_money(n: float) -> str:
    try:
        return f"${float(n):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "$0,00"

def _mov_fecha(mov):
    n, v = _get_field(mov, ("fecha","fec","created_at","fechahora","datetime","ts"))
    return getattr(v, "strftime", lambda *_: v)("%Y-%m-%d %H:%M") if v else ""

def _mov_detalle(mov):
    _, txt = _get_field(mov, ("detalle","descripcion","observacion","obs","concepto","glosa","nota"))
    return str(txt or "")

def _mov_comprobante(mov):
    _, comp = _get_field(mov, ("comprobante", "nro_comprobante", "numero", "nro"))
    return str(comp or "")

def _mov_debe(mov):
    _, debe = _get_field(mov, ("debe","debito","debit"))
    if debe is not None:
        return _as_float(debe)
    # si no hay debe/haber, todo monto positivo se ve como debe
    _, monto = _get_field(mov, ("monto","importe","valor","importe_total","monto_mov","monto_neto"))
    m = _as_float(monto)
    return m if m > 0 else 0.0

def _mov_haber(mov):
    _, haber = _get_field(mov, ("haber","credito","credit"))
    if haber is not None:
        return _as_float(haber)
    # si no hay debe/haber, los montos negativos se ven como haber
    _, monto = _get_field(mov, ("monto","importe","valor","importe_total","monto_mov","monto_neto"))
    m = _as_float(monto)
    return -m if m < 0 else 0.0

def _mov_signo(mov):
    # saldo del movimiento: +debe - haber si existen; si no, monto
    d = _mov_debe(mov)
    h = _mov_haber(mov)
    if d or h:
        return d - h
    _, monto = _get_field(mov, ("monto","importe","valor","importe_total","monto_mov","monto_neto"))
    return _as_float(monto)

def _load_movs_cliente(session, key_type, key_val):
    """
    key_type: 'id' o 'name'
    key_val : id (int) o nombre (str)
    """
    movs = []
    for Model in CC_MODELOS:
        try:
            q = session.query(Model)
        except Exception:
            continue

        if key_type == "id":
            # filtra por atributos posibles
            for f in ("cliente_id","id_cliente","fk_cliente","id_cli"):
                if hasattr(Model, f):
                    try:
                        rows = q.filter(getattr(Model, f) == key_val).all()
                        movs.extend(rows)
                        break
                    except Exception:
                        pass
        elif key_type == "name":
            for f in ("cliente","cliente_nombre","nombre_cliente","cliente_texto"):
                if hasattr(Model, f):
                    try:
                        rows = q.filter(getattr(Model, f) == key_val).all()
                        movs.extend(rows)
                        break
                    except Exception:
                        pass

    # orden por fecha si se puede, si no queda en el orden natural
    try:
        movs.sort(key=lambda m: _mov_fecha(m) or "")
    except Exception:
        pass

    return movs

# ==== Diálogo ====
class MovimientosCuentaDialog(QDialog):
    """
    Muestra todos los movimientos de una cuenta y el saldo acumulado.
    """
    def __init__(self, parent=None, key_type=None, key_val=None, titulo="Cuenta Corriente"):
        super().__init__(parent)
        self.setWindowTitle(f"Movimientos – {titulo}")
        self.resize(760, 520)

        root = QVBoxLayout(self)

        hdr = QHBoxLayout()
        self.lbl_title = QLabel(f"{titulo}")
        self.lbl_title.setStyleSheet("font-size:16px; font-weight:600;")
        hdr.addWidget(self.lbl_title)
        hdr.addStretch()
        self.lbl_saldo = QLabel("Saldo: $0,00")
        self.lbl_saldo.setStyleSheet("font-size:18px; font-weight:700; color:#0a58ca;")
        hdr.addWidget(self.lbl_saldo)
        root.addLayout(hdr)

        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels(["Fecha", "Detalle", "Comp.", "Debe", "Haber", "Saldo"])
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers)
        self.tbl.setSelectionBehavior(self.tbl.SelectRows)
        root.addWidget(self.tbl)

        self._key_type = key_type
        self._key_val = key_val

        self._load()

    def _load(self):
        total = 0.0
        self.tbl.setRowCount(0)

        with SessionLocal() as s:
            rows = _load_movs_cliente(s, self._key_type, self._key_val)
            for r in rows:
                fecha = _mov_fecha(r)
                det   = _mov_detalle(r)
                comp  = _mov_comprobante(r)
                debe  = _mov_debe(r)
                haber = _mov_haber(r)
                total += (debe - haber)

                row = self.tbl.rowCount()
                self.tbl.insertRow(row)
                self.tbl.setItem(row, 0, QTableWidgetItem(fecha))
                self.tbl.setItem(row, 1, QTableWidgetItem(det))
                self.tbl.setItem(row, 2, QTableWidgetItem(comp))

                it_d = QTableWidgetItem(_fmt_money(debe))
                it_h = QTableWidgetItem(_fmt_money(haber))
                it_s = QTableWidgetItem(_fmt_money(total))
                for it in (it_d, it_h, it_s):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                self.tbl.setItem(row, 3, it_d)
                self.tbl.setItem(row, 4, it_h)
                self.tbl.setItem(row, 5, it_s)

        self.lbl_saldo.setText(f"Saldo: {_fmt_money(total)}")
