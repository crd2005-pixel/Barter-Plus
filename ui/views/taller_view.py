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
        self.lbl_qr = QLabel()
        self.lbl_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)

        qimg = QImage.fromData(self.img_bytes)
        pix = QPixmap.fromImage(qimg)
        self.lbl_qr.setPixmap(pix.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio))
        layout.addWidget(self.lbl_qr)

        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(self.accept)
        layout.addWidget(btn_cerrar)

class NuevoVehiculoDialog(QDialog):
    def __init__(self, cliente_id=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo Vehículo")
        self.cliente_id = cliente_id
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.combo_cliente = QComboBox()
        from database.conexion import get_session
        from database.models.cliente import Cliente
        from sqlalchemy import select
        with get_session() as s:
            clientes = s.scalars(select(Cliente).order_by(Cliente.nombre)).all()
            for c in clientes:
                self.combo_cliente.addItem(c.nombre, c.id)

        if self.cliente_id:
            idx = self.combo_cliente.findData(self.cliente_id)
            if idx >= 0:
                self.combo_cliente.setCurrentIndex(idx)
            self.combo_cliente.setEnabled(False)

        self.txt_patente = QLineEdit()
        self.txt_marca = QLineEdit()
        self.txt_modelo = QLineEdit()
        self.spin_anio = QSpinBox()
        self.spin_anio.setRange(1900, 2100)
        self.spin_anio.setValue(QDate.currentDate().year())

        form.addRow("Cliente:", self.combo_cliente)
        form.addRow("Patente:", self.txt_patente)
        form.addRow("Marca:", self.txt_marca)
        form.addRow("Modelo:", self.txt_modelo)
        form.addRow("Año:", self.spin_anio)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_guardar = QPushButton("Guardar")
        btn_guardar.clicked.connect(self.guardar)
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        btn_box.addWidget(btn_guardar)
        btn_box.addWidget(btn_cancelar)
        layout.addLayout(btn_box)

    def guardar(self):
        c_id = self.combo_cliente.currentData()
        patente = self.txt_patente.text().strip().upper()
        if not c_id or not patente:
            QMessageBox.warning(self, "Error", "Debe seleccionar un cliente y escribir la patente.")
            return

        try:
            TallerService.crear_vehiculo(c_id, patente, self.txt_marca.text(), self.txt_modelo.text(), self.spin_anio.value())
            QMessageBox.information(self, "Éxito", "Vehículo registrado.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

        # Conectar Cliente -> Vehículo
        self.combo_cliente.currentIndexChanged.connect(self._filtrar_vehiculos_por_cliente)

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
            "ID", "Vehículo (Patente)", "Batería", "Fecha Instalación", "Vencimiento", "Acción"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.btn_exportar_pdf_grilla = QPushButton("Exportar Historial a PDF")
        self.btn_exportar_pdf_grilla.clicked.connect(self._exportar_pdf)
        layout.addWidget(self.btn_exportar_pdf_grilla)

        self.combo_vehiculos.currentIndexChanged.connect(self.cargar_historial)

    def _exportar_pdf(self):
        from utils.export_utils import ExportUtils
        import os
        from PyQt6.QtWidgets import QFileDialog

        c_id = self.combo_cliente.currentData()
        if not c_id:
            QMessageBox.warning(self, "Error", "Seleccione un cliente primero.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Exportar PDF", f"Historial_Garantias_Cliente_{c_id}.pdf", "PDF Files (*.pdf)")
        if path:
            ExportUtils.exportar_tabla_a_pdf(self.table, f"Historial de Garantías - Cliente ID: {c_id}", path)
            QMessageBox.information(self, "Éxito", "Historial exportado correctamente.")

    def buscar_producto(self):
        query = self.txt_busqueda_prod.text().strip()
        if not query: return
        p = ProductoService.buscar_por_query_flexible(query)
        if p:
            self.producto_id_sel = p.id
            self.lbl_prod_sel.setText(p.nombre)
        else:
            QMessageBox.warning(self, "No encontrado", "No se encontró la batería.")

        self.table.itemDoubleClicked.connect(self._abrir_detalle_service)

    def _abrir_detalle_service(self, item):
        row = item.row()
        c_id_str = self.table.item(row, 0).text()
        if not c_id_str.isdigit(): return

        c_id = int(c_id_str)
        from ui.components.dialogs import DetalleServiceDialog
        dlg = DetalleServiceDialog(c_id, self)
        dlg.exec()

    def cargar_clientes(self):
        from database.conexion import get_session
        from database.models.cliente import Cliente
        from sqlalchemy import select
        self.combo_cliente.blockSignals(True)
        self.combo_cliente.clear()
        self.combo_cliente.addItem("Seleccione un Cliente...", None)
        with get_session() as s:
            clientes = s.scalars(select(Cliente).order_by(Cliente.nombre)).all()
            for c in clientes:
                self.combo_cliente.addItem(c.nombre, c.id)
        self.combo_cliente.blockSignals(False)
        self._filtrar_vehiculos_por_cliente()

    def _filtrar_vehiculos_por_cliente(self):
        c_id = self.combo_cliente.currentData()
        self.combo_vehiculos.blockSignals(True)
        self.combo_vehiculos.clear()

        if not c_id:
            self.combo_vehiculos.setEnabled(False)
            self.combo_vehiculos.blockSignals(False)
            self.cargar_historial()
            return

        self.combo_vehiculos.setEnabled(True)
        from services.taller_service import TallerService
        vehiculos = TallerService.obtener_vehiculos_por_cliente(c_id)
        for v in vehiculos:
            self.combo_vehiculos.addItem(f"{v.dominio} - {v.marca} {v.modelo}", v.id)

        self.combo_vehiculos.blockSignals(False)
        self.cargar_historial()

    def nuevo_vehiculo(self):
        c_id = self.combo_cliente.currentData()
        if not c_id:
            QMessageBox.warning(self, "Error", "Seleccione un cliente primero.")
            return
        d = NuevoVehiculoDialog(c_id, self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self._filtrar_vehiculos_por_cliente()

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

            # Cruzando datos para mostrar Patente
            patente_info = f"{g.vehiculo.dominio} ({g.vehiculo.marca})"

            self.table.setItem(row, 1, QTableWidgetItem(patente_info))
            self.table.setItem(row, 2, QTableWidgetItem(g.producto.nombre))
            self.table.setItem(row, 3, QTableWidgetItem(g.fecha_instalacion.strftime('%d/%m/%Y')))

            i_venc = QTableWidgetItem(g.fecha_vencimiento.strftime('%d/%m/%Y'))
            if g.fecha_vencimiento < QDate.currentDate().toPyDate():
                i_venc.setForeground(Qt.GlobalColor.red)
            self.table.setItem(row, 4, i_venc)

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

        # Selector de Cliente y Vehículo Superior
        header_lay = QVBoxLayout()

        # Cliente
        lay_cli = QHBoxLayout()
        self.combo_cliente = QComboBox()
        self.btn_recargar_c = QPushButton("Actualizar Clientes")
        self.btn_recargar_c.clicked.connect(self.cargar_clientes)
        lay_cli.addWidget(QLabel("Cliente:"))
        lay_cli.addWidget(self.combo_cliente)
        lay_cli.addWidget(self.btn_recargar_c)
        header_lay.addLayout(lay_cli)

        # Vehículo
        lay_veh = QHBoxLayout()
        self.combo_vehiculos = QComboBox()
        self.combo_vehiculos.setEnabled(False)
        self.btn_recargar_v = QPushButton("Actualizar Lista")
        self.btn_recargar_v.clicked.connect(self._filtrar_vehiculos_por_cliente)

        lay_veh.addWidget(QLabel("Vehículo:"))
        lay_veh.addWidget(self.combo_vehiculos)
        lay_veh.addWidget(self.btn_recargar_v)
        header_lay.addLayout(lay_veh)

        layout.addLayout(header_lay)

        # Conectar Cliente -> Vehículo
        self.combo_cliente.currentIndexChanged.connect(self._filtrar_vehiculos_por_cliente)

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

        self.btn_exportar_pdf_grilla = QPushButton("Exportar Historial a PDF")
        self.btn_exportar_pdf_grilla.clicked.connect(self._exportar_pdf)
        layout.addWidget(self.btn_exportar_pdf_grilla)

        self.combo_vehiculos.currentIndexChanged.connect(self.cargar_historial)

        self.table.itemDoubleClicked.connect(self._abrir_detalle_service)

    def _abrir_detalle_service(self, item):
        row = item.row()
        c_id_str = self.table.item(row, 0).text()
        if not c_id_str.isdigit(): return

        c_id = int(c_id_str)
        from ui.components.dialogs import DetalleServiceDialog
        dlg = DetalleServiceDialog(c_id, self)
        dlg.exec()

    def cargar_clientes(self):
        from database.conexion import get_session
        from database.models.cliente import Cliente
        from sqlalchemy import select
        self.combo_cliente.blockSignals(True)
        self.combo_cliente.clear()
        self.combo_cliente.addItem("Seleccione un Cliente...", None)
        with get_session() as s:
            clientes = s.scalars(select(Cliente).order_by(Cliente.nombre)).all()
            for c in clientes:
                self.combo_cliente.addItem(c.nombre, c.id)
        self.combo_cliente.blockSignals(False)
        self._filtrar_vehiculos_por_cliente()

    def _filtrar_vehiculos_por_cliente(self):
        c_id = self.combo_cliente.currentData()
        self.combo_vehiculos.blockSignals(True)
        self.combo_vehiculos.clear()

        if not c_id:
            self.combo_vehiculos.setEnabled(False)
            self.combo_vehiculos.blockSignals(False)
            self.cargar_historial()
            return

        self.combo_vehiculos.setEnabled(True)
        from services.taller_service import TallerService
        vehiculos = TallerService.obtener_vehiculos_por_cliente(c_id)
        for v in vehiculos:
            self.combo_vehiculos.addItem(f"{v.dominio} - {v.marca} {v.modelo}", v.id)

        self.combo_vehiculos.blockSignals(False)
        self.cargar_historial()

    def _exportar_pdf(self):
        from utils.export_utils import ExportUtils
        import os
        from PyQt6.QtWidgets import QFileDialog

        c_id = self.combo_cliente.currentData()
        if not c_id:
            QMessageBox.warning(self, "Error", "Seleccione un cliente primero.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Exportar PDF", f"Historial_Service_Cliente_{c_id}.pdf", "PDF Files (*.pdf)")
        if path:
            ExportUtils.exportar_tabla_a_pdf(self.table, f"Historial de Service - Cliente ID: {c_id}", path)
            QMessageBox.information(self, "Éxito", "Historial exportado correctamente.")

    def guardar_service(self):
        v_id = self.combo_vehiculos.currentData()
        if not v_id:
            QMessageBox.warning(self, "Error", "Debe seleccionar un vehículo.")
            return

        km_act = self.txt_km_act.value()
        km_prox = self.txt_km_prox.value()
        if km_act <= 0 or km_prox <= 0:
            QMessageBox.warning(self, "Error", "El Kilometraje Actual y Próximo deben ser mayores a 0.")
            return

        aceite = self.txt_aceite.text().strip()
        if not aceite:
            QMessageBox.warning(self, "Error", "Debe indicar el aceite utilizado.")
            return

        try:
            c = TallerService.registrar_cambio_aceite(
                vehiculo_id=v_id,
                km_actual=km_act,
                proximo_km=km_prox,
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
