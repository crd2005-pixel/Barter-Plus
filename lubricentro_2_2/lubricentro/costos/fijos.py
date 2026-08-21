# costos/fijos.py
import datetime as dt
from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QHBoxLayout, QFormLayout, QLineEdit, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QDateEdit, QLabel, QDoubleSpinBox,
    QDialog, QDialogButtonBox, QCheckBox, QSpinBox
)
from sqlalchemy import and_

from db import SessionLocal, Impuesto, ImpuestoPeriodo, Empleado, SueldoLiquidacion
from db.models.costos import GastoNegocio
from db.models.costos_extra import CreditoNegocio, CreditoCuota, AdelantoSueldo
from services.costo_service import CostoService

# ---------- util fecha ----------
def _to_date(qd: "QDate") -> dt.date:
    return dt.date(qd.year(), qd.month(), qd.day())

def _periodo_label(periodicidad: str, fecha_base: dt.date) -> str:
    y, m = fecha_base.year, fecha_base.month
    p = (periodicidad or "").upper()
    if p == 'MENSUAL':    return f"{y:04d}-{m:02d}"
    if p == 'BIMESTRAL':  return f"{y:04d}-B{((m - 1)//2 + 1):02d}"
    if p == 'TRIMESTRAL': return f"{y:04d}-T{((m - 1)//3 + 1):02d}"
    if p == 'ANUAL':      return f"{y:04d}"
    return f"{y:04d}-{m:02d}"

def _periodo_rango(periodicidad: str, fecha_base: dt.date) -> tuple[dt.date, dt.date]:
    y, m = fecha_base.year, fecha_base.month
    p = (periodicidad or "").upper()
    if p == 'MENSUAL':
        start = dt.date(y, m, 1)
        end = (dt.date(y + (1 if m == 12 else 0), 1 if m == 12 else m + 1, 1)) - dt.timedelta(days=1)
        return start, end
    if p == 'BIMESTRAL':
        m0 = m - ((m - 1) % 2)
        start = dt.date(y, m0, 1)
        m1 = m0 + 1
        end = (dt.date(y + (1 if m1 == 12 else 0), 1 if m1 == 12 else m1 + 1, 1)) - dt.timedelta(days=1)
        return start, end
    if p == 'TRIMESTRAL':
        q_start = m - ((m - 1) % 3)
        start = dt.date(y, q_start, 1)
        m_end = q_start + 2
        end = (dt.date(y + (1 if m_end == 12 else 0), 1 if m_end == 12 else m_end + 1, 1)) - dt.timedelta(days=1)
        return start, end
    if p == 'ANUAL':
        return dt.date(y, 1, 1), dt.date(y, 12, 31)
    return _periodo_rango('MENSUAL', fecha_base)

