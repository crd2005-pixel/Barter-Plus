# -*- coding: utf-8 -*-
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QEvent
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QLabel,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QFrame,
    QCheckBox, QWidget, QMessageBox, QCompleter
)

from db import SessionLocal, Cliente, Producto
from services.config_service import ConfigService

# ---------- util interno ----------
def _to_bool_any(v):
    try:
        if isinstance(v, bool): return v
        if isinstance(v, (int, float)): return int(v) != 0
        s = str(v).strip().lower()
        return s in ("1","s","si","sí","y","yes","true","t")
    except Exception:
        return False

def _fmt(n):
    try:
        return f"${float(n):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "$0,00"

def _set_especial_robusto(cli, checked: bool):
    # Intentar usar el campo 'tipo' si no existen campos específicos
    if hasattr(cli, "tipo") and checked:
        try:
            cli.tipo = "Especial"
        except Exception:
            pass
    elif hasattr(cli, "tipo") and not checked:
        # Si desmarcan, volver a minorista (default)
        try:
            if str(cli.tipo).lower() == "especial":
                cli.tipo = "minorista"
        except Exception:
            pass

    # Intentar también campos legacy o dinámicos
    nombres = ("especial","es_especial","cliente_especial","vip","is_special")
    escrito = False
    for n in nombres:
        if hasattr(cli, n):
            try:
                cur = getattr(cli, n)
                # ... (rest of logic mostly generic)
                setattr(cli, n, 1 if checked else 0)
                escrito = True
                break
            except Exception:
                pass

# -----------------------------
# ClienteDialog
# -----------------------------
class ClienteDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo Cliente")
        self.resize(380, 300)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.inp_nombre = QLineEdit()
        self.inp_cuit = QLineEdit()
        self.inp_dir = QLineEdit()
        self.inp_tel = QLineEdit()
        self.inp_mail = QLineEdit()
        self.chk_especial = QCheckBox("Cliente especial (-10%)")

        form.addRow("Nombre:", self.inp_nombre)
        form.addRow("CUIT/DNI:", self.inp_cuit)
        form.addRow("Dirección:", self.inp_dir)
        form.addRow("Teléfono:", self.inp_tel)
        form.addRow("Email:", self.inp_mail)
        form.addRow("", self.chk_especial)
        layout.addLayout(form)

        box = QHBoxLayout()
        self.btn_ok = QPushButton("Guardar")
        self.btn_cancel = QPushButton("Cancelar")
        box.addStretch(); box.addWidget(self.btn_ok); box.addWidget(self.btn_cancel)
        layout.addLayout(box)

        self.btn_ok.clicked.connect(self._save)
        self.btn_cancel.clicked.connect(self.reject)

        self._datos = {}

    def _save(self):
        nombre = (self.inp_nombre.text() or "").strip()
        cuit = (self.inp_cuit.text() or "").strip()
        if not nombre: return

        with SessionLocal() as s:
            cli = Cliente(
                nombre=nombre,
                cuit_dni=cuit,
                direccion=(self.inp_dir.text() or "").strip(),
                telefono=(self.inp_tel.text() or "").strip(),
                email=(self.inp_mail.text() or "").strip()
            )
            s.add(cli); s.flush()
            _set_especial_robusto(cli, self.chk_especial.isChecked())
            s.commit()

        self._datos = {
            "nombre": nombre, "cuit_dni": cuit,
            "direccion": (self.inp_dir.text() or "").strip(),
            "telefono": (self.inp_tel.text() or "").strip(),
            "email": (self.inp_mail.text() or "").strip(),
            "especial": 1 if self.chk_especial.isChecked() else 0
        }
        self.accept()

    def datos(self):
        return self._datos




