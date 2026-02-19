# main.py
# ===========================
# Ventana principal estable con menú de tema y carga segura de pestañas
# ===========================

import sys
import traceback
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QAction, QMessageBox, QLabel
)
from PyQt5.QtGui import QPalette, QColor, QKeySequence
from PyQt5.QtCore import Qt, QSettings

# --- Auto-init BD ---
try:
    from db import Base, engine
    Base.metadata.create_all(engine)
    # Ejecutar migraciones para asegurar columnas nuevas
    from migrar_db import run_migrations
    run_migrations()
except Exception as _e:
    print('Aviso: no se pudo crear/verificar tablas o migrar:', _e)
# ---------------------

def global_exception_hook(exctype, value, traceback_obj):
    """
    Global exception handler to capture unhandled exceptions and show them in a dialog.
    """
    txt = "".join(traceback.format_exception(exctype, value, traceback_obj))
    print("Capturada excepción global:", txt)
    try:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setText("Ocurrió un error inesperado.")
        msg.setInformativeText(str(value))
        msg.setDetailedText(txt)
        msg.setWindowTitle("Error Crítico")
        msg.exec_()
    except Exception:
        # Fallback if Qt fails
        pass

def apply_dark_theme(app: QApplication):
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(35, 35, 35))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)


def apply_light_theme(app: QApplication):
    app.setStyle("Fusion")
    app.setPalette(QPalette())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Barter Plus — Estable")
        self.resize(1200, 800)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.setCentralWidget(central)

        self.status = QLabel("Listo")
        self.statusBar().addPermanentWidget(self.status)

        self._build_menu()
        self._load_tabs_safe()
        # Seleccionar Ventas por defecto
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i).lower().startswith('ventas'):
                self.tabs.setCurrentIndex(i); break
  # no rompe si falta algún módulo

    def _build_menu(self):
        menubar = self.menuBar()
        menu_ver = menubar.addMenu("Ver")

        act_claro = QAction("Tema claro", self)
        act_oscuro = QAction("Tema oscuro", self)
        menu_ver.addAction(act_claro)
        menu_ver.addAction(act_oscuro)

        act_claro.triggered.connect(lambda: self._set_theme('claro'))
        act_oscuro.triggered.connect(lambda: self._set_theme('oscuro'))

        # Accion F5 Refresh
        act_refresh = QAction("Actualizar (F5)", self)
        act_refresh.setShortcut(QKeySequence.Refresh)
        act_refresh.triggered.connect(self._handle_f5)
        menu_ver.addAction(act_refresh)

    def _set_theme(self, mode: str):
        app = QApplication.instance()
        if mode == 'oscuro':
            apply_dark_theme(app)
        else:
            apply_light_theme(app)
        QSettings("BarterPlus", "App").setValue("theme", mode)

    def _try_add(self, title: str, import_stmt: str, cls_name: str):
        """
        import_stmt: string de import seguro, ejemplo:
            'from ventas.main_tab import VentasTab'
        cls_name: nombre de la clase importada (p.ej. 'VentasTab')
        """
        try:
            namespace = {}
            exec(import_stmt, namespace, namespace)
            cls = namespace[cls_name]
            self.tabs.addTab(cls(), title)
            return True
        except Exception as e:
            # Log a consola y muestra en status bar
            traceback.print_exc()
            self.status.setText(f"Sin '{title}': {e.__class__.__name__}")

            # Acumular error para mostrar al final
            if not hasattr(self, "_load_errors"):
                self._load_errors = []
            self._load_errors.append(f"<b>{title}</b>: {e}<br><small>{e.__class__.__name__}</small>")
            return False

    def _load_tabs_safe(self):
        # Inicializar lista de errores
        self._load_errors = []

        # Orden recomendado. Carga “mejor esfuerzo”.
        self._try_add("Ventas", "from ventas.main_tab import VentasTab", "VentasTab")
        self._try_add("Productos", "from productos.main_tab import ProductosTab", "ProductosTab")
        self._try_add("Proveedores", "from proveedores.main_tab import ProveedoresTab", "ProveedoresTab")
        self._try_add("Costos", "from costos.main_tab import CostosTab", "CostosTab")
        self._try_add("Caja", "from caja.main_tab import CajaTab", "CajaTab")
        self._try_add("Resumen", "from resumen import ResumenTab", "ResumenTab")

        # Configuración (pestaña a parte)
        try:
            from configuracion_tab import ConfiguracionTab
            # Pasamos callback para cambio de tema inmediato
            tab = ConfiguracionTab(apply_theme_callback=self._set_theme)
            self.tabs.addTab(tab, "Configuración")
        except Exception as e:
            traceback.print_exc()
            self.status.setText(f"Sin Configuración: {e}")
            self._load_errors.append(f"<b>Configuración</b>: {e}")

        # Mostrar errores si los hubo (Plus: reporte de salud al inicio)
        if self._load_errors:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Advertencia de Carga")
            msg.setText("Algunos módulos no se pudieron cargar.")
            msg.setInformativeText("El programa funcionará, pero faltarán las siguientes pestañas:")
            msg.setDetailedText("\n".join(self._load_errors).replace("<br>", "\n").replace("<b>", "").replace("</b>", "").replace("<small>", "").replace("</small>", ""))
            msg.exec_()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F5:
            self._handle_f5()
        else:
            super().keyPressEvent(event)

    def _handle_f5(self):
        current = self.tabs.currentWidget()
        if current and hasattr(current, "reload"):
            try:
                current.reload()
                self.status.setText(f"Recargada pestaña: {self.tabs.tabText(self.tabs.currentIndex())}")
            except Exception as e:
                self.status.setText(f"Error recargando: {e}")
        elif current and hasattr(current, "refresh"):
             try:
                current.refresh()
                self.status.setText(f"Refrescada pestaña: {self.tabs.tabText(self.tabs.currentIndex())}")
             except Exception as e:
                self.status.setText(f"Error refrescando: {e}")
        else:
             self.status.setText("La pestaña actual no soporta recarga automática.")

def main():
    sys.excepthook = global_exception_hook
    app = QApplication(sys.argv)
    theme = QSettings("BarterPlus", "App").value("theme", "oscuro")
    apply_dark_theme(app) if theme == "oscuro" else apply_light_theme(app)

    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
