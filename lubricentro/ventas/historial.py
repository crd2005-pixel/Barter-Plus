# -*- coding: utf-8 -*-
import os, glob, re, datetime as dt
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QDialog, QHeaderView, QMessageBox
)

from db import SessionLocal, Venta

try:
    from db import VentaPago
except Exception:
    VentaPago = None

# -------- util --------
def _fmt(n):
    try:
        return f"${float(n):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "$0,00"

def _get(obj, *names, default=None):
    for n in names:
        if hasattr(obj, n):
            try:
                v = getattr(obj, n)
                return v() if callable(v) else v
            except Exception:
                pass
    return default

def _comp_str(v):
    """
    Normaliza a ####-######.
    Toma de varios campos o cae a 0001-id.
    """
    campos = ("comprobante","numero_comprobante","nro_comprobante","numero","nro")
    for n in campos:
        val = _get(v, n)
        if val:
            s = str(val).strip()
            m = re.match(r"^\s*0*(\d+)\s*-\s*0*(\d+)\s*$", s)
            if m:
                pv, seq = int(m.group(1)), int(m.group(2))
                return f"{pv:04d}-{seq:06d}"
            # si guardaron solo el número
            try:
                seq = int(s)
                # intenta pv desde el modelo, si no 1
                pv = _get(v, "punto_venta", "pto_venta", "pv", default=1) or 1
                pv = int(pv) if int(pv) > 0 else 1
                return f"{pv:04d}-{seq:06d}"
            except Exception:
                break
    # fallback a id
    vid = _get(v, "id", default=None)
    try:
        return f"0001-{int(vid):06d}"
    except Exception:
        return "0001-000001"

# -------- Detalle --------
class DetalleVentaDialog(QDialog):
    def __init__(self, venta_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Detalle de venta #{venta_id}")
        self.resize(760, 540)
        layout = QVBoxLayout(self)

        with SessionLocal() as s:
            v = s.query(Venta).get(venta_id)
            if not v:
                QMessageBox.warning(self, "Venta", "No se encontró la venta.")
                self.close(); return

            comp = _comp_str(v)
            layout.addWidget(QLabel(f"Comprobante: {comp}"))

            cli_txt = (
                _get(v, "cliente_nombre", "nombre_cliente", "cliente_texto", "cliente_str")
                or (_get(v, "cliente").nombre if _get(v, "cliente") else "-")
                or "-"
            )
            layout.addWidget(QLabel(f"Cliente: {cli_txt}"))

            fecha = _get(v, "fecha") or dt.datetime.now()
            layout.addWidget(QLabel(f"Fecha: {fecha.strftime('%d/%m/%Y %H:%M')}"))

            forma = _get(v, "forma_pago", "pago", "metodo_pago", default="-") or "-"
            layout.addWidget(QLabel(f"Forma de pago: {forma}"))

            if bool(_get(v, "anulada", default=False)):
                layout.addWidget(QLabel(f"Estado: ANULADA ({_get(v,'motivo_anulacion','') or ''})"))

            tbl = QTableWidget(0, 4)
            tbl.setHorizontalHeaderLabels(["Producto", "Cantidad", "Precio", "Subtotal"])
            tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            layout.addWidget(tbl)

            for it in _get(v, "items", default=[]) or []:
                nombre = (
                    _get(it, "nombre", "descripcion", "detalle")
                    or (_get(it, "producto").nombre if _get(it, "producto") else "(Manual)")
                )
                q = _get(it, "cantidad", "cant", default=0) or 0
                try: q = float(q)
                except Exception: q = 0.0
                sub = _get(it, "subtotal", "importe", default=0) or 0
                try: sub = float(sub)
                except Exception: sub = 0.0
                pu = _get(it, "precio", "precio_unit", "precio_unitario", "p_unit", "precio_venta",
                          "precio_u", "unit_price", "valor_unitario", "importe_unit")
                try: pu = float(pu)
                except Exception: pu = sub / q if q else 0.0

                r = tbl.rowCount(); tbl.insertRow(r)
                tbl.setItem(r, 0, QTableWidgetItem(str(nombre)))
                tbl.setItem(r, 1, QTableWidgetItem(f"{q:.2f}"))
                tbl.setItem(r, 2, QTableWidgetItem(_fmt(pu)))
                tbl.setItem(r, 3, QTableWidgetItem(_fmt(sub)))

            total = _get(v, "total", "total_final", "importe_total", "monto_total", "importe", "monto", default=0.0) or 0.0
            layout.addWidget(QLabel(f"Total: {_fmt(total)}"))

            # botón abrir PDF: busca en exports y export
            try:
                patterns = [
                    os.path.join("exports", "remitos", f"remito_{venta_id}_*.pdf"),
                    os.path.join("export",  "remitos", f"remito_{venta_id}_*.pdf"),
                ]
                files = []
                for p in patterns:
                    files.extend(glob.glob(p))
                if files:
                    files.sort()
                    btn_pdf = QPushButton("Abrir comprobante (PDF)")
                    btn_pdf.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(files[-1])))
                    layout.addWidget(btn_pdf)
            except Exception:
                pass

            if VentaPago is not None:
                try:
                    pagos = s.query(VentaPago).filter_by(venta_id=_get(v, "id")).all()
                except Exception:
                    pagos = []
                if pagos:
                    layout.addWidget(QLabel("Pagos registrados:"))
                    for p in pagos:
                        medio = _get(p, "medio", "forma", default="-") or "-"
                        monto = _get(p, "monto", "importe", default=0.0) or 0.0
                        det = _get(p, "detalle", default="") or ""
                        layout.addWidget(QLabel(f"• {medio}: {_fmt(monto)} {det}"))

        h = QHBoxLayout()
        b = QPushButton("Cerrar"); b.clicked.connect(self.close)
        h.addStretch(); h.addWidget(b)
        layout.addLayout(h)

