# -*- coding: utf-8 -*-
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QDialog,
    QFormLayout, QCheckBox
)
from db import SessionLocal, Cliente

# --- helpers: leer/escribir "especial" de forma robusta ---
_FLAG_NAMES = ("especial", "es_especial", "cliente_especial", "vip", "is_special")
_DESC_NAMES = ("descuento", "descuento_pct", "descuento_porcentaje",
               "porc_descuento", "porcentaje_descuento")
_TIPO_NAMES = ("tipo_cliente", "categoria", "tipo")

def _to_bool_any(v):
    try:
        if isinstance(v, bool): return v
        if isinstance(v, (int, float)): return int(v) != 0
        s = str(v).strip().lower()
        return s in ("1","s","si","sí","y","yes","true","t","especial")
    except Exception:
        return False

def _get_attr(obj, names):
    for n in names:
        if hasattr(obj, n):
            return n, getattr(obj, n)
    return None, None

def _get_especial(cli) -> bool:
    # 1) flags
    for n in _FLAG_NAMES:
        if hasattr(cli, n) and _to_bool_any(getattr(cli, n)):
            return True
    # 2) descuentos
    for n in _DESC_NAMES:
        if hasattr(cli, n):
            try:
                if float(getattr(cli, n) or 0) >= 9.9:
                    return True
            except Exception:
                pass
    # 3) tipo
    for n in _TIPO_NAMES:
        if hasattr(cli, n) and str(getattr(cli, n) or "").strip().lower().startswith("esp"):
            return True
    return False

def _set_especial(cli, checked: bool):
    wrote = False
    # flags
    for n in _FLAG_NAMES:
        if hasattr(cli, n):
            cur = getattr(cli, n)
            try:
                if isinstance(cur, bool): setattr(cli, n, bool(checked))
                elif isinstance(cur, (int, float)): setattr(cli, n, 1 if checked else 0)
                elif isinstance(cur, str):
                    up = cur.strip().upper()
                    if up in ("S","N"): setattr(cli, n, "S" if checked else "N")
                    elif up in ("1","0"): setattr(cli, n, "1" if checked else "0")
                    else: setattr(cli, n, "1" if checked else "0")
                else: setattr(cli, n, 1 if checked else 0)
                wrote = True
                break
            except Exception:
                pass
    if not wrote:
        try:
            setattr(cli, "especial", 1 if checked else 0); wrote = True
        except Exception:
            pass
    # descuentos (si existen)
    for n in _DESC_NAMES:
        if hasattr(cli, n):
            try: setattr(cli, n, 10.0 if checked else 0.0)
            except Exception: pass
    # tipo (si existe)
    for n in _TIPO_NAMES:
        if hasattr(cli, n):
            try: setattr(cli, n, "especial" if checked else "comun")
            except Exception: pass

# --- diálogo de edición ---
class ClienteEditDialog(QDialog):
    def __init__(self, parent=None, cliente_id=None):
        super().__init__(parent)
        self.setWindowTitle("Cliente")
        self.resize(520, 220)
        self._id = cliente_id
        self.saved_id = None

        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.ed_nombre = QLineEdit()
        self.ed_doc = QLineEdit()
        self.ed_tel = QLineEdit()
        self.ed_mail = QLineEdit()
        self.ed_dir = QLineEdit()
        self.chk_especial = QCheckBox("Cliente especial (-10%)")

        form.addRow("Nombre:", self.ed_nombre)
        form.addRow("CUIT/DNI:", self.ed_doc)
        form.addRow("Teléfono:", self.ed_tel)
        form.addRow("Email:", self.ed_mail)
        form.addRow("Dirección:", self.ed_dir)
        form.addRow("", self.chk_especial)
        lay.addLayout(form)

        bar = QHBoxLayout(); bar.addStretch()
        btn_ok = QPushButton("Guardar"); btn_ok.clicked.connect(self._save)
        btn_cancel = QPushButton("Cancelar"); btn_cancel.clicked.connect(self.reject)
        bar.addWidget(btn_ok); bar.addWidget(btn_cancel)
        lay.addLayout(bar)

        if self._id: self._load()

    def _load(self):
        with SessionLocal() as s:
            c = s.query(Cliente).get(self._id)
            if not c: return
            self.ed_nombre.setText(getattr(c,"nombre","") or "")
            self.ed_doc.setText(getattr(c,"cuit_dni","") or "")
            self.ed_tel.setText(getattr(c,"telefono","") or "")
            self.ed_mail.setText(getattr(c,"email","") or "")
            self.ed_dir.setText(getattr(c,"direccion","") or "")
            self.chk_especial.setChecked(_get_especial(c))

    def _save(self):
        nombre = (self.ed_nombre.text() or "").strip()
        if not nombre:
            QMessageBox.information(self,"Cliente","Ingresá un nombre."); return
        try:
            with SessionLocal() as s:
                if self._id:
                    c = s.query(Cliente).get(self._id)
                    if not c:
                        QMessageBox.information(self,"Cliente","Cliente inexistente."); return
                else:
                    c = Cliente(); s.add(c)

                try: c.nombre = nombre
                except Exception: pass
                try: c.cuit_dni = (self.ed_doc.text() or "").strip()
                except Exception: pass
                try: c.telefono = (self.ed_tel.text() or "").strip()
                except Exception: pass
                try: c.email = (self.ed_mail.text() or "").strip()
                except Exception: pass
                try: c.direccion = (self.ed_dir.text() or "").strip()
                except Exception: pass

                _set_especial(c, self.chk_especial.isChecked())

                s.commit()
                self.saved_id = getattr(c,"id",None)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self,"Cliente",f"No se pudo guardar.\n{e}")

    @staticmethod
    def edit(parent=None, cliente_id=None):
        dlg = ClienteEditDialog(parent=parent, cliente_id=cliente_id)
        ok = dlg.exec_()
        return ok == dlg.Accepted, dlg.saved_id

