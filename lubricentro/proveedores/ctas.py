# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QDialog, QFormLayout, QLabel, QPushButton, QTextEdit
)
from PyQt5.QtCore import Qt

from services.proveedor_service import ProveedorService, MovimientoProveedor

try:
    from proveedores.bootstrap import bootstrap
    _ns = bootstrap()
    Proveedor = _ns.get("Proveedor")
except:
    Proveedor = None

class CuentasCorrientesTab(QWidget):
    """
    Vista unificada de movimientos de proveedores.
    Muestra saldos agrupados por proveedor.
    Doble click abre ficha detallada (historial).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)

        self.tbl = self._make_table()
        lay.addWidget(self.tbl)

        from PyQt5.QtWidgets import QPushButton
        self.btn_refresh = QPushButton("Actualizar Saldos")
        self.btn_refresh.clicked.connect(self._load_saldos)
        lay.addWidget(self.btn_refresh)

        self._load_saldos()

    # ---------- helpers ----------
    def _make_table(self) -> QTableWidget:
        tbl = QTableWidget()
        tbl.setColumnCount(3)
        tbl.setHorizontalHeaderLabels(["Proveedor", "Saldo", "Último Movimiento"])
        tbl.setSelectionBehavior(tbl.SelectRows)
        tbl.setEditTriggers(tbl.NoEditTriggers)
        tbl.cellDoubleClicked.connect(self._open_provider_detail)
        return tbl

    def _load_saldos(self):
        try:
            with ProveedorService.get_session() as s:
                movs = ProveedorService.get_movimientos(s)
                # Agrupar por proveedor_id
                saldos = {} # pid -> {saldo, last_date, name}

                # Fetch provider names if possible
                prov_map = {}
                if Proveedor:
                    for p in s.query(Proveedor).all():
                        prov_map[p.id] = p.nombre or p.razon_social or "Sin Nombre"

                for m in movs:
                    pid = getattr(m, "proveedor_id", None)
                    if not pid:
                        # Fallback: extract from description "[Prov] ..."
                        desc = str(getattr(m, "descripcion", "") or "")
                        if desc.startswith("["):
                            try:
                                j = desc.index("]")
                                pname = desc[1:j]
                                # Fake ID or group by name?
                                # Better grouping by ID is reliable.
                                # If no ID, group by name (negative ID hash?)
                                pid = hash(pname)
                                prov_map[pid] = pname
                            except: pass

                    if not pid: continue

                    if pid not in saldos:
                        saldos[pid] = {"saldo": 0.0, "last": None, "name": prov_map.get(pid, f"Prov #{pid}")}

                    debe = float(getattr(m, "debe", 0) or 0)
                    haber = float(getattr(m, "haber", 0) or 0)
                    saldos[pid]["saldo"] += (debe - haber)

                    m_date = getattr(m, "fecha", None)
                    if m_date:
                        if saldos[pid]["last"] is None or m_date > saldos[pid]["last"]:
                            saldos[pid]["last"] = m_date

            self._fill_table(self.tbl, saldos)
            self.tbl.resizeColumnsToContents()
        except Exception as e:
            print(f"Error loading Saldos Proveedores: {e}")
            self.tbl.setRowCount(0)

    def _fill_table(self, tbl: QTableWidget, saldos_dict):
        tbl.setRowCount(0)
        # Sort by Name
        sorted_saldos = sorted(saldos_dict.items(), key=lambda x: x[1]["name"])

        for pid, data in sorted_saldos:
            r = tbl.rowCount(); tbl.insertRow(r)

            # Nombre
            it_nom = QTableWidgetItem(str(data["name"]))
            it_nom.setData(Qt.UserRole, pid) # Store PID
            tbl.setItem(r, 0, it_nom)

            # Saldo
            s_val = data["saldo"]
            it_bal = QTableWidgetItem(f"{s_val:,.2f}")
            if s_val > 0.01:
                it_bal.setForeground(Qt.red) # Deuda
            elif s_val < -0.01:
                it_bal.setForeground(Qt.green) # A favor (pagado de más?)
            tbl.setItem(r, 1, it_bal)

            # Last Date
            ld = data["last"]
            ld_str = ld.strftime("%Y-%m-%d") if ld else "-"
            tbl.setItem(r, 2, QTableWidgetItem(ld_str))

    # ---------- Detalle (Ficha) ----------
    def _open_provider_detail(self, row: int, col: int):
        item = self.tbl.item(row, 0)
        if not item: return
        pid = item.data(Qt.UserRole)

        # Check if pid is hash (int) or db id (int).
        # If hash (no real provider record), we can't easily filter by ID in DB unless we saved it.
        # But our bootstrap logic links MovimientoProveedor to Proveedor.id.

        from .detalle_dialog import ProveedorDetalleDialog
        dlg = ProveedorDetalleDialog(pid, parent=self)
        dlg.exec_()
        self._load_saldos() # Refresh on close