# -----------------------------
# SlidePanel producto manual
# -----------------------------
class SlidePanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setStyleSheet("""
            QFrame#SlidePanel {
                background-color: #202124;
                border: 1px solid #3c4043;
                border-radius: 6px;
            }
            QLabel { color: #E8EAED; }
            QLineEdit {
                background: #2b2f33;
                color: #E8EAED;
                border: 1px solid #5f6368;
                border-radius: 4px;
                padding: 4px 6px;
            }
            QPushButton {
                background: #303134;
                color: #E8EAED;
                border: 1px solid #5f6368;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QPushButton:hover { border-color: #8ab4f8; }
            QPushButton:pressed { background: #202124; }
        """)
        self.setObjectName("SlidePanel")

        self._expanded = False
        self._lock = False
        self._hide_connected = False
        self._h_collapsed = 30
        self._h_expanded = 92
        self.setMaximumHeight(self._h_collapsed)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(6)

        hdr = QHBoxLayout()
        self.lbl_title = QLabel("Producto manual / externo")
        self.lbl_toggle = QLabel("▸")
        hdr.addWidget(self.lbl_title)
        hdr.addStretch()
        hdr.addWidget(self.lbl_toggle)
        root.addLayout(hdr)

        self.content = QWidget()
        cont = QHBoxLayout(self.content)
        cont.setContentsMargins(0, 0, 0, 0)
        cont.setSpacing(8)

        self.ed_desc = QLineEdit(); self.ed_desc.setPlaceholderText("Descripción")
        self.ed_cant = QLineEdit("1"); self.ed_cant.setPlaceholderText("Cant.")
        self.ed_prec = QLineEdit("0"); self.ed_prec.setPlaceholderText("Precio")
        self.btn_add = QPushButton("Agregar manual")

        cont.addWidget(QLabel("Descripción:"))
        cont.addWidget(self.ed_desc, 2)
        cont.addWidget(QLabel("Cant.:"))
        cont.addWidget(self.ed_cant, 1)
        cont.addWidget(QLabel("Precio:"))
        cont.addWidget(self.ed_prec, 1)
        cont.addWidget(self.btn_add, 0)

        root.addWidget(self.content)
        self.content.setVisible(False)

        self.anim = QPropertyAnimation(self, b"maximumHeight")
        self.anim.setDuration(180)
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)

        for w in (self.ed_desc, self.ed_cant, self.ed_prec):
            w.installEventFilter(self)

    def eventFilter(self, obj, ev):
        et = ev.type()
        if et == QEvent.FocusIn:
            self._lock = True
        elif et == QEvent.FocusOut:
            self._lock = self._is_outside()
        return super().eventFilter(obj, ev)

    def _is_outside(self):
        try:
            return not self.rect().contains(self.mapFromGlobal(QCursor.pos()))
        except Exception:
            return False

    def _expand(self):
        if self._expanded:
            return
        self._expanded = True
        self.content.setVisible(True)
        self.lbl_toggle.setText("▾")
        self._animate_to(self._h_expanded)

    def _collapse(self):
        if not self._expanded:
            return
        if self._lock:
            return
        self._expanded = False
        self.lbl_toggle.setText("▸")
        self._animate_to(self._h_collapsed, hide_after=True)

    def _animate_to(self, h, hide_after=False):
        try:
            self.anim.stop()
            self.anim.setStartValue(self.maximumHeight())
            self.anim.setEndValue(h)
            if hide_after and not self._hide_connected:
                self.anim.finished.connect(self._hide_content_once)
                self._hide_connected = True
            self.anim.start()
        except Exception:
            self.setMaximumHeight(h)
            if hide_after:
                self._hide_content_once()

    def _hide_content_once(self):
        self.content.setVisible(False)
        try:
            if self._hide_connected:
                self.anim.finished.disconnect(self._hide_content_once)
        except Exception:
            pass
        self._hide_connected = False

    def enterEvent(self, event):
        if not self._lock:
            self._expand()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._lock:
            self._collapse()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if self._expanded:
            self._collapse()
        else:
            self._expand()
        super().mousePressEvent(event)


