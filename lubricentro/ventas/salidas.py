# -*- coding: utf-8 -*-
# Subpestaña "Salidas": gastos/impuestos/pagos a proveedores + cobros Cta Cte clientes.
# Compatible con tu ZIP 1.6.4.x: ClienteSearchHelper(line_edit: QLineEdit)

import datetime as dt

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDateEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QFormLayout,
    QLineEdit, QComboBox, QTextEdit, QGroupBox
)

from db import SessionLocal, Impuesto, Empleado
from db.models.clientes import Cliente, CuentaCorrienteCliente
from services.salidas_service import SalidasService

# ClienteSearchHelper oficial (recibe QLineEdit). Si no existe, fallback vacío.
try:
    from ventas.nueva_venta_complemento import ClienteSearchHelper
except Exception:
    class ClienteSearchHelper:
        def __init__(self, line_edit: QLineEdit):
            self.le = line_edit
            self.current_id = None  # sin autocompletar en fallback

_MEDIOS = ("efectivo", "transferencia", "debito", "credito", "ctacte")
_TIPOS_GASTO = ("fiscal", "negocio", "sueldo", "proveedor", "otro")

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

# misma lógica que usa ventas/nueva_venta.py
def _find_cliente(session, texto):
    t = (texto or "").strip()
    if not t:
        return None
    c = session.query(Cliente).filter(Cliente.cuit_dni == t).first()
    return c or session.query(Cliente).filter(Cliente.nombre == t).first()

class SalidasTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Estado proveedores (carga perezosa)
        self._prov_ready = False
        self.ProvSession = None
        self.MovimientoProveedor = None
        self.Proveedor = None

        root = QVBoxLayout(self)

        # --- Salidas (gastos/pagos) ---
        gb_sal = QGroupBox("Salidas de caja: gastos, impuestos y pagos a proveedores")
        f1 = QFormLayout(gb_sal)

        self.dp_fecha_g = QDateEdit(calendarPopup=True); self.dp_fecha_g.setDate(QDate.currentDate())
        self.cmb_medio_g = QComboBox(self); self.cmb_medio_g.addItems(list(_MEDIOS))
        self.cmb_tipo_g = QComboBox(self); self.cmb_tipo_g.addItems(list(_TIPOS_GASTO))
        self.txt_monto_g = QLineEdit(self); self.txt_monto_g.setPlaceholderText("0,00")
        self.txt_concepto_g = QLineEdit(self); self.txt_concepto_g.setPlaceholderText("Concepto, ej.: 'AFIP IVA' / 'Luz' / 'Pago factura X'")
        self.txt_obs_g = QTextEdit(self); self.txt_obs_g.setPlaceholderText("Observación"); self.txt_obs_g.setMinimumHeight(80)

        # Combo dinámico para entidad (Proveedor, Impuesto o Empleado)
        self.lbl_entidad = QLabel("Entidad:")
        self.cmb_entidad = QComboBox(self)
        self.cmb_entidad.setEnabled(False)
        self.cmb_tipo_g.currentTextChanged.connect(self._on_tipo_changed)

        f1.addRow("Fecha:", self.dp_fecha_g)
        f1.addRow("Medio:", self.cmb_medio_g)
        f1.addRow("Tipo:", self.cmb_tipo_g)
        f1.addRow(self.lbl_entidad, self.cmb_entidad)
        f1.addRow("Monto:", self.txt_monto_g)
        f1.addRow("Concepto:", self.txt_concepto_g)
        f1.addRow("Observación:", self.txt_obs_g)

        hb1 = QHBoxLayout()
        self.btn_guardar_g = QPushButton("Registrar salida")
        self.btn_guardar_g.clicked.connect(self._registrar_salida)
        hb1.addStretch(); hb1.addWidget(self.btn_guardar_g)
        f1.addRow(hb1)

        root.addWidget(gb_sal)

        # --- Cobros Cta Cte Clientes ---
        gb_cc = QGroupBox("Cobros de Cuentas Corrientes (Clientes)")
        v2 = QVBoxLayout(gb_cc)

        f2 = QFormLayout()
        self.ed_cliente = QLineEdit(self); self.ed_cliente.setPlaceholderText("Nombre exacto o DNI/CUIT")
        self.cli_helper = ClienteSearchHelper(self.ed_cliente)  # << CORRECTO: pasa el QLineEdit
        self.dp_fecha_c = QDateEdit(calendarPopup=True); self.dp_fecha_c.setDate(QDate.currentDate())
        self.cmb_medio_c = QComboBox(self); self.cmb_medio_c.addItems(list(_MEDIOS))
        self.txt_monto_c = QLineEdit(self); self.txt_monto_c.setPlaceholderText("0,00")
        self.txt_obs_c = QTextEdit(self); self.txt_obs_c.setPlaceholderText("Observación"); self.txt_obs_c.setMinimumHeight(60)

        f2.addRow("Cliente:", self.ed_cliente)
        f2.addRow("Fecha:", self.dp_fecha_c)
        f2.addRow("Medio:", self.cmb_medio_c)
        f2.addRow("Monto:", self.txt_monto_c)
        f2.addRow("Observación:", self.txt_obs_c)

        hb2 = QHBoxLayout()
        self.btn_cobro = QPushButton("Registrar cobro de Cta Cte")
        self.btn_cobro.clicked.connect(self._registrar_cobro_ctacte)
        hb2.addStretch(); hb2.addWidget(self.btn_cobro)
        f2.addRow(hb2)

        v2.addLayout(f2)

        self.tbl_cobros = QTableWidget(0, 5, self)
        self.tbl_cobros.setHorizontalHeaderLabels(["Fecha", "Cliente", "Monto", "Medio", "Obs"])
        self.tbl_cobros.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_cobros.setSelectionBehavior(self.tbl_cobros.SelectRows)
        self.tbl_cobros.setEditTriggers(self.tbl_cobros.NoEditTriggers)
        v2.addWidget(self.tbl_cobros)

        root.addWidget(gb_cc)
        self._cargar_cobros()

    # ---------------- soporte ----------------

    def _on_tipo_changed(self, val):
        self.cmb_entidad.clear()
        self.cmb_entidad.setEnabled(False)
        self.lbl_entidad.setText("Entidad:")

        if val == "proveedor":
            self.lbl_entidad.setText("Proveedor:")
            self._init_proveedores()
            self._cargar_proveedores()
        elif val == "fiscal":
            self.lbl_entidad.setText("Impuesto:")
            self._cargar_impuestos()
        elif val == "sueldo":
            self.lbl_entidad.setText("Empleado:")
            self._cargar_empleados()
        else:
            self.cmb_entidad.setEnabled(False)

    def _init_proveedores(self):
        if self._prov_ready:
            return
        try:
            from proveedores.bootstrap import bootstrap as prov_bootstrap
            ns = prov_bootstrap()
            self.ProvSession = ns.get("SessionLocal")
            self.MovimientoProveedor = ns.get("MovimientoProveedor")
            self.Proveedor = ns.get("Proveedor")
        except Exception:
            self.ProvSession = None
            self.MovimientoProveedor = None
            self.Proveedor = None
        self._prov_ready = True

    def _cargar_proveedores(self):
        if not self._prov_ready or not self.Proveedor or not self.ProvSession:
            self.cmb_entidad.addItem("<no disponible>", 0)
            return
        try:
            with self.ProvSession() as s:
                rows = s.query(self.Proveedor).order_by(self.Proveedor.nombre.asc()).all()
            self.cmb_entidad.addItem("<seleccionar>", 0)
            for r in rows:
                self.cmb_entidad.addItem(r.nombre or f"ID {r.id}", int(r.id))
            self.cmb_entidad.setEnabled(True)
        except Exception:
            self.cmb_entidad.addItem("<error>", 0)

    def _cargar_impuestos(self):
        try:
            with SessionLocal() as s:
                rows = s.query(Impuesto).filter_by(activo=True).order_by(Impuesto.nombre).all()
                self.cmb_entidad.addItem("<seleccionar>", 0)
                for r in rows:
                    self.cmb_entidad.addItem(f"{r.nombre} ({r.periodicidad})", r.id)
                self.cmb_entidad.setEnabled(True)
        except Exception:
            pass

    def _cargar_empleados(self):
        try:
            with SessionLocal() as s:
                rows = s.query(Empleado).filter_by(activo=True).order_by(Empleado.nombre).all()
                self.cmb_entidad.addItem("<seleccionar>", 0)
                for r in rows:
                    self.cmb_entidad.addItem(r.nombre, r.id)
                self.cmb_entidad.setEnabled(True)
        except Exception:
            pass

    def _set_tbl(self, r, c, v):
        self.tbl_cobros.setItem(r, c, QTableWidgetItem("" if v is None else str(v)))

    # ---------------- acciones ----------------

    def _registrar_salida(self):
        try:
            monto = _f2(self.txt_monto_g.text())
            if monto <= 0:
                raise ValueError()
        except Exception:
            QMessageBox.warning(self, "Salidas", "Monto inválido.")
            return

        fecha = self.dp_fecha_g.date().toPyDate()
        medio = self.cmb_medio_g.currentText()
        tipo = self.cmb_tipo_g.currentText()
        concepto = (self.txt_concepto_g.text() or "").strip()
        obs = (self.txt_obs_g.toPlainText() or "").strip()

        # Validar selección de entidad para tipos que la requieren
        entidad_id = None
        if self.cmb_entidad.isEnabled():
            entidad_id = int(self.cmb_entidad.currentData() or 0)
            if entidad_id <= 0:
                QMessageBox.warning(self, "Atención", f"Debe seleccionar una entidad para tipo '{tipo}'")
                return

        try:
            with SessionLocal() as s:
                SalidasService.registrar_salida(
                    session=s,
                    fecha=fecha,
                    medio=medio,
                    tipo_destino=tipo,
                    monto=monto,
                    concepto=concepto,
                    observacion=obs,
                    entity_id=entidad_id
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error registrando salida: {e}")
            return

        # Si es pago a proveedor, mantener lógica de registro en DB proveedores
        if tipo == "proveedor":
            self._init_proveedores()
            if self.ProvSession and self.MovimientoProveedor and entidad_id:
                try:
                    with self.ProvSession() as ps:
                        mov = self.MovimientoProveedor(
                            proveedor_id=entidad_id,
                            fecha=fecha,
                            fecha_vencimiento=None,
                            descripcion=f"[{medio}] {concepto}",
                            forma_pago=medio,
                            debe=0.0,
                            haber=float(monto)
                        )
                        ps.add(mov); ps.commit()
                except Exception:
                    QMessageBox.warning(self, "Proveedores", "No se pudo registrar el movimiento en proveedores.")

        QMessageBox.information(self, "Salidas", "Salida registrada correctamente.\nVerifique en pestaña Costos.")
        self.txt_monto_g.setText("")
        self.txt_concepto_g.setText("")
        self.txt_obs_g.setPlainText("")

    def _registrar_cobro_ctacte(self):
        cli = None
        with SessionLocal() as s:
            # si el helper mantiene current_id, úsalo; sino busca por texto como en nueva_venta
            cid = getattr(self.cli_helper, "current_id", None)
            if cid:
                try:
                    cli = s.query(Cliente).filter(Cliente.id == int(cid)).first()
                except Exception:
                    cli = None
            if cli is None:
                cli = _find_cliente(s, self.ed_cliente.text())

        if not cli or not getattr(cli, "id", None):
            QMessageBox.warning(self, "Cobros", "Seleccione un cliente válido (nombre exacto o DNI/CUIT).")
            return

        try:
            monto = _f2(self.txt_monto_c.text())
            if monto <= 0:
                raise ValueError()
        except Exception:
            QMessageBox.warning(self, "Cobros", "Monto inválido.")
            return

        fecha = self.dp_fecha_c.date().toPyDate()
        medio = self.cmb_medio_c.currentText()
        obs = (self.txt_obs_c.toPlainText() or "").strip()
        concepto = f"Cobro Cta Cte ({medio})"

        with SessionLocal() as s:
            row = CuentaCorrienteCliente(
                cliente_id=int(cli.id),
                fecha=dt.datetime.combine(fecha, dt.time(hour=12)),
                concepto=concepto if not obs else f"{concepto} - {obs}",
                monto=float(-abs(monto))  # pago = negativo
            )
            s.add(row); s.commit()

        QMessageBox.information(self, "Cobros", "Cobro registrado en Cta Cte del cliente.")
        self._cargar_cobros()
        self.txt_monto_c.setText("")
        self.txt_obs_c.setPlainText("")
        # mantener el texto del cliente para registrar varios cobros seguidos

    def _cargar_cobros(self):
        with SessionLocal() as s:
            rows = (
                s.query(CuentaCorrienteCliente, Cliente)
                .join(Cliente, Cliente.id == CuentaCorrienteCliente.cliente_id)
                .filter(CuentaCorrienteCliente.monto < 0)
                .order_by(CuentaCorrienteCliente.fecha.desc(), CuentaCorrienteCliente.id.desc())
                .limit(100)
                .all()
            )
        self.tbl_cobros.setRowCount(len(rows))
        for r,(mov, cli) in enumerate(rows):
            try:
                ftxt = mov.fecha.strftime("%Y-%m-%d %H:%M")
            except Exception:
                ftxt = str(mov.fecha)
            self._set_tbl(r, 0, ftxt)
            self._set_tbl(r, 1, getattr(cli, "nombre", f"ID {cli.id}"))
            self._set_tbl(r, 2, _fmt(abs(mov.monto)))
            medio = ""
            desc = getattr(mov, "concepto", "") or ""
            if "(" in desc and ")" in desc:
                try:
                    medio = desc.split("(")[1].split(")")[0]
                except Exception:
                    medio = ""
            self._set_tbl(r, 3, medio)
            self._set_tbl(r, 4, desc)
