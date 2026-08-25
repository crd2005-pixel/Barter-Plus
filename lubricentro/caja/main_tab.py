# -*- coding: utf-8 -*-
# caja/main_tab.py
# Pestaña única de CAJA.
# Flujo: Cargar valores del día (precierre automático) → Observaciones → Cerrar caja.
# Historial de cierres en la misma pestaña. Estimados del sistema:
#   Ventas (pagos) + Cobros CtaCte clientes − Gastos, por medio.
# Nada se ve hasta que el cajero guarda sus valores.

import datetime as dt

from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDateEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QDialog, QFormLayout,
    QLineEdit, QGroupBox, QTextEdit, QFrame, QSizePolicy
)

from sqlalchemy import func

from db import SessionLocal
from db.models.caja import CierreCaja, CierreCajaItem, CierreCajaPago, CierreCajaAjuste
from services.caja_service import CajaService
from .detalle_dialog import DetalleCajaDialog

# -------------------- utilitarios --------------------

def _fmt(v):
    try:
        return f"{float(v):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    except Exception:
        return str(v)

def _f2(x):
    try:
        return float(str(x).replace(",", ".").strip())
    except Exception:
        return 0.0

# -------------------- diálogos --------------------

class ConteoDialog(QDialog):
    """Dialogo para ingresar los TOTALES del día por medio."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cargar valores del día")
        self.setModal(True)
        self.resize(640, 360)

        frm = QFormLayout(self)

        self.ed_ef = QLineEdit(self); self.ed_ef.setPlaceholderText("0,00"); self.ed_ef.setText("0")
        self.ed_tr = QLineEdit(self); self.ed_tr.setPlaceholderText("0,00"); self.ed_tr.setText("0")
        self.ed_db = QLineEdit(self); self.ed_db.setPlaceholderText("0,00"); self.ed_db.setText("0")
        self.ed_tc = QLineEdit(self); self.ed_tc.setPlaceholderText("0,00"); self.ed_tc.setText("0")
        self.ed_cc = QLineEdit(self); self.ed_cc.setPlaceholderText("0,00"); self.ed_cc.setText("0")
        self.ed_obs = QTextEdit(self); self.ed_obs.setPlaceholderText("Observación inicial (opcional)")
        self.ed_obs.setMinimumHeight(80)

        frm.addRow("Efectivo:", self.ed_ef)
        frm.addRow("Transferencia:", self.ed_tr)
        frm.addRow("Tarjeta débito:", self.ed_db)
        frm.addRow("Tarjeta crédito:", self.ed_tc)
        frm.addRow("Cuenta corriente:", self.ed_cc)
        frm.addRow("Observación:", self.ed_obs)

        hb = QHBoxLayout()
        self.btn_ok = QPushButton("Guardar", self)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("Cancelar", self)
        self.btn_cancel.clicked.connect(self.reject)
        for b in (self.btn_ok, self.btn_cancel):
            b.setAutoDefault(False); b.setDefault(False)
        hb.addStretch(); hb.addWidget(self.btn_ok); hb.addWidget(self.btn_cancel)
        frm.addRow(hb)

    def datos(self):
        return {
            "efectivo": _f2(self.ed_ef.text()),
            "transferencia": _f2(self.ed_tr.text()),
            "debito": _f2(self.ed_db.text()),
            "credito": _f2(self.ed_tc.text()),
            "ctacte": _f2(self.ed_cc.text()),
            "obs": (self.ed_obs.toPlainText() or "").strip()
        }

class ObservacionesDialog(QDialog):
    """Carga/edita observaciones del precierre."""
    def __init__(self, parent=None, dif_total=0.0, texto=""):
        super().__init__(parent)
        self.setWindowTitle("Observaciones de caja")
        self.setModal(True)
        self.resize(640, 300)

        frm = QFormLayout(self)
        self.lbl = QLabel(f"Diferencia total actual: {_fmt(dif_total)}")
        self.ed_obs = QTextEdit(self)
        self.ed_obs.setText(texto)
        self.ed_obs.setMinimumHeight(120)

        frm.addRow(self.lbl)
        frm.addRow("Observación:", self.ed_obs)

        hb = QHBoxLayout()
        self.btn_ok = QPushButton("Guardar", self); self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("Cancelar", self); self.btn_cancel.clicked.connect(self.reject)
        for b in (self.btn_ok, self.btn_cancel):
            b.setAutoDefault(False); b.setDefault(False)
        hb.addStretch(); hb.addWidget(self.btn_ok); hb.addWidget(self.btn_cancel)
        frm.addRow(hb)

    def texto(self):
        return (self.ed_obs.toPlainText() or "").strip()

# -------------------- pestaña principal --------------------

class CajaTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Main Layout: Vertical, clean spacing
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(15)

        # --- 1. Top Bar: Control Panel (Dates & Actions) ---
        gb_ctrl = QGroupBox("Panel de Control")
        gb_ctrl.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")

        layout_ctrl = QHBoxLayout(gb_ctrl)
        layout_ctrl.setContentsMargins(15, 15, 15, 15)
        layout_ctrl.setSpacing(20)

        # Date Section
        self.dp_desde = QDateEdit(calendarPopup=True); self.dp_desde.setDate(QDate.currentDate())
        self.dp_hasta = QDateEdit(calendarPopup=True); self.dp_hasta.setDate(QDate.currentDate())

        # Styles for dates
        date_style = "QDateEdit { font-size: 13px; padding: 4px; border: 1px solid #ccc; border-radius: 4px; }"
        self.dp_desde.setStyleSheet(date_style)
        self.dp_hasta.setStyleSheet(date_style)

        vbox_dates = QVBoxLayout()
        hbox_d1 = QHBoxLayout(); hbox_d1.addWidget(QLabel("Desde:")); hbox_d1.addWidget(self.dp_desde)
        hbox_d2 = QHBoxLayout(); hbox_d2.addWidget(QLabel("Hasta:")); hbox_d2.addWidget(self.dp_hasta)

        # Quick Date Buttons
        hbox_quick = QHBoxLayout()
        btn_hoy = QPushButton("Hoy"); btn_hoy.clicked.connect(lambda: self._set_rango_dias(0))
        btn_ayer = QPushButton("Ayer"); btn_ayer.clicked.connect(lambda: self._set_rango_dias(1))
        btn_sem = QPushButton("Semana"); btn_sem.clicked.connect(lambda: self._set_rango_dias(7))
        for b in (btn_hoy, btn_ayer, btn_sem):
            b.setStyleSheet("padding: 2px 5px; font-size: 11px;")
            hbox_quick.addWidget(b)

        vbox_dates.addLayout(hbox_d1)
        vbox_dates.addLayout(hbox_d2)
        vbox_dates.addLayout(hbox_quick)

        self.btn_actualizar = QPushButton("Actualizar Rango")
        self.btn_actualizar.setStyleSheet("padding: 6px 12px; font-weight: bold;")
        self.btn_actualizar.clicked.connect(self.cargar)

        layout_ctrl.addLayout(vbox_dates)
        layout_ctrl.addWidget(self.btn_actualizar)

        # Spacer
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        layout_ctrl.addWidget(line)

        # Actions Section (Big Buttons)
        self.btn_conteo = QPushButton("1. Cargar valores (Cierre)")
        self.btn_conteo.setStyleSheet("QPushButton { background-color: #007bff; color: white; font-weight: bold; padding: 10px 15px; border-radius: 5px; font-size: 13px; } QPushButton:hover { background-color: #0056b3; }")
        self.btn_conteo.clicked.connect(self._registrar_conteos)

        self.btn_obs = QPushButton("2. Observaciones")
        self.btn_obs.setStyleSheet("QPushButton { padding: 10px 15px; border-radius: 5px; font-size: 13px; border: 1px solid #ccc; }")
        self.btn_obs.clicked.connect(self._observaciones)

        self.btn_cerrar = QPushButton("3. Cerrar Caja Final")
        self.btn_cerrar.setStyleSheet("QPushButton { background-color: #28a745; color: white; font-weight: bold; padding: 10px 15px; border-radius: 5px; font-size: 13px; } QPushButton:hover { background-color: #218838; }")
        self.btn_cerrar.clicked.connect(self._cerrar_caja)

        layout_ctrl.addWidget(self.btn_conteo)
        layout_ctrl.addWidget(self.btn_obs)
        layout_ctrl.addWidget(self.btn_cerrar)
        layout_ctrl.addStretch()

        root.addWidget(gb_ctrl)

        # --- 2. Summary Section (Read Only) ---
        gb_res = QGroupBox("Resumen del Cierre Seleccionado")
        gb_res.setStyleSheet("QGroupBox { font-weight: bold; color: black; border: 1px solid #aaa; margin-top: 10px; }")
        gl = QHBoxLayout(gb_res)

        # High contrast styles
        lbl_base = "QLabel { font-size: 16px; padding: 6px; border-radius: 4px; border: 1px solid #888; background-color: #ffffff; font-weight: bold; }"

        self.lbl_sys = QLabel("Sistema: ---")
        self.lbl_sys.setStyleSheet(lbl_base + " color: #004085; background-color: #cce5ff;") # Dark blue on light blue

        self.lbl_cont = QLabel("Contado: ---")
        self.lbl_cont.setStyleSheet(lbl_base + " color: #155724; background-color: #d4edda;") # Dark green on light green

        self.lbl_dif = QLabel("Diferencia: ---")
        self.lbl_dif.setStyleSheet(lbl_base + " color: #721c24; background-color: #f8d7da;") # Dark red on light red

        # Etiquetas explicativas en negro fuerte
        l1 = QLabel("Calculado (Sistema):"); l1.setStyleSheet("color: black; font-weight: bold;")
        l2 = QLabel("Declarado (Caja):"); l2.setStyleSheet("color: black; font-weight: bold;")
        l3 = QLabel("Diferencia:"); l3.setStyleSheet("color: black; font-weight: bold;")

        gl.addWidget(l1); gl.addWidget(self.lbl_sys)
        gl.addSpacing(15)
        gl.addWidget(l2); gl.addWidget(self.lbl_cont)
        gl.addSpacing(15)
        gl.addWidget(l3); gl.addWidget(self.lbl_dif)
        gl.addStretch()

        root.addWidget(gb_res)

        # --- 3. History Table ---
        lbl_hist = QLabel("Historial de Cierres (Doble clic para ver detalles)")
        lbl_hist.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px; color: black;")
        root.addWidget(lbl_hist)

        self.tbl_hist = QTableWidget(0, 12, self)
        headers = [
            "Desde", "Hasta", "Estado",
            "Total (Sist.)",
            "Efectivo", "Transfer.", "Débito", "Crédito", "Cta.Cte.",
            "Dif. Efe", "Dif. Trf", "Dif. Otros"
        ]
        self.tbl_hist.setHorizontalHeaderLabels(headers)
        self.tbl_hist.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_hist.setSelectionBehavior(self.tbl_hist.SelectRows)
        self.tbl_hist.setEditTriggers(self.tbl_hist.NoEditTriggers)
        self.tbl_hist.setAlternatingRowColors(True)
        # High contrast table style
        self.tbl_hist.setStyleSheet("""
            QTableWidget { font-size: 12px; color: black; gridline-color: #666; selection-background-color: #007bff; selection-color: white; }
            QHeaderView::section { background-color: #343a40; color: white; padding: 5px; font-weight: bold; border: 1px solid #666; }
            QTableWidget::item { color: black; }
        """)
        self.tbl_hist.doubleClicked.connect(self._on_hist_double_click)

        root.addWidget(self.tbl_hist)

        # (Hidden table for internal use if needed, kept for compatibility)
        self.tbl = QTableWidget(0, 6, self)
        self.tbl.setVisible(False)
        root.addWidget(self.tbl)

        self._precierre_id = None
        self.cargar()

    # -------------------- helpers --------------------

    def _set_rango_dias(self, days_back):
        today = QDate.currentDate()
        if days_back == 0:
            self.dp_desde.setDate(today)
            self.dp_hasta.setDate(today)
        elif days_back == 1:
            yesterday = today.addDays(-1)
            self.dp_desde.setDate(yesterday)
            self.dp_hasta.setDate(yesterday)
        else:
            self.dp_desde.setDate(today.addDays(-days_back))
            self.dp_hasta.setDate(today)
        self.cargar()

    def _rango(self):
        d0 = self.dp_desde.date().toPyDate()
        d1 = self.dp_hasta.date().toPyDate()
        t0 = dt.datetime.combine(d0, dt.time.min)
        t1 = dt.datetime.combine(d1, dt.time.max)
        return t0, t1

    def _set_hist(self, r, c, v):
        it = QTableWidgetItem("" if v is None else str(v))
        it.setTextAlignment(Qt.AlignCenter)
        self.tbl_hist.setItem(r, c, it)

    # -------------------- flujo de caja --------------------

    # -------------------- carga / historial --------------------

    def cargar(self):
        # Reset labels to safe state (Blind)
        self.lbl_sys.setText("Sistema: ---")
        self.lbl_cont.setText("Contado: ---")
        self.lbl_dif.setText("Diferencia: ---")
        self.cargar_historial()

    def cargar_historial(self):
        self.tbl_hist.setRowCount(0)
        start, end = self._rango()
        with SessionLocal() as s:
            rows = (
                s.query(CierreCaja)
                .filter(CierreCaja.fecha_desde >= start, CierreCaja.fecha_hasta <= end)
                .order_by(CierreCaja.fecha_desde.desc(), CierreCaja.id.desc())
                .all()
            )
        self.tbl_hist.setRowCount(len(rows))
        for r, c in enumerate(rows):
            # Guardamos el ID en UserRole del primer item
            it_fecha = QTableWidgetItem(c.fecha_desde.strftime("%Y-%m-%d %H:%M") if c.fecha_desde else "")
            it_fecha.setData(Qt.UserRole, c.id)
            it_fecha.setTextAlignment(Qt.AlignCenter)
            self.tbl_hist.setItem(r, 0, it_fecha)

            self._set_hist(r, 1, c.fecha_hasta.strftime("%Y-%m-%d %H:%M") if c.fecha_hasta else "")
            self._set_hist(r, 2, getattr(c, "estado", "PREC"))
            self._set_hist(r, 3, _fmt(getattr(c, "total", 0.0)))
            self._set_hist(r, 4, _fmt(getattr(c, "total_efectivo", 0.0)))
            self._set_hist(r, 5, _fmt(getattr(c, "total_transferencia", 0.0)))
            self._set_hist(r, 6, _fmt(getattr(c, "total_debito", 0.0)))
            self._set_hist(r, 7, _fmt(getattr(c, "total_credito", 0.0)))
            self._set_hist(r, 8, _fmt(getattr(c, "total_ctacte", 0.0)))
            self._set_hist(r, 9, _fmt(getattr(c, "dif_efectivo", 0.0)))
            self._set_hist(r,10, _fmt(getattr(c, "dif_transferencia", 0.0)))
            self._set_hist(r,11, f"D:{_fmt(getattr(c,'dif_debito',0.0))}  TC:{_fmt(getattr(c,'dif_credito',0.0))}  CC:{_fmt(getattr(c,'dif_ctacte',0.0))}")

        # Lógica de visualización "Blind" (Ciego)
        if rows:
            latest = rows[0]
            # Si ya se hizo PRE-CIERRE o CIERRE FINAL, mostramos los datos.
            # El usuario pidió: "que no sepan ... hasta después del pre cierre"
            # O sea, si existe registro (PREC o FINAL), ya pueden ver.
            # Si NO existe registro, no ven nada (estado inicial del método cargar).

            estado = getattr(latest, "estado", "PREC")
            if estado in ("PREC", "FINAL"):
                total_sist = float(getattr(latest, "total", 0.0))
                contado = float(getattr(latest, "contado_efectivo", 0.0)) + float(getattr(latest, "contado_transferencia", 0.0)) + \
                          float(getattr(latest, "contado_debito", 0.0)) + float(getattr(latest, "contado_credito", 0.0)) + \
                          float(getattr(latest, "contado_ctacte", 0.0))
                dif_total = (
                    float(getattr(latest, "dif_efectivo", 0.0)) +
                    float(getattr(latest, "dif_transferencia", 0.0)) +
                    float(getattr(latest, "dif_debito", 0.0)) +
                    float(getattr(latest, "dif_credito", 0.0)) +
                    float(getattr(latest, "dif_ctacte", 0.0))
                )
                self.lbl_sys.setText(f"Sistema: {_fmt(total_sist)}")
                self.lbl_cont.setText(f"Contado: {_fmt(contado)}")
                self.lbl_dif.setText(f"Diferencia: {_fmt(dif_total)}")

                # Resaltar diferencia si es significativa
                if abs(dif_total) > 0.01:
                     self.lbl_dif.setStyleSheet("QLabel { font-size: 16px; padding: 6px; border-radius: 4px; border: 2px solid #dc3545; background-color: #f8d7da; color: #721c24; font-weight: bold; }")
                else:
                     self.lbl_dif.setStyleSheet("QLabel { font-size: 16px; padding: 6px; border-radius: 4px; border: 1px solid #28a745; background-color: #d4edda; color: #155724; font-weight: bold; }")

    # -------------------- flujo de caja --------------------

    def _registrar_conteos(self):
        dlg = ConteoDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        data = dlg.datos()

        start, end = self._rango()

        try:
            with SessionLocal() as s:
                c = CajaService.crear_precierre(s, start, end, data)
                self._precierre_id = c.id
            QMessageBox.information(self, "Caja", "Valores del día guardados. Pre-cierre creado.")
            self.cargar_historial()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar precierre: {e}")

    def _observaciones(self):
        start, end = self._rango()
        with SessionLocal() as s:
            c = (
                s.query(CierreCaja)
                .filter(CierreCaja.fecha_desde >= start, CierreCaja.fecha_hasta <= end)
                .order_by(CierreCaja.id.desc())
                .first()
            )
            if not c:
                QMessageBox.information(self, "Caja", "No hay pre-cierre en este rango.")
                return

            dif_total = (
                float(getattr(c, "dif_efectivo", 0.0)) +
                float(getattr(c, "dif_transferencia", 0.0)) +
                float(getattr(c, "dif_debito", 0.0)) +
                float(getattr(c, "dif_credito", 0.0)) +
                float(getattr(c, "dif_ctacte", 0.0))
            )
            dlg = ObservacionesDialog(self, dif_total=dif_total, texto=(getattr(c, "motivo_diferencia", "") or ""))
            if dlg.exec_() != QDialog.Accepted:
                return
            c.motivo_diferencia = dlg.texto()
            s.commit()

        QMessageBox.information(self, "Caja", "Observación guardada.")

    def _cerrar_caja(self):
        start, end = self._rango()
        with SessionLocal() as s:
            c = (
                s.query(CierreCaja)
                .filter(CierreCaja.fecha_desde >= start, CierreCaja.fecha_hasta <= end)
                .order_by(CierreCaja.id.desc())
                .first()
            )
            if not c:
                QMessageBox.information(self, "Caja", "No hay pre-cierre en este rango.")
                return

            dif_total = (
                float(getattr(c, "dif_efectivo", 0.0)) +
                float(getattr(c, "dif_transferencia", 0.0)) +
                float(getattr(c, "dif_debito", 0.0)) +
                float(getattr(c, "dif_credito", 0.0)) +
                float(getattr(c, "dif_ctacte", 0.0))
            )

            motivo = getattr(c, "motivo_diferencia", "") or ""
            if abs(dif_total) > 0.0001 and not motivo:
                dlg = ObservacionesDialog(self, dif_total=dif_total, texto="")
                if dlg.exec_() != QDialog.Accepted:
                    return
                motivo = dlg.texto()
                if not motivo:
                    QMessageBox.warning(self, "Caja", "El motivo es obligatorio si hay diferencias.")
                    return

            try:
                CajaService.cerrar_caja(s, c.id, motivo)
                QMessageBox.information(self, "Caja", "Caja cerrada. Cierre FINAL guardado.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al cerrar caja: {e}")

        self.cargar_historial()

    def _on_hist_double_click(self, index):
        if not index.isValid():
            return
        row = index.row()
        # El ID esta guardado en columna 0 UserRole
        it = self.tbl_hist.item(row, 0)
        cid = it.data(Qt.UserRole)
        if not cid:
            return

        with SessionLocal() as s:
            cierre = s.get(CierreCaja, cid)
            if cierre:
                dlg = DetalleCajaDialog(cierre, self)
                dlg.exec_()