# -------- Listado --------
class HistorialVentasTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self.lbl_total = QLabel("Total general: $0,00")
        layout.addWidget(self.lbl_total)

        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels(["N°", "Cliente", "Fecha", "Forma de pago", "Total", "Estado"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tbl)

        btns = QHBoxLayout()
        self.btn_refresh = QPushButton("Actualizar"); self.btn_refresh.clicked.connect(self.cargar)
        btns.addStretch(); btns.addWidget(self.btn_refresh)
        layout.addLayout(btns)

        self.tbl.cellDoubleClicked.connect(self._abrir_detalle)
        self.cargar()

    def cargar(self):
        self.tbl.setRowCount(0)
        total_general = 0.0
        with SessionLocal() as s:
            ventas = s.query(Venta).order_by(Venta.fecha.desc()).all()
            for v in ventas:
                r = self.tbl.rowCount(); self.tbl.insertRow(r)

                nro = _comp_str(v)
                it_n = QTableWidgetItem(nro)
                it_n.setData(Qt.UserRole, _get(v, "id"))        # ID oculto para doble click
                self.tbl.setItem(r, 0, it_n)

                cli_txt = (
                    _get(v, "cliente_nombre", "nombre_cliente", "cliente_texto", "cliente_str")
                    or (_get(v, "cliente").nombre if _get(v, "cliente") else "-")
                    or "-"
                )
                self.tbl.setItem(r, 1, QTableWidgetItem(cli_txt))

                fecha = _get(v, "fecha")
                fecha_txt = fecha.strftime("%d/%m/%Y %H:%M") if isinstance(fecha, dt.datetime) else ""
                self.tbl.setItem(r, 2, QTableWidgetItem(fecha_txt))

                forma = _get(v, "forma_pago", "pago", "metodo_pago", default="-") or "-"
                self.tbl.setItem(r, 3, QTableWidgetItem(forma))

                total = _get(v, "total", "total_final", "importe_total", "monto_total", "importe", "monto", default=0.0) or 0.0
                self.tbl.setItem(r, 4, QTableWidgetItem(_fmt(total)))

                # Check multiple flags for annulled state
                is_anul = bool(_get(v, "anulada", default=False))
                if not is_anul:
                    st = str(_get(v, "estado", default="")).strip().upper()
                    if st == "ANULADA":
                        is_anul = True

                estado = "Anulada" if is_anul else "Emitida"
                self.tbl.setItem(r, 5, QTableWidgetItem(estado))

                try: total_general += float(total or 0.0)
                except Exception: pass

        self.lbl_total.setText(f"Total general: {_fmt(total_general)}")

    def _abrir_detalle(self, row, col):
        it = self.tbl.item(row, 0)
        if not it: return
        venta_id = it.data(Qt.UserRole)
        try:
            venta_id = int(venta_id)
        except Exception:
            return
        dlg = DetalleVentaDialog(venta_id, self)
        dlg.exec_()