# --- Tab ---
class ClientesTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.inp_buscar = QLineEdit(); self.inp_buscar.setPlaceholderText("Buscar por nombre o CUIT/DNI…")
        btn_refresh = QPushButton("Actualizar"); btn_refresh.clicked.connect(self.cargar)
        top.addWidget(QLabel("Buscar:")); top.addWidget(self.inp_buscar,1); top.addWidget(btn_refresh)
        layout.addLayout(top)

        self.tbl = QTableWidget(0,6)
        self.tbl.setHorizontalHeaderLabels(["ID","Nombre","CUIT/DNI","Teléfono","Email","Especial"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.setSelectionBehavior(self.tbl.SelectRows)
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers)
        self.tbl.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.tbl)

        bar = QHBoxLayout(); bar.addStretch()
        btn_new = QPushButton("Nuevo"); btn_edit = QPushButton("Editar"); btn_del = QPushButton("Borrar")
        btn_new.clicked.connect(self._nuevo); btn_edit.clicked.connect(self._editar); btn_del.clicked.connect(self._borrar)
        bar.addWidget(btn_new); bar.addWidget(btn_edit); bar.addWidget(btn_del)
        layout.addLayout(bar)

        self.inp_buscar.textChanged.connect(self.cargar)
        self.cargar()

    def cargar(self):
        pat = (self.inp_buscar.text() or "").strip()
        self.tbl.setRowCount(0)
        with SessionLocal() as s:
            q = s.query(Cliente)
            if pat:
                try:
                    q = q.filter((Cliente.nombre.ilike(f"%{pat}%")) | (Cliente.cuit_dni.ilike(f"%{pat}%")))
                except Exception:
                    q = q.filter((Cliente.nombre.contains(pat)) | (Cliente.cuit_dni.contains(pat)))
            rows = q.order_by(Cliente.nombre.asc()).all()
        for r in rows:
            rid = getattr(r,"id",None)
            nombre = getattr(r,"nombre","") or ""
            doc = getattr(r,"cuit_dni","") or ""
            tel = getattr(r,"telefono","") or ""
            mail = getattr(r,"email","") or ""
            esp = "Sí" if _get_especial(r) else "No"
            i = self.tbl.rowCount(); self.tbl.insertRow(i)
            self.tbl.setItem(i,0,QTableWidgetItem(str(rid if rid is not None else "")))
            self.tbl.setItem(i,1,QTableWidgetItem(nombre))
            self.tbl.setItem(i,2,QTableWidgetItem(doc))
            self.tbl.setItem(i,3,QTableWidgetItem(tel))
            self.tbl.setItem(i,4,QTableWidgetItem(mail))
            self.tbl.setItem(i,5,QTableWidgetItem(esp))

    def _row_sel(self):
        rows = self.tbl.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    def _id_sel(self):
        r = self._row_sel()
        if r is None: return None
        try: return int(self.tbl.item(r,0).text())
        except Exception: return None

    def _on_double_click(self, row, _col):
        try: cid = int(self.tbl.item(row,0).text())
        except Exception: return
        ok,_ = ClienteEditDialog.edit(self, cliente_id=cid)
        if ok: self.cargar()

    def _nuevo(self):
        ok,_ = ClienteEditDialog.edit(self, cliente_id=None)
        if ok: self.cargar()

    def _editar(self):
        cid = self._id_sel()
        if not cid:
            QMessageBox.information(self,"Clientes","Seleccioná un cliente."); return
        ok,_ = ClienteEditDialog.edit(self, cliente_id=cid)
        if ok: self.cargar()

    def _borrar(self):
        cid = self._id_sel()
        if not cid:
            QMessageBox.information(self,"Clientes","Seleccioná un cliente."); return
        if QMessageBox.question(self,"Borrar","¿Eliminar el cliente seleccionado?",
                                QMessageBox.Yes|QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            with SessionLocal() as s:
                c = s.query(Cliente).get(cid)
                if not c:
                    QMessageBox.information(self,"Clientes","Cliente inexistente."); return
                s.delete(c); s.commit()
        except Exception as e:
            QMessageBox.critical(self,"Clientes",f"No se pudo borrar.\n{e}"); return
        self.cargar(); QMessageBox.information(self,"Clientes","Eliminado.")