# -----------------------------
# Buscador de clientes con completer
# -----------------------------
class ClienteSearchHelper:
    def __init__(self, line_edit: QLineEdit):
        self.le = line_edit
        self.completer = QCompleter([], self.le)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        try:
            self.completer.setFilterMode(Qt.MatchContains)
        except Exception:
            pass
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.le.setCompleter(self.completer)

        self._strings = []
        self._map = {}   # display -> (id, nombre, doc, tel)
        self.current_id = None

        self.le.textEdited.connect(self._refresh)

        try:
            self.completer.activated[str].connect(self._on_pick)
        except Exception:
            self.completer.activated.connect(lambda _: self._on_pick(self.le.text()))

    def _on_pick(self, display):
        data = self._map.get(display)
        if data:
            _id, nombre, _doc, _tel = data
            self.current_id = _id
            self.le.setText(nombre)

    def _refresh(self, txt):
        pat = (txt or "").strip()
        self.current_id = None
        with SessionLocal() as s:
            q = s.query(Cliente)
            if pat:
                try:
                    q = q.filter(
                        (Cliente.nombre.ilike(f"%{pat}%")) |
                        (Cliente.cuit_dni.ilike(f"%{pat}%"))
                    )
                except Exception:
                    q = q.filter(
                        (Cliente.nombre.contains(pat)) |
                        (Cliente.cuit_dni.contains(pat))
                    )
            rows = q.order_by(Cliente.nombre.asc()).limit(30).all()

        self._strings = []
        self._map.clear()
        for r in rows:
            nombre = getattr(r, "nombre", "") or ""
            doc = getattr(r, "cuit_dni", "") or ""
            tel = getattr(r, "telefono", "") or ""
            display = f"{nombre} — {doc} — {tel}"
            self._strings.append(display)
            self._map[display] = (getattr(r, "id", None), nombre, doc, tel)

        try:
            from PyQt5.QtCore import QStringListModel
            self.completer.setModel(QStringListModel(self._strings, self.completer))
        except Exception:
            pass




