# -*- coding: utf-8 -*-
# ventas/main_tab.py — Tab contenedor de Ventas
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QMessageBox
import traceback, os, importlib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOGDIR = os.path.join(ROOT, "logs")
ERRLOG = os.path.join(LOGDIR, "errores_BarterPlus.log")
os.makedirs(LOGDIR, exist_ok=True)

def _log_exc(prefix: str):
    tb = traceback.format_exc()
    try:
        with open(ERRLOG, "a", encoding="utf-8") as f:
            f.write("\n--- VentasTab ---\n" + prefix + "\n" + tb + "\n")
    except Exception:
        pass
    try:
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.critical(None, "Ventas", f"{prefix}\n\nRevise logs/errores_BarterPlus.log")
    except Exception:
        pass

def _safe_import(modname, attr=None):
    try:
        m = importlib.import_module(modname)
        return getattr(m, attr) if attr else m
    except Exception:
        _log_exc(f"Import falló: {modname}{'.'+attr if attr else ''}")
        return None

# Tabs
NuevaVentaTab         = _safe_import("ventas.nueva_venta", "NuevaVentaTab")
HistorialVentasTab    = _safe_import("ventas.historial", "HistorialVentasTab")
CuentasCorrienteTab   = _safe_import("ventas.cuentas_corriente", "CuentasCorrienteTab")
ClientesTab           = _safe_import("ventas.clientes_tab", "ClientesTab")
SalidasTab            = _safe_import("ventas.salidas", "SalidasTab")
# Para aislar: cambiar SalidasTab por un stub si existiera: ventas.salidas_stub.SalidasStub

class VentasTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self._add_tab(NuevaVentaTab, "Nueva Venta")
        self._add_tab(HistorialVentasTab, "Historial")
        self._add_tab(CuentasCorrienteTab, "Cuentas Corrientes")
        self._add_tab(ClientesTab, "Clientes")
        self._add_tab(SalidasTab, "Salidas")

        layout.addWidget(self.tabs)

    def _add_tab(self, cls, titulo):
        if cls is None:
            return
        try:
            w = cls()
        except Exception:
            _log_exc(f"Construcción falló: {titulo}")
            return
        self.tabs.addTab(w, titulo)
