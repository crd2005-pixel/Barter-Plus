from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QInputDialog, QDialog,
    QFormLayout, QLineEdit, QComboBox, QTabWidget, QSpinBox, QCheckBox, QDateEdit
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QPixmap, QImage
from services.taller_service import TallerService
from services.cliente_service import ClienteService
from services.producto_service import ProductoService

class DialogoQR(QDialog):
    def __init__(self, titulo: str, img_bytes: bytes, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Código QR - {titulo}")
        self.img_bytes = img_bytes
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        lbl_qr = QLabel()
        lbl_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)

        image = QImage.fromData(self.img_bytes)
        pixmap = QPixmap.fromImage(image)
        lbl_qr.setPixmap(pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio))

        layout.addWidget(lbl_qr)

        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(self.accept)
        layout.addWidget(btn_cerrar)

class NuevoVehiculoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registrar Nuevo Vehículo")
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        self.combo_cliente = QComboBox()
        for c in ClienteService.listar_todos():
            self.combo_cliente.addItem(c.nombre, c.id)

        self.txt_dominio = QLineEdit()
        self.txt_marca = QLineEdit()
        self.txt_modelo = QLineEdit()
        self.txt_anio = QSpinBox()
        self.txt_anio.setRange(1950, QDate.currentDate().year() + 1)
        self.txt_anio.setValue(2015)

        layout.addRow("Cliente Dueño:", self.combo_cliente)
        layout.addRow("Dominio/Patente (*):", self.txt_dominio)
        layout.addRow("Marca:", self.txt_marca)
        layout.addRow("Modelo:", self.txt_modelo)
        layout.addRow("Año:", self.txt_anio)

        btn_layout = QHBoxLayout()
        btn_guardar = QPushButton("Guardar")
        btn_guardar.clicked.connect(self.guardar)
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(btn_guardar)
        btn_layout.addWidget(btn_cancelar)
        layout.addRow(btn_layout)

    def guardar(self):
        dom = self.txt_dominio.text().strip()
        if not dom:
            QMessageBox.warning(self, "Error", "El dominio es obligatorio.")
            return

        try:
            TallerService.crear_vehiculo(
                cliente_id=self.combo_cliente.currentData(),
                dominio=dom,
                marca=self.txt_marca.text().strip(),
                modelo=self.txt_modelo.text().strip(),
                anio=self.txt_anio.value()
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar: {e}")


class GarantiasTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Selector de Vehículo Superior
        header_lay = QHBoxLayout()
        self.combo_vehiculos = QComboBox()
        self.btn_recargar_v = QPushButton("Actualizar Lista")
        self.btn_recargar_v.clicked.connect(self.cargar_vehiculos)
        self.btn_nuevo_v = QPushButton("+ Vehículo")
        self.btn_nuevo_v.clicked.connect(self.nuevo_vehiculo)

        header_lay.addWidget(QLabel("Vehículo:"))
        header_lay.addWidget(self.combo_vehiculos)
        header_lay.addWidget(self.btn_recargar_v)
        header_lay.addWidget(self.btn_nuevo_v)
        layout.addLayout(header_lay)

        # Formulario de Registro
        form_lay = QFormLayout()

        self.combo_producto = QComboBox()
        for p in ProductoService.listar_todos(): # asumiendo listar_todos, lo haré hardcode query por ahora
            pass
        # Actually it's better to dynamically load or use search, but let's just use flexible search for Bateria

        self.txt_busqueda_prod = QLineEdit()
        self.txt_busqueda_prod.setPlaceholderText("Código o Nombre de Batería...")
        self.btn_buscar_prod = QPushButton("Buscar")
        self.btn_buscar_prod.clicked.connect(self.buscar_producto)
        self.lbl_prod_sel = QLabel("Ninguno seleccionado")
        self.producto_id_sel = None

        box_prod = QHBoxLayout()
        box_prod.addWidget(self.txt_busqueda_prod)
        box_prod.addWidget(self.btn_buscar_prod)

        form_lay.addRow("Buscar Batería:", box_prod)
        form_lay.addRow("Seleccionada:", self.lbl_prod_sel)

        self.spin_meses = QSpinBox()
        self.spin_meses.setRange(1, 48)
        self.spin_meses.setValue(12)
        form_lay.addRow("Meses de Garantía:", self.spin_meses)

        self.btn_guardar_g = QPushButton("Registrar Garantía")
        self.btn_guardar_g.setStyleSheet("font-weight: bold; background-color: #5cb85c; color: white;")
        self.btn_guardar_g.clicked.connect(self.guardar_garantia)
        form_lay.addRow(self.btn_guardar_g)

        layout.addLayout(form_lay)

        # Grilla de Historial
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Fecha Instalación", "Batería", "Vencimiento", "Código", "Acción"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.combo_vehiculos.currentIndexChanged.connect(self.cargar_historial)

    def buscar_producto(self):
        query = self.txt_busqueda_prod.text().strip()
        if not query: return
        p = ProductoService.buscar_por_query_flexible(query)
        if p:
            self.producto_id_sel = p.id
            self.lbl_prod_sel.setText(p.nombre)
        else:
            QMessageBox.warning(self, "No encontrado", "No se encontró la batería.")

    def cargar_vehiculos(self):
        self.combo_vehiculos.blockSignals(True)
        self.combo_vehiculos.clear()
        from database.conexion import get_session
        from database.models.taller import Vehiculo
        from sqlalchemy import select
        with get_session() as session:
            vehiculos = session.scalars(select(Vehiculo)).all()
            for v in vehiculos:
                self.combo_vehiculos.addItem(f"{v.dominio} - {v.marca} {v.modelo}", v.id)
        self.combo_vehiculos.blockSignals(False)
        self.cargar_historial()

    def nuevo_vehiculo(self):
        d = NuevoVehiculoDialog(self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.cargar_vehiculos()

    def guardar_garantia(self):
        v_id = self.combo_vehiculos.currentData()
        if not v_id or not self.producto_id_sel:
            QMessageBox.warning(self, "Error", "Debe seleccionar un vehículo y una batería.")
            return

        try:
            g = TallerService.registrar_garantia(v_id, self.producto_id_sel, self.spin_meses.value())
            QMessageBox.information(self, "Éxito", "Garantía registrada.")
            self.cargar_historial()
            self.mostrar_qr(g.id)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def cargar_historial(self):
        v_id = self.combo_vehiculos.currentData()
        if not v_id:
            self.table.setRowCount(0)
            return

        historial = TallerService.obtener_garantias(v_id)
        self.table.setRowCount(len(historial))
        for row, g in enumerate(historial):
            self.table.setItem(row, 0, QTableWidgetItem(str(g.id)))
            self.table.setItem(row, 1, QTableWidgetItem(g.fecha_instalacion.strftime('%d/%m/%Y')))
            self.table.setItem(row, 2, QTableWidgetItem(g.producto.nombre))

            i_venc = QTableWidgetItem(g.fecha_vencimiento.strftime('%d/%m/%Y'))
            if g.fecha_vencimiento < QDate.currentDate().toPyDate():
                i_venc.setForeground(Qt.GlobalColor.red)
            self.table.setItem(row, 3, i_venc)

            self.table.setItem(row, 4, QTableWidgetItem(g.codigo_garantia))

            btn_qr = QPushButton("Ver QR")
            btn_qr.clicked.connect(lambda checked, gid=g.id: self.mostrar_qr(gid))
            self.table.setCellWidget(row, 5, btn_qr)

    def mostrar_qr(self, g_id):
        try:
            img = TallerService.generar_qr_garantia(g_id)
            d = DialogoQR("Garantía de Batería", img, self)
            d.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error QR", str(e))

class AceiteTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Selector de Vehículo Superior
        header_lay = QHBoxLayout()
        self.combo_vehiculos = QComboBox()
        self.btn_recargar_v = QPushButton("Actualizar Lista")
        self.btn_recargar_v.clicked.connect(self.cargar_vehiculos)

        header_lay.addWidget(QLabel("Vehículo:"))
        header_lay.addWidget(self.combo_vehiculos)
        header_lay.addWidget(self.btn_recargar_v)
        layout.addLayout(header_lay)

        # Formulario
        form_lay = QFormLayout()

        self.txt_km_act = QSpinBox()
        self.txt_km_act.setRange(0, 9999999)
        self.txt_km_prox = QSpinBox()
        self.txt_km_prox.setRange(0, 9999999)

        self.txt_aceite = QLineEdit()
        self.txt_aceite.setPlaceholderText("Ej: Total Quartz 7000 10W40")

        self.chk_f_aceite = QCheckBox("Aceite")
        self.chk_f_aire = QCheckBox("Aire")
        self.chk_f_comb = QCheckBox("Combustible")
        self.chk_f_hab = QCheckBox("Habitáculo")

        filtros_lay = QHBoxLayout()
        filtros_lay.addWidget(self.chk_f_aceite)
        filtros_lay.addWidget(self.chk_f_aire)
        filtros_lay.addWidget(self.chk_f_comb)
        filtros_lay.addWidget(self.chk_f_hab)

        self.txt_obs = QLineEdit()

        form_lay.addRow("Km Actual:", self.txt_km_act)
        form_lay.addRow("Próximo Cambio (Km):", self.txt_km_prox)
        form_lay.addRow("Aceite Utilizado:", self.txt_aceite)
        form_lay.addRow("Filtros:", filtros_lay)
        form_lay.addRow("Observaciones:", self.txt_obs)

        self.btn_guardar_a = QPushButton("Registrar Service")
        self.btn_guardar_a.setStyleSheet("font-weight: bold; background-color: #0275d8; color: white;")
        self.btn_guardar_a.clicked.connect(self.guardar_service)
        form_lay.addRow(self.btn_guardar_a)

        layout.addLayout(form_lay)

        # Grilla de Historial
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Fecha", "Km Act", "Próximo Km", "Aceite", "Filtros", "Acción"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.combo_vehiculos.currentIndexChanged.connect(self.cargar_historial)

    def cargar_vehiculos(self):
        self.combo_vehiculos.blockSignals(True)
        self.combo_vehiculos.clear()
        from database.conexion import get_session
        from database.models.taller import Vehiculo
        from sqlalchemy import select
        with get_session() as session:
            vehiculos = session.scalars(select(Vehiculo)).all()
            for v in vehiculos:
                self.combo_vehiculos.addItem(f"{v.dominio} - {v.marca} {v.modelo}", v.id)
        self.combo_vehiculos.blockSignals(False)
        self.cargar_historial()

    def guardar_service(self):
        v_id = self.combo_vehiculos.currentData()
        if not v_id:
            QMessageBox.warning(self, "Error", "Debe seleccionar un vehículo.")
            return

        aceite = self.txt_aceite.text().strip()
        if not aceite:
            QMessageBox.warning(self, "Error", "Debe indicar el aceite utilizado.")
            return

        try:
            c = TallerService.registrar_cambio_aceite(
                vehiculo_id=v_id,
                km_actual=self.txt_km_act.value(),
                proximo_km=self.txt_km_prox.value(),
                aceite=aceite,
                f_aceite=self.chk_f_aceite.isChecked(),
                f_aire=self.chk_f_aire.isChecked(),
                f_comb=self.chk_f_comb.isChecked(),
                f_hab=self.chk_f_hab.isChecked(),
                obs=self.txt_obs.text().strip()
            )
            QMessageBox.information(self, "Éxito", "Service registrado.")
            self.cargar_historial()
            self.mostrar_qr(c.id)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def cargar_historial(self):
        v_id = self.combo_vehiculos.currentData()
        if not v_id:
            self.table.setRowCount(0)
            return

        historial = TallerService.obtener_cambios_aceite(v_id)
        self.table.setRowCount(len(historial))
        for row, c in enumerate(historial):
            self.table.setItem(row, 0, QTableWidgetItem(str(c.id)))
            self.table.setItem(row, 1, QTableWidgetItem(c.fecha.strftime('%d/%m/%Y')))
            self.table.setItem(row, 2, QTableWidgetItem(str(c.km_actual)))
            self.table.setItem(row, 3, QTableWidgetItem(str(c.proximo_km)))
            self.table.setItem(row, 4, QTableWidgetItem(c.aceite_utilizado))

            filtros = []
            if c.filtro_aceite: filtros.append("Aceite")
            if c.filtro_aire: filtros.append("Aire")
            if c.filtro_combustible: filtros.append("Comb")
            if c.filtro_habitaculo: filtros.append("Habit")
            self.table.setItem(row, 5, QTableWidgetItem(", ".join(filtros)))

            btn_qr = QPushButton("Ver QR")
            btn_qr.clicked.connect(lambda checked, cid=c.id: self.mostrar_qr(cid))
            self.table.setCellWidget(row, 6, btn_qr)

    def mostrar_qr(self, c_id):
        try:
            img = TallerService.generar_qr_aceite(c_id)
            d = DialogoQR("Service (Aceite y Filtros)", img, self)
            d.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error QR", str(e))


class TallerView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.tab_garantias = GarantiasTab()
        self.tab_aceite = AceiteTab()

        self.tabs.addTab(self.tab_garantias, "Garantías de Baterías")
        self.tabs.addTab(self.tab_aceite, "Cambios de Aceite")

        layout.addWidget(self.tabs)

    def showEvent(self, event):
        super().showEvent(event)
        self.tab_garantias.cargar_vehiculos()
        self.tab_aceite.cargar_vehiculos()