# -----------------------------
# Pagos combinados (restaurado)
# -----------------------------
class PagosMixtosDialog(QDialog):
    def __init__(self, parent=None, total_actual=0.0):
        super().__init__(parent)
        self.setWindowTitle("Pagos combinados")
        self.resize(720, 460)

        self.total_base = float(total_actual or 0.0)
        self._tarj_cfg = {}
        self._load_tarjeta_cfg()

        layout = QVBoxLayout(self)

        form = QHBoxLayout()
        self.cb_tipo = QComboBox()
        self.cb_tipo.addItems([
            "Efectivo", "Transferencia", "Débito", "Crédito", "Tarjeta", "Cheque", "Cuenta Corriente"
        ])

        self.cb_tarjeta = QComboBox()
        self.cb_cuotas = QComboBox()
        self._populate_tarjeta_marcas()
        self._populate_cuotas()

        self.inp_monto = QLineEdit(); self.inp_monto.setPlaceholderText("Monto base")
        self.inp_lote  = QLineEdit(); self.inp_lote.setPlaceholderText("Lote")
        self.inp_cupon = QLineEdit(); self.inp_cupon.setPlaceholderText("Cupón")

        self.btn_add = QPushButton("Agregar")
        self.btn_add.clicked.connect(self._add_pago)

        form.addWidget(QLabel("Forma:"));   form.addWidget(self.cb_tipo)
        form.addWidget(QLabel("Tarjeta:")); form.addWidget(self.cb_tarjeta)
        form.addWidget(QLabel("Cuotas:"));  form.addWidget(self.cb_cuotas)
        form.addWidget(QLabel("Monto:"));   form.addWidget(self.inp_monto)
        form.addWidget(QLabel("Lote:"));    form.addWidget(self.inp_lote)
        form.addWidget(QLabel("Cupón:"));   form.addWidget(self.inp_cupon)
        form.addWidget(self.btn_add)

        layout.addLayout(form)

        self.tbl = QTableWidget(0, 3)
        self.tbl.setHorizontalHeaderLabels(["Forma", "Detalle", "Monto (final)"])
        layout.addWidget(self.tbl)

        bar = QHBoxLayout()
        self.lbl_rest = QLabel(_fmt(self.total_base))
        self.lbl_rest.setStyleSheet("font-size:24px; font-weight:600; color:#0a58ca;")
        bar.addWidget(QLabel("Restante:"))
        bar.addWidget(self.lbl_rest)
        bar.addStretch()
        btn_ok = QPushButton("Aceptar")
        btn_ok.setStyleSheet("font-size:18px; padding:8px 14px;")
        btn_ok.clicked.connect(self.accept)
        bar.addWidget(btn_ok)
        layout.addLayout(bar)

        self._pagos = []
        self.out_data = []

        self.cb_tipo.currentTextChanged.connect(self._toggle_tarjeta)
        self.cb_tarjeta.currentTextChanged.connect(self._populate_cuotas)

        self._toggle_tarjeta(self.cb_tipo.currentText())
        self._recalc_restante()

    def _load_tarjeta_cfg(self):
        with SessionLocal() as s:
            self._tarj_cfg = ConfigService.get_tarjeta_coefs(s)

    def _populate_tarjeta_marcas(self):
        self.cb_tarjeta.blockSignals(True)
        self.cb_tarjeta.clear()
        self.cb_tarjeta.addItems(sorted(self._tarj_cfg.keys()))
        self.cb_tarjeta.blockSignals(False)

    def _populate_cuotas(self):
        self.cb_cuotas.blockSignals(True)
        self.cb_cuotas.clear()
        marca = self.cb_tarjeta.currentText()
        cuotas_list = sorted(self._tarj_cfg.get(marca, {}).keys()) or [1,3,6,12]
        self.cb_cuotas.addItems([str(c) for c in cuotas_list])
        self.cb_cuotas.blockSignals(False)

    def _toggle_tarjeta(self, text):
        low = text.lower()
        is_tarj = low in ("tarjeta", "crédito", "credito")
        is_deb  = low in ("débito", "debito")
        self.cb_tarjeta.setEnabled(is_tarj)
        self.cb_cuotas.setEnabled(is_tarj)
        # Lote/Cupón para tarjeta o débito
        en = is_tarj or is_deb
        for w in (self.inp_lote, self.inp_cupon):
            w.setEnabled(en); w.setVisible(en)
        # Ocultar tarjeta/cuotas cuando es débito
        if is_deb:
            self.cb_tarjeta.setVisible(False); self.cb_cuotas.setVisible(False)
        else:
            self.cb_tarjeta.setVisible(True);  self.cb_cuotas.setVisible(True)

    def _f(self, txt, d=0.0):
        try:
            return float((txt or "").replace(" ", "").replace("$", "").replace(",", "."))
        except Exception:
            return d

    def _recargo_pct(self):
        try:
            marca = self.cb_tarjeta.currentText()
            cuotas = int(self.cb_cuotas.currentText() or "1")
            return float(self._tarj_cfg.get(marca, {}).get(cuotas, 0.0))
        except Exception:
            return 0.0

    def _add_pago(self):
        tipo = self.cb_tipo.currentText()
        base = self._f(self.inp_monto.text(), 0.0)
        if base <= 0:
            return

        low = tipo.lower()
        det = ""
        final = base
        lote = (self.inp_lote.text() or "").strip()
        cupon = (self.inp_cupon.text() or "").strip()

        if low in ("tarjeta", "crédito", "credito"):
            pct = self._recargo_pct()
            final = base * (1.0 + pct / 100.0)
            det = f"{self.cb_tarjeta.currentText()} {self.cb_cuotas.currentText()} cuotas (+{pct:.1f}%)"
            if lote or cupon:
                det = (det + "  " if det else "") + f"Lote {lote} Cupón {cupon}".strip()
        elif low in ("débito", "debito"):
            final = base  # sin recargo
            if lote or cupon:
                det = f"Lote {lote} Cupón {cupon}".strip()

        r = self.tbl.rowCount()
        self.tbl.insertRow(r)
        self.tbl.setItem(r, 0, QTableWidgetItem(tipo))
        self.tbl.setItem(r, 1, QTableWidgetItem(det))
        self.tbl.setItem(r, 2, QTableWidgetItem(f"{final:.2f}"))

        self._pagos.append({"tipo": tipo, "detalle": det, "base": base, "final": final})
        self.inp_monto.clear(); self.inp_lote.clear(); self.inp_cupon.clear()
        self._recalc_restante()

    def _recalc_restante(self):
        pagado_base = sum(p["base"] for p in self._pagos)
        restante = max(self.total_base - pagado_base, 0.0)
        self.lbl_rest.setText(_fmt(restante))

    def accept(self):
        # Normaliza a tuplas (medio, monto_final, detalle)
        out = []
        for p in self._pagos:
            out.append((p["tipo"], float(p.get("final",0.0) or 0.0), p.get("detalle","")))
        self.out_data = out
        super().accept()