# ---------- IMPUESTOS ----------
class ImpuestosWidget(QWidget):
    def __init__(self, on_change=None):
        super().__init__()
        self._on_change = on_change
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.inp_nombre = QLineEdit(); self.inp_nombre.setPlaceholderText("Nombre del impuesto (Luz, Agua, Gas, Monotributo...)")
        self.cmb_per = QComboBox(); self.cmb_per.addItems(["MENSUAL","BIMESTRAL","TRIMESTRAL","ANUAL"])
        btn_add = QPushButton("Agregar/Actualizar"); btn_add.clicked.connect(self._add_impuesto)
        top.addWidget(self.inp_nombre, 2); top.addWidget(self.cmb_per); top.addWidget(btn_add)
        layout.addLayout(top)

        gen = QHBoxLayout()
        self.cmb_imp = QComboBox(); self._reload_impuestos()
        self.dt_base = QDateEdit(QDate.currentDate()); self.dt_base.setCalendarPopup(True)
        self.sp_monto = QDoubleSpinBox(); self.sp_monto.setRange(0, 1_000_000); self.sp_monto.setDecimals(2); self.sp_monto.setValue(0.0)
        btn_gen = QPushButton("Generar periodo"); btn_gen.clicked.connect(self._generar_periodo)
        btn_pay = QPushButton("Marcar pagado"); btn_pay.clicked.connect(self._pagar_periodo)
        gen.addWidget(QLabel("Impuesto")); gen.addWidget(self.cmb_imp, 1)
        gen.addWidget(QLabel("Fecha base")); gen.addWidget(self.dt_base)
        gen.addWidget(QLabel("Monto")); gen.addWidget(self.sp_monto)
        gen.addWidget(btn_gen); gen.addWidget(btn_pay)
        layout.addLayout(gen)

        self.tbl = QTableWidget(0, 7)
        self.tbl.setHorizontalHeaderLabels(["ID","Impuesto","Periodo","Inicio","Fin","Monto","Pagado"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tbl)
        self._cargar_periodos()

    def update_all(self):
        self._reload_impuestos()
        self._cargar_periodos()

    def _reload_impuestos(self):
        self.cmb_imp.clear()
        with SessionLocal() as s:
            rows = s.query(Impuesto).filter(Impuesto.activo == True).order_by(Impuesto.nombre.asc()).all()
        for r in rows:
            self.cmb_imp.addItem(f"{r.nombre} ({r.periodicidad})", r.id)

    def _add_impuesto(self):
        nombre = (self.inp_nombre.text() or "").strip()
        per = self.cmb_per.currentText().strip()
        if not nombre:
            QMessageBox.warning(self, "Falta", "Ingrese nombre"); return
        with SessionLocal() as s:
            obj = s.query(Impuesto).filter(Impuesto.nombre.ilike(nombre)).first()
            if obj:
                obj.periodicidad = per
            else:
                s.add(Impuesto(nombre=nombre, periodicidad=per, activo=True))
            s.commit()
        self._reload_impuestos()
        self._cargar_periodos()
        if self._on_change: self._on_change()
        QMessageBox.information(self, "OK", "Guardado.")

    def _generar_periodo(self):
        imp_id = self.cmb_imp.currentData()
        if not imp_id:
            QMessageBox.warning(self, "Impuesto", "Seleccione impuesto"); return
        with SessionLocal() as s:
            imp = s.get(Impuesto, int(imp_id))
            base = _to_date(self.dt_base.date())
            label = _periodo_label(imp.periodicidad, base)
            ini, fin = _periodo_rango(imp.periodicidad, base)
            per = s.query(ImpuestoPeriodo).filter(
                and_(ImpuestoPeriodo.impuesto_id==imp.id, ImpuestoPeriodo.periodo_label==label)
            ).first()
            if per:
                per.fecha_inicio, per.fecha_fin = ini, fin
                per.monto = float(self.sp_monto.value() or 0.0)
                per.periodicidad = imp.periodicidad
            else:
                per = ImpuestoPeriodo(
                    impuesto_id=imp.id,
                    periodo_label=label,
                    fecha_inicio=ini, fecha_fin=fin,
                    monto=float(self.sp_monto.value() or 0.0),
                    pagado=False,
                    periodicidad=imp.periodicidad
                )
                s.add(per)
            s.commit()
        self._cargar_periodos()
        if self._on_change: self._on_change()

    def _pagar_periodo(self):
        row = self.tbl.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Periodo", "Seleccione un periodo"); return
        per_id = int(self.tbl.item(row, 0).text())
        with SessionLocal() as s:
            per = s.get(ImpuestoPeriodo, per_id)
            if per:
                per.pagado = True
                s.commit()
        self._cargar_periodos()
        if self._on_change: self._on_change()

    def _cargar_periodos(self):
        self.tbl.setRowCount(0)
        with SessionLocal() as s:
            rows = s.query(ImpuestoPeriodo).order_by(ImpuestoPeriodo.id.desc()).all()
        for r in rows:
            i = self.tbl.rowCount(); self.tbl.insertRow(i)
            self.tbl.setItem(i, 0, QTableWidgetItem(str(r.id)))
            self.tbl.setItem(i, 1, QTableWidgetItem(str(getattr(r, "impuesto_id", ""))))
            self.tbl.setItem(i, 2, QTableWidgetItem(r.periodo_label or ""))
            self.tbl.setItem(i, 3, QTableWidgetItem(r.fecha_inicio.strftime("%d/%m/%Y") if r.fecha_inicio else ""))
            self.tbl.setItem(i, 4, QTableWidgetItem(r.fecha_fin.strftime("%d/%m/%Y") if r.fecha_fin else ""))
            self.tbl.setItem(i, 5, QTableWidgetItem(f"{float(r.monto or 0):.2f}"))
            self.tbl.setItem(i, 6, QTableWidgetItem("Sí" if r.pagado else "No"))

# ---------- DIALOGO CREDITO ----------
class CreditoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cargar crédito en cuotas (Gasto del negocio)")
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.inp_desc = QLineEdit(); self.inp_desc.setPlaceholderText("Descripción del crédito")
        self.sp_total = QDoubleSpinBox(); self.sp_total.setRange(0, 100_000_000); self.sp_total.setDecimals(2)
        self.sp_cuota = QDoubleSpinBox(); self.sp_cuota.setRange(0, 100_000_000); self.sp_cuota.setDecimals(2)
        self.sp_cant = QSpinBox(); self.sp_cant.setRange(1, 240)
        self.dt_inicio = QDateEdit(QDate.currentDate()); self.dt_inicio.setCalendarPopup(True)
        self.sp_dia = QSpinBox(); self.sp_dia.setRange(1, 31); self.sp_dia.setValue(QDate.currentDate().day())
        form.addRow("Descripción", self.inp_desc)
        form.addRow("Monto total", self.sp_total)
        form.addRow("Monto por cuota", self.sp_cuota)
        form.addRow("Cantidad de cuotas", self.sp_cant)
        form.addRow("Fecha inicio", self.dt_inicio)
        form.addRow("Día de vencimiento (cada mes)", self.sp_dia)
        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def data(self):
        return {
            "descripcion": (self.inp_desc.text() or "").strip(),
            "monto_total": float(self.sp_total.value() or 0.0),
            "monto_cuota": float(self.sp_cuota.value() or 0.0),
            "cant_cuotas": int(self.sp_cant.value() or 1),
            "fecha_inicio": _to_date(self.dt_inicio.date()),
            "dia_venc": int(self.sp_dia.value() or 1),
        }

# ---------- GASTOS DEL NEGOCIO ----------
class GastosNegocioWidget(QWidget):
    def __init__(self, on_change=None):
        super().__init__()
        self._on_change = on_change
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.dt = QDateEdit(QDate.currentDate()); self.dt.setCalendarPopup(True)
        self.inp_cat = QLineEdit(); self.inp_cat.setPlaceholderText("Categoría (Bolsas, Alquiler, Internet, etc.)")
        self.inp_desc = QLineEdit(); self.inp_desc.setPlaceholderText("Descripción")
        self.sp_monto = QDoubleSpinBox(); self.sp_monto.setRange(0, 1_000_000); self.sp_monto.setDecimals(2)
        self.chk_pagado = QCheckBox("Pagado")
        btn = QPushButton("Agregar"); btn.clicked.connect(self._add)
        btn_credito = QPushButton("Crédito…"); btn_credito.clicked.connect(self._credito)
        top.addWidget(self.dt); top.addWidget(self.inp_cat, 1); top.addWidget(self.inp_desc, 2)
        top.addWidget(self.sp_monto); top.addWidget(self.chk_pagado); top.addWidget(btn); top.addWidget(btn_credito)
        layout.addLayout(top)
        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels(["Fecha","Categoría","Descripción","Monto","Pagado","Crédito"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tbl)
        self._load()

    def update_all(self):
        self._load()

    def _load(self):
        self.tbl.setRowCount(0)
        with SessionLocal() as s:
            rows = s.query(GastoNegocio).order_by(GastoNegocio.fecha.desc()).all()
        for r in rows:
            i = self.tbl.rowCount(); self.tbl.insertRow(i)
            self.tbl.setItem(i, 0, QTableWidgetItem(r.fecha.strftime("%d/%m/%Y")))
            self.tbl.setItem(i, 1, QTableWidgetItem(r.categoria or ""))
            self.tbl.setItem(i, 2, QTableWidgetItem(r.descripcion or ""))
            self.tbl.setItem(i, 3, QTableWidgetItem(f"{float(r.monto or 0):.2f}"))
            self.tbl.setItem(i, 4, QTableWidgetItem("Sí" if r.pagado else "No"))
            self.tbl.setItem(i, 5, QTableWidgetItem(str(r.credito_id or "")))

    def _add(self):
        with SessionLocal() as s:
            s.add(GastoNegocio(
                fecha=_to_date(self.dt.date()),
                categoria=(self.inp_cat.text() or "").strip() or None,
                descripcion=(self.inp_desc.text() or "").strip() or None,
                monto=float(self.sp_monto.value() or 0.0),
                pagado=bool(self.chk_pagado.isChecked()),
                credito_id=None
            ))
            s.commit()
        self._load()
        if self._on_change: self._on_change()

    def _credito(self):
        dlg = CreditoDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        data = dlg.data()
        if not data["descripcion"] or data["monto_total"] <= 0 or data["monto_cuota"] <= 0 or data["cant_cuotas"] <= 0:
            QMessageBox.warning(self, "Crédito", "Complete correctamente los datos."); return
        fecha_ini = data["fecha_inicio"]; dia_venc = data["dia_venc"]
        cuotas = []
        y, m = fecha_ini.year, fecha_ini.month
        for n in range(data["cant_cuotas"]):
            mm = m + n
            yy = y + (mm - 1) // 12
            mm = ((mm - 1) % 12) + 1
            last_day = [31, 29 if (yy % 4 == 0 and (yy % 100 != 1 or yy % 400 == 0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mm - 1]
            day = min(dia_venc, last_day)
            cuotas.append(dt.date(yy, mm, day))
        with SessionLocal() as s:
            cred = CreditoNegocio(
                descripcion=data["descripcion"],
                monto_total=float(data["monto_total"]),
                monto_cuota=float(data["monto_cuota"]),
                cant_cuotas=int(data["cant_cuotas"]),
                fecha_inicio=fecha_ini,
                dia_vencimiento=dia_venc
            )
            s.add(cred); s.flush()
            for fv in cuotas:
                s.add(CreditoCuota(credito_id=cred.id, fecha_venc=fv, monto=float(data["monto_cuota"]), pagado=False))
                s.add(GastoNegocio(
                    fecha=fv, categoria="Crédito", descripcion=f"{data['descripcion']} - cuota",
                    monto=float(data["monto_cuota"]), pagado=False, credito_id=cred.id
                ))
            s.commit()
        self._load()
        if self._on_change: self._on_change()
        QMessageBox.information(self, "Crédito", "Cuotas generadas y asentadas por mes.")

# ---------- SUELDOS ----------
class SueldosWidget(QWidget):
    def __init__(self, on_change=None):
        super().__init__()
        self._on_change = on_change
        layout = QVBoxLayout(self)
        alta = QHBoxLayout()
        self.inp_emp = QLineEdit(); self.inp_emp.setPlaceholderText("Nombre empleado")
        self.inp_cuil = QLineEdit(); self.inp_cuil.setPlaceholderText("CUIL (opcional)")
        btn_emp = QPushButton("Agregar empleado"); btn_emp.clicked.connect(self._add_empleado)
        alta.addWidget(self.inp_emp, 1); alta.addWidget(self.inp_cuil); alta.addWidget(btn_emp)
        layout.addLayout(alta)
        liq = QHBoxLayout()
        self.cmb_emp = QComboBox(); self._reload_emps()
        self.dt_per = QDateEdit(QDate.currentDate()); self.dt_per.setCalendarPopup(True)
        self.sp_bruto = QDoubleSpinBox(); self.sp_bruto.setRange(0, 10_000_000); self.sp_bruto.setDecimals(2)
        self.sp_desc = QDoubleSpinBox(); self.sp_desc.setRange(0, 10_000_000); self.sp_desc.setDecimals(2)
        self.chk_pagado = QCheckBox("Pagado")
        btn_save = QPushButton("Guardar liquidación"); btn_save.clicked.connect(self._guardar_liq)
        liq.addWidget(QLabel("Empleado")); liq.addWidget(self.cmb_emp, 1)
        liq.addWidget(QLabel("Periodo base")); liq.addWidget(self.dt_per)
        liq.addWidget(QLabel("Bruto")); liq.addWidget(self.sp_bruto)
        liq.addWidget(QLabel("Descuentos")); liq.addWidget(self.sp_desc)
        liq.addWidget(self.chk_pagado); liq.addWidget(btn_save)
        layout.addLayout(liq)
        adel = QHBoxLayout()
        self.dt_adv = QDateEdit(QDate.currentDate()); self.dt_adv.setCalendarPopup(True)
        self.sp_adv = QDoubleSpinBox(); self.sp_adv.setRange(0, 10_000_000); self.sp_adv.setDecimals(2)
        self.chk_adv_pagado = QCheckBox("Pagado")
        btn_adv = QPushButton("Cargar adelanto"); btn_adv.clicked.connect(self._guardar_adelanto)
        adel.addWidget(QLabel("Fecha adelanto")); adel.addWidget(self.dt_adv)
        adel.addWidget(QLabel("Monto")); adel.addWidget(self.sp_adv)
        adel.addWidget(self.chk_adv_pagado); adel.addWidget(btn_adv)
        layout.addLayout(adel)
        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels(["Empleado","Periodo","Fecha pago","Bruto","Neto","Pagado"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tbl)
        self._load_liqs()
        self.tbl_adv = QTableWidget(0, 4)
        self.tbl_adv.setHorizontalHeaderLabels(["Fecha","Empleado","Monto","Pagado"])
        self.tbl_adv.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(QLabel("Adelantos"))
        layout.addWidget(self.tbl_adv)
        self._load_adelantos()

    def update_all(self):
        self._reload_emps()
        self._load_liqs()
        self._load_adelantos()

    def _periodo_mensual_label(self, d: dt.date) -> str:
        return f"{d.year:04d}-{d.month:02d}"

    def _reload_emps(self):
        self.cmb_emp.clear()
        with SessionLocal() as s:
            rows = s.query(Empleado).filter(Empleado.activo == True).order_by(Empleado.nombre.asc()).all()
        for r in rows:
            self.cmb_emp.addItem(r.nombre, r.id)

    def _add_empleado(self):
        nombre = (self.inp_emp.text() or "").strip()
        if not nombre:
            QMessageBox.warning(self, "Falta", "Ingrese nombre"); return
        with SessionLocal() as s:
            s.add(Empleado(nombre=nombre, cuil=(self.inp_cuil.text() or "").strip() or None, activo=True))
            s.commit()
        self._reload_emps()
        self.inp_emp.clear(); self.inp_cuil.clear()
        QMessageBox.information(self, "OK", "Empleado agregado.")

    def _guardar_liq(self):
        emp_id = self.cmb_emp.currentData()
        if not emp_id:
            QMessageBox.warning(self, "Empleado", "Seleccione empleado"); return
        base = _to_date(self.dt_per.date())
        label = self._periodo_mensual_label(base)
        bruto = float(self.sp_bruto.value()); desc = float(self.sp_desc.value()); neto = bruto - desc
        with SessionLocal() as s:
            liq = s.query(SueldoLiquidacion).filter(
                and_(SueldoLiquidacion.empleado_id == int(emp_id), SueldoLiquidacion.periodo_label == label)
            ).first()
            if not liq:
                liq = SueldoLiquidacion(empleado_id=int(emp_id), periodo_label=label)
                s.add(liq)
            liq.bruto = bruto
            liq.descuentos = desc
            liq.neto = neto
            liq.fecha_pago = base if self.chk_pagado.isChecked() else None
            s.commit()
        self._load_liqs()
        if self._on_change: self._on_change()

    def _load_liqs(self):
        self.tbl.setRowCount(0)
        with SessionLocal() as s:
            rows = s.query(SueldoLiquidacion).order_by(SueldoLiquidacion.periodo_label.desc()).all()
        for r in rows:
            i = self.tbl.rowCount(); self.tbl.insertRow(i)
            self.tbl.setItem(i, 0, QTableWidgetItem(str(r.empleado_id)))
            self.tbl.setItem(i, 1, QTableWidgetItem(r.periodo_label or ""))
            self.tbl.setItem(i, 2, QTableWidgetItem(r.fecha_pago.strftime("%d/%m/%Y") if r.fecha_pago else ""))
            self.tbl.setItem(i, 3, QTableWidgetItem(f"{float(r.bruto or 0):.2f}"))
            self.tbl.setItem(i, 4, QTableWidgetItem(f"{float(r.neto or 0):.2f}"))
            self.tbl.setItem(i, 5, QTableWidgetItem("Sí" if r.fecha_pago else "No"))

    def _guardar_adelanto(self):
        emp_id = self.cmb_emp.currentData()
        if not emp_id:
            QMessageBox.warning(self, "Empleado", "Seleccione empleado"); return
        with SessionLocal() as s:
            s.add(AdelantoSueldo(
                empleado_id=int(emp_id),
                fecha=_to_date(self.dt_adv.date()),
                monto=float(self.sp_adv.value() or 0.0),
                pagado=bool(self.chk_adv_pagado.isChecked())
            ))
            s.commit()
        self._load_adelantos()
        if self._on_change: self._on_change()

    def _load_adelantos(self):
        self.tbl_adv.setRowCount(0)
        with SessionLocal() as s:
            rows = s.query(AdelantoSueldo).order_by(AdelantoSueldo.fecha.desc()).all()
        for r in rows:
            i = self.tbl_adv.rowCount(); self.tbl_adv.insertRow(i)
            self.tbl_adv.setItem(i, 0, QTableWidgetItem(r.fecha.strftime("%d/%m/%Y")))
            self.tbl_adv.setItem(i, 1, QTableWidgetItem(str(r.empleado_id)))
            self.tbl_adv.setItem(i, 2, QTableWidgetItem(f"{float(r.monto or 0):.2f}"))
            self.tbl_adv.setItem(i, 3, QTableWidgetItem("Sí" if r.pagado else "No"))

class CostosFijosTab(QWidget):
    def __init__(self, on_change=None):
        super().__init__()
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(ImpuestosWidget(on_change=on_change), "Impuestos")
        self.tabs.addTab(GastosNegocioWidget(on_change=on_change), "Gastos del negocio")
        self.tabs.addTab(SueldosWidget(on_change=on_change), "Sueldos")
        layout.addWidget(self.tabs)

    def update_all(self):
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if hasattr(w, "update_all"):
                w.update_all()
