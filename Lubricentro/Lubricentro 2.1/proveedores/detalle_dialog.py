# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QMessageBox, QAbstractItemView, QMenu, QInputDialog,
    QDateEdit, QLineEdit, QDoubleSpinBox, QFormLayout
)
from PyQt5.QtCore import Qt, QDate
from datetime import date

from services.proveedor_service import ProveedorService, MovimientoProveedor
from proveedores.facturas import FacturaProveedorWidget # Reuse logic if possible, or direct form

# Need access to FacturaProveedor to edit linked invoices
try:
    from proveedores.bootstrap import bootstrap
    _ns = bootstrap()
    FacturaProveedor = _ns.get("FacturaProveedor")
    FacturaItem = _ns.get("FacturaItem")
    ProvSession = _ns.get("SessionLocal")
except:
    FacturaProveedor = None
    FacturaItem = None
    ProvSession = None

class ProveedorDetalleDialog(QDialog):
    def __init__(self, proveedor_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ficha de Proveedor")
        self.resize(900, 600)
        self.proveedor_id = proveedor_id

        lay = QVBoxLayout(self)

        # Header Info
        self.lbl_info = QLabel("Proveedor: ...")
        self.lbl_info.setStyleSheet("font-size: 16px; font-weight: bold;")
        lay.addWidget(self.lbl_info)

        # Table
        self.tbl = QTableWidget()
        self.tbl.setColumnCount(6)
        self.tbl.setHorizontalHeaderLabels(["Fecha", "Vencimiento", "Descripción", "Debe", "Haber", "Saldo Parcial"])
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tbl.customContextMenuRequested.connect(self._context_menu)
        lay.addWidget(self.tbl)

        # Buttons
        h = QHBoxLayout()

        btn_mod = QPushButton("Modificar seleccionado")
        btn_mod.clicked.connect(self._on_btn_modificar)
        h.addWidget(btn_mod)

        btn_del = QPushButton("Borrar seleccionado")
        btn_del.setStyleSheet("color: red;")
        btn_del.clicked.connect(self._on_btn_borrar)
        h.addWidget(btn_del)

        h.addStretch()
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        h.addWidget(btn_close)
        lay.addLayout(h)

        self._load_data()

    def _on_btn_modificar(self):
        row = self.tbl.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Modificar", "Seleccione un movimiento.")
            return
        mid = self.tbl.item(row, 0).data(Qt.UserRole)
        self._editar_movimiento(mid)

    def _on_btn_borrar(self):
        row = self.tbl.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Borrar", "Seleccione un movimiento.")
            return
        mid = self.tbl.item(row, 0).data(Qt.UserRole)
        self._borrar_movimiento(mid)

    def _load_data(self):
        try:
            with ProveedorService.get_session() as s:
                # Get Name
                if self.proveedor_id and isinstance(self.proveedor_id, int):
                    # Check if real ID
                    # If it was a hash, we might not find it easily if no real record.
                    # Assuming real ID for now.
                    from proveedores.bootstrap import bootstrap
                    P = bootstrap().get("Proveedor")
                    if P:
                        p = s.query(P).get(self.proveedor_id)
                        if p:
                            self.lbl_info.setText(f"Proveedor: {p.nombre or p.razon_social} (ID: {p.id})")

                # Get Movs
                q = s.query(MovimientoProveedor).filter(MovimientoProveedor.proveedor_id == self.proveedor_id).order_by(MovimientoProveedor.fecha.asc(), MovimientoProveedor.id.asc())
                movs = q.all()

                self.tbl.setRowCount(0)
                saldo = 0.0

                for m in movs:
                    debe = float(getattr(m, "debe", 0) or 0)
                    haber = float(getattr(m, "haber", 0) or 0)
                    saldo += (debe - haber)

                    r = self.tbl.rowCount(); self.tbl.insertRow(r)

                    # Date
                    d_txt = m.fecha.strftime("%d/%m/%Y") if m.fecha else ""
                    self.tbl.setItem(r, 0, QTableWidgetItem(d_txt))

                    # Vto
                    v_txt = m.fecha_vencimiento.strftime("%d/%m/%Y") if m.fecha_vencimiento else ""
                    self.tbl.setItem(r, 1, QTableWidgetItem(v_txt))

                    # Desc
                    self.tbl.setItem(r, 2, QTableWidgetItem(str(m.descripcion or "")))

                    # Debe
                    self.tbl.setItem(r, 3, QTableWidgetItem(f"{debe:,.2f}"))

                    # Haber
                    self.tbl.setItem(r, 4, QTableWidgetItem(f"{haber:,.2f}"))

                    # Saldo
                    self.tbl.setItem(r, 5, QTableWidgetItem(f"{saldo:,.2f}"))

                    self.tbl.item(r, 0).setData(Qt.UserRole, m.id)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error cargando ficha: {e}")

    def _context_menu(self, pos):
        item = self.tbl.itemAt(pos)
        if not item: return
        mid = self.tbl.item(item.row(), 0).data(Qt.UserRole)

        menu = QMenu(self)
        act_edit = menu.addAction("Modificar")
        act_del = menu.addAction("Borrar")

        action = menu.exec_(self.tbl.mapToGlobal(pos))
        if action == act_edit:
            self._editar_movimiento(mid)
        elif action == act_del:
            self._borrar_movimiento(mid)

    def _borrar_movimiento(self, mid):
        # Logic: If linked to invoice, warn and delegate to Invoice Delete (which handles stock).
        # How to check link? By convention description or lookup.
        # We can reuse _revertir_stock_y_movimientos logic but we need to find the Invoice ID first.
        # Let's verify if there is an Invoice with same provider, date, amount.

        resp = QMessageBox.question(self, "Borrar", "¿Eliminar este movimiento? (Si es factura, se revertirá stock)", QMessageBox.Yes | QMessageBox.No)
        if resp != QMessageBox.Yes: return

        try:
            # Check for linked invoice
            fid = self._find_linked_invoice(mid)
            if fid:
                # Use the logic from facturas.py via a temporary instance or static method?
                # We need to instantiate FacturaProveedorWidget to access private methods or copy logic.
                # Instantiating is safe (hidden).
                from proveedores.facturas import FacturaProveedorWidget
                # We need to expose _borrar_factura or make it public.
                # It is private. Let's make a public wrapper in this file or call it carefully.
                # Accessing private method is possible in Python.
                w = FacturaProveedorWidget()
                w._borrar_factura(fid) # This handles everything (Revert Stock + Delete Mov)
                # Wait, _borrar_factura shows its own confirmation dialog. That's fine.
            else:
                # Just delete movement (e.g. manual payment or adjustment)
                with ProveedorService.get_session() as s:
                    m = s.query(MovimientoProveedor).get(mid)
                    if m:
                        s.delete(m)
                        s.commit()

            self._load_data()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo borrar: {e}")

    def _editar_movimiento(self, mid):
        # Logic: If invoice, load invoice editor. If manual, show simple dialog.
        fid = self._find_linked_invoice(mid)

        if fid:
            # Open Invoice Editor Dialog
            from proveedores.facturas import FacturaProveedorWidget
            # We want to open it as a Dialog, not embedded.
            dlg = QDialog(self)
            dlg.setWindowTitle("Modificar Factura")
            dlg.resize(800, 600)
            l = QVBoxLayout(dlg)

            w = FacturaProveedorWidget(on_after_save=dlg.accept)
            # Load data
            w._cargar_factura_para_edicion(fid)
            l.addWidget(w)

            if dlg.exec_() == QDialog.Accepted:
                self._load_data()
        else:
            # Simple manual edit
            self._editar_manual(mid)

    def _find_linked_invoice(self, mid):
        # Find FacturaProveedor that matches this movement
        with ProveedorService.get_session() as s:
            m = s.query(MovimientoProveedor).get(mid)
            if not m: return None

            # Match by Provider, Date, Amount (Debe for Invoice/Remito)
            # Risk: Duplicate amounts on same day.
            # Best guess heuristic.
            if m.debe > 0:
                # Likely Factura/Remito
                f = s.query(FacturaProveedor).filter(
                    FacturaProveedor.proveedor_id == m.proveedor_id,
                    FacturaProveedor.fecha == m.fecha,
                    FacturaProveedor.monto_total == m.debe
                ).first()
                return f.id if f else None
            # If Haber > 0, likely Payment (FacturaProveedor of type 'Pago'?)
            # Our Invoice Entry saves Pagos as FacturaProveedor type='Pago'.
            if m.haber > 0:
                f = s.query(FacturaProveedor).filter(
                    FacturaProveedor.proveedor_id == m.proveedor_id,
                    FacturaProveedor.fecha == m.fecha,
                    FacturaProveedor.monto_total == m.haber, # Wait, monto_total in Factura is usually the full amount
                    FacturaProveedor.tipo == "Pago"
                ).first()
                return f.id if f else None
        return None

    def _editar_manual(self, mid):
        # Simple dialog for fields
        with ProveedorService.get_session() as s:
            m = s.query(MovimientoProveedor).get(mid)
            if not m: return

            dlg = QDialog(self)
            dlg.setWindowTitle("Editar Movimiento Manual")
            form = QFormLayout(dlg)

            dt_f = QDateEdit(); dt_f.setDate(m.fecha)
            txt_d = QLineEdit(m.descripcion)
            sp_debe = QDoubleSpinBox(); sp_debe.setRange(0, 1e9); sp_debe.setValue(m.debe or 0)
            sp_haber = QDoubleSpinBox(); sp_haber.setRange(0, 1e9); sp_haber.setValue(m.haber or 0)

            form.addRow("Fecha:", dt_f)
            form.addRow("Descripción:", txt_d)
            form.addRow("Debe:", sp_debe)
            form.addRow("Haber:", sp_haber)

            h = QHBoxLayout()
            btn_ok = QPushButton("Guardar"); btn_ok.clicked.connect(dlg.accept)
            btn_cn = QPushButton("Cancelar"); btn_cn.clicked.connect(dlg.reject)
            h.addWidget(btn_ok); h.addWidget(btn_cn)
            form.addRow(h)

            if dlg.exec_() == QDialog.Accepted:
                m.fecha = dt_f.date().toPyDate()
                m.descripcion = txt_d.text()
                m.debe = sp_debe.value()
                m.haber = sp_haber.value()
                s.commit()
                self._load_data()
