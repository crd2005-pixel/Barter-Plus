from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QCheckBox, QPushButton, QMessageBox, QHBoxLayout, QLabel, QDoubleSpinBox
)
from services.cliente_service import ClienteService

class DeclaracionCiegaDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Declaración Ciega de Caja")
        self.setFixedSize(400, 150)
        from PyQt6.QtWidgets import QVBoxLayout, QLabel, QDoubleSpinBox, QHBoxLayout, QPushButton
        layout = QVBoxLayout(self)

        lbl = QLabel("Ingrese el dinero físico total contado en caja:")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(lbl)

        self.spin_monto = QDoubleSpinBox()
        self.spin_monto.setRange(0, 100000000)
        self.spin_monto.setDecimals(2)
        self.spin_monto.setPrefix("$ ")
        self.spin_monto.setStyleSheet("font-size: 24px; padding: 5px;")
        layout.addWidget(self.spin_monto)

        btn_box = QHBoxLayout()
        btn_ok = QPushButton("Aceptar")
        btn_ok.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; height: 35px;")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addStretch()
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_ok)
        layout.addLayout(btn_box)

    def get_monto(self):
        return self.spin_monto.value()


class FastClientDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo Cliente Rápido")
        self.nuevo_cliente_id = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_nombre = QLineEdit()
        self.txt_nombre.setPlaceholderText("Nombre y Apellido (Obligatorio)")
        self.txt_dni = QLineEdit()
        self.txt_dni.setPlaceholderText("DNI / CUIT")
        self.txt_celular = QLineEdit()
        self.txt_celular.setPlaceholderText("Teléfono / Celular")
        self.txt_direccion = QLineEdit()
        self.txt_direccion.setPlaceholderText("Dirección")
        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("Correo Electrónico")
        self.chk_especial = QCheckBox("Es Cliente VIP (Aplica descuentos 10%)")

        form.addRow("Nombre/Razón Social (*):", self.txt_nombre)
        form.addRow("DNI/CUIT:", self.txt_dni)
        form.addRow("Celular:", self.txt_celular)
        form.addRow("Dirección:", self.txt_direccion)
        form.addRow("Email:", self.txt_email)
        form.addRow("", self.chk_especial)
        layout.addLayout(form)

        self.btn_guardar = QPushButton("Guardar Cliente")
        self.btn_guardar.setStyleSheet("background-color: #0275d8; color: white; font-weight: bold;")
        self.btn_guardar.clicked.connect(self.guardar)
        layout.addWidget(self.btn_guardar)

    def guardar(self):
        if not self.txt_nombre.text().strip():
            QMessageBox.warning(self, "Error", "El nombre es obligatorio")
            return

        try:
            nuevo = ClienteService.crear_cliente(
                nombre=self.txt_nombre.text().strip(),
                dni=self.txt_dni.text().strip() or None,
                telefono=self.txt_celular.text().strip() or None,
                direccion=self.txt_direccion.text().strip() or None,
                email=self.txt_email.text().strip() or None,
                es_especial=self.chk_especial.isChecked()
            )
            self.nuevo_cliente_id = nuevo.id
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo crear: {e}")

class ItemManualDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ítem Manual / Servicio")
        self.data_item = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_desc = QLineEdit()
        self.txt_desc.setPlaceholderText("Ej. Mano de obra, Envío, Servicio...")

        self.spin_cant = QDoubleSpinBox()
        self.spin_cant.setRange(0.01, 99999.0)
        self.spin_cant.setValue(1.0)

        self.spin_precio = QDoubleSpinBox()
        self.spin_precio.setRange(0.01, 9999999.0)
        self.spin_precio.setPrefix("$ ")
        self.spin_precio.setValue(1000.0)

        form.addRow("Descripción:", self.txt_desc)
        form.addRow("Cantidad:", self.spin_cant)
        form.addRow("Precio Unitario:", self.spin_precio)
        layout.addLayout(form)

        self.btn_ok = QPushButton("Añadir al Carrito")
        self.btn_ok.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold;")
        self.btn_ok.clicked.connect(self.agregar)
        layout.addWidget(self.btn_ok)

    def agregar(self):
        if not self.txt_desc.text().strip():
            QMessageBox.warning(self, "Error", "Debe ingresar una descripción.")
            return

        self.data_item = {
            'id': None,
            'codigo': "MAN-001",
            'marca': "Servicio/Manual",
            'nombre': self.txt_desc.text().strip(),
            'precio_base': self.spin_precio.value(),
            'cantidad': self.spin_cant.value(),
            'descuento_unit': 0.0
        }
        self.accept()

from PyQt6.QtWidgets import QWidget, QSplitter, QComboBox, QDoubleSpinBox, QSpinBox, QFileDialog
from PyQt6.QtPrintSupport import QPrinter, QPrintPreviewWidget, QPrintDialog
from PyQt6.QtGui import QPainter, QFont, QPageSize, QPixmap, QFontMetrics, QPageLayout
from PyQt6.QtCore import QSizeF, QSettings, Qt, QRectF, QTimer, QMarginsF
import os
class ConfiguracionTicketDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Impresora de Tickets (POS)")
        self.resize(450, 400)

        from PyQt6.QtWidgets import QVBoxLayout, QFormLayout, QComboBox, QDoubleSpinBox, QSpinBox, QHBoxLayout, QPushButton, QLineEdit, QMessageBox, QFileDialog
        from PyQt6.QtCore import QSettings

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.cmb_printer = QComboBox()

        from PyQt6.QtPrintSupport import QPrinterInfo
        printers = [p.printerName() for p in QPrinterInfo.availablePrinters()]
        self.cmb_printer.addItems(printers)

        self.sp_width = QDoubleSpinBox()
        self.sp_width.setRange(20, 200)
        self.sp_width.setSuffix(" mm")
        self.sp_width.setValue(58.0)

        self.sp_margin_x = QDoubleSpinBox()
        self.sp_margin_x.setRange(0, 50)
        self.sp_margin_x.setSuffix(" mm")

        self.sp_margin_y = QDoubleSpinBox()
        self.sp_margin_y.setRange(0, 50)
        self.sp_margin_y.setSuffix(" mm")

        self.sp_font_size = QSpinBox()
        self.sp_font_size.setRange(5, 30)

        self.sp_logo_width = QSpinBox()
        self.sp_logo_width.setRange(50, 500)
        self.sp_logo_width.setSuffix(" px")
        self.sp_logo_width.setValue(150)

        self.txt_logo = QLineEdit()
        self.btn_logo = QPushButton("...")
        self.btn_logo.clicked.connect(self.browse_logo)
        lay_logo = QHBoxLayout()
        lay_logo.addWidget(self.txt_logo)
        lay_logo.addWidget(self.btn_logo)

        self.txt_address = QLineEdit()
        self.txt_phone = QLineEdit()

        form.addRow("Impresora:", self.cmb_printer)
        form.addRow("Ancho Papel:", self.sp_width)
        form.addRow("Margen X:", self.sp_margin_x)
        form.addRow("Margen Y:", self.sp_margin_y)
        form.addRow("Tamaño Fuente:", self.sp_font_size)
        form.addRow("Ancho Logo:", self.sp_logo_width)
        form.addRow("Logo:", lay_logo)
        form.addRow("Dirección:", self.txt_address)
        form.addRow("Teléfono:", self.txt_phone)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_save = QPushButton("Guardar")
        btn_save.clicked.connect(self.save_config)
        btn_box.addWidget(btn_save)

        layout.addLayout(btn_box)

        self.load_config()

    def browse_logo(self):
        import os
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar Logo", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.txt_logo.setText(path)

    def load_config(self):
        from PyQt6.QtCore import QSettings
        settings = QSettings("BarterPlus", "TicketConfig")
        printer_name = settings.value("printer_name", "")
        idx = self.cmb_printer.findText(printer_name)
        if idx >= 0:
            self.cmb_printer.setCurrentIndex(idx)

        self.sp_width.setValue(float(settings.value("width", 58.0)))
        self.sp_margin_x.setValue(float(settings.value("margin_x", 2.0)))
        self.sp_margin_y.setValue(float(settings.value("margin_y", 2.0)))
        self.sp_font_size.setValue(int(settings.value("font_size", 8)))
        self.txt_logo.setText(settings.value("logo_path", ""))
        self.txt_address.setText(settings.value("address", ""))
        self.txt_phone.setText(settings.value("phone", ""))
        self.sp_logo_width.setValue(int(settings.value("logo_width", 150)))

    def save_config(self):
        from PyQt6.QtCore import QSettings
        from PyQt6.QtWidgets import QMessageBox
        settings = QSettings("BarterPlus", "TicketConfig")
        settings.setValue("printer_name", self.cmb_printer.currentText())
        settings.setValue("width", self.sp_width.value())
        settings.setValue("margin_x", self.sp_margin_x.value())
        settings.setValue("margin_y", self.sp_margin_y.value())
        settings.setValue("font_size", self.sp_font_size.value())
        settings.setValue("logo_path", self.txt_logo.text())
        settings.setValue("address", self.txt_address.text())
        settings.setValue("phone", self.txt_phone.text())
        settings.setValue("logo_width", self.sp_logo_width.value())

        QMessageBox.information(self, "Éxito", "Configuración de Tickets guardada.")
        self.accept()

class TicketPreviewDialog(QDialog):
    def __init__(self, venta, detalles_final, cliente_nombre="Consumidor Final", parent=None):
        super().__init__(parent)
        self.venta = venta
        self.detalles_final = detalles_final
        self.cliente_nombre = cliente_nombre
        self.setWindowTitle("Impresión de Ticket")
        self.resize(500, 700)

        self.settings = QSettings("BarterPlus", "TicketConfig")

        main_layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.btn_config = QPushButton("Ajustes Predeterminados")
        self.btn_config.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold; height: 35px;")
        self.btn_config.clicked.connect(self.open_config)

        self.btn_imprimir = QPushButton("Imprimir Ticket")
        self.btn_imprimir.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; height: 35px;")
        self.btn_imprimir.clicked.connect(self.imprimir)

        toolbar.addWidget(self.btn_config)
        toolbar.addStretch()
        toolbar.addWidget(self.btn_imprimir)

        main_layout.addLayout(toolbar)

        self.printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
        self.preview = QPrintPreviewWidget(self.printer)

        # Sobrescritura de QPalette estricta para ignorar Tema Oscuro
        from PyQt6.QtGui import QPalette, QColor
        paleta = self.preview.palette()
        paleta.setColor(QPalette.ColorRole.Base, QColor("white"))
        paleta.setColor(QPalette.ColorRole.Text, QColor("black"))
        paleta.setColor(QPalette.ColorRole.WindowText, QColor("black"))
        self.preview.setPalette(paleta)

        self.preview.paintRequested.connect(self.paint_preview)

        main_layout.addWidget(self.preview)

        QTimer.singleShot(100, self.preview.updatePreview)

    def open_config(self):
        dlg = ConfiguracionTicketDialog(self)
        if dlg.exec():
            self.preview.updatePreview()

    def paint_preview(self, printer):
        from PyQt6.QtGui import QPageSize, QPageLayout, QTextDocument
        from PyQt6.QtCore import QSizeF, Qt, QMarginsF
        from PyQt6.QtPrintSupport import QPrinter
        import os

        # Configuración básica
        w_mm = float(self.settings.value("width", 58.0))
        margin_x = float(self.settings.value("margin_x", 2.0))
        margin_y = float(self.settings.value("margin_y", 2.0))
        font_size = int(self.settings.value("font_size", 12))
        logo_path = self.settings.value("logo_path", "")
        logo_width = int(self.settings.value("logo_width", 150))

        # Extracción segura
        address = str(self.settings.value("address", "Avenida Libertador Sur 415 - Gral. Alvear - Mza.")).strip()
        phone = str(self.settings.value("phone", "2625-582956 // 2625-416889")).strip()
        if not address: address = "Avenida Libertador Sur 415 - Gral. Alvear - Mza."
        if not phone: phone = "2625-582956 // 2625-416889"

        leyenda = self.venta.tipo_comprobante if self.venta.tipo_comprobante else "Remito"

        cliente_nombre = getattr(self, 'cliente_nombre', "Consumidor Final")
        if not cliente_nombre: cliente_nombre = "Consumidor Final"

        margins = QMarginsF(margin_x, margin_y, margin_x, margin_y)
        printer.setPageMargins(margins, QPageLayout.Unit.Millimeter)

        logo_html = ""
        if logo_path and os.path.exists(logo_path):
            logo_html = f'<div align="center"><img src="file:///{os.path.abspath(logo_path).replace(chr(92), "/")}" width="{logo_width}px"></div>'

        items_html = ""
        for item in self.detalles_final:
            nombre = item.get('nombre', '')
            cant = item.get('cantidad', 1)
            subt = item.get('subtotal', 0.0)
            items_html += f"<tr><td align='left'>{cant}x {nombre}</td><td align='right'>${subt:.2f}</td></tr>"

        html_ticket = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <style>
            * {{
                box-sizing: border-box;
                font-family: monospace, sans-serif;
            }}
            body {{
                width: 100%;
                margin: 0;
                padding: 0 2px;
                font-size: {font_size}px;
                line-height: 1.4;
                word-wrap: break-word;
                overflow-wrap: break-word;
                white-space: normal;
            }}
            table {{ width: 100%; border-collapse: collapse; margin: 5px 0; }}
            th, td {{ padding: 2px 0; vertical-align: top; }}
        </style>
        </head>
        <body>
            <font color="black">
                {logo_html}
                <div align="center">
                    <p><b>[{'X'}] {leyenda}</b></p>
                    <p>Cliente: {cliente_nombre}</p>
                </div>
                <hr>
                <p>Venta ID: {self.venta.id}<br>Fecha: {self.venta.fecha.strftime('%d/%m/%Y %H:%M')}</p>
                <hr>
                <table>
                    {items_html}
                </table>
                <hr>
                <div align="right" style="font-weight: bold; font-size: 1.1em; margin-top: 5px;">
                    TOTAL: ${self.venta.total:.2f}
                </div>
                <p><b>Pago:</b> {self.venta.metodo_pago}</p>
                <hr>
                <div align="center">
                    <p>{address}</p>
                    <p>{phone}</p>
                    <br>
                    <p><b>¡Lo esperamos nuevamente!</b></p>
                </div>
            </font>
        </body>
        </html>
        """

        document = QTextDocument()
        document.setDefaultStyleSheet("body { color: #000000; background-color: #ffffff; } p, table, th, td, div { color: #000000; }")
        document.setHtml(html_ticket)

        printer.setFullPage(True)
        document.setTextWidth(printer.pageLayout().paintRectPixels(printer.resolution()).width())

        doc_height_px = document.size().height()
        dpi = printer.resolution()
        alto_total_mm = (doc_height_px / dpi) * 25.4 + margin_y * 2

        if alto_total_mm < 50.0: alto_total_mm = 50.0
        if alto_total_mm > 1000.0: alto_total_mm = 1000.0

        size = QPageSize(QSizeF(w_mm, alto_total_mm), QPageSize.Unit.Millimeter, "", QPageSize.SizeMatchPolicy.ExactMatch)
        printer.setPageSize(size)
        printer.setPageMargins(margins, QPageLayout.Unit.Millimeter)

        document.print(printer)

    def imprimir(self):
        from PyQt6.QtPrintSupport import QPrinter
        from PyQt6.QtWidgets import QMessageBox

        print_job = QPrinter(QPrinter.PrinterMode.HighResolution)
        print_job.setOutputFormat(QPrinter.OutputFormat.NativeFormat)

        # Obtener y forzar nombre de impresora configurada directamente
        printer_name = self.settings.value("printer_name", "POS-80")
        if printer_name:
            print_job.setPrinterName(printer_name)

        # Imprimir de forma silenciosa
        self.paint_preview(print_job)

        # Enviar aviso temporal de finalización para la interfaz sin bloquear con prompts extras (sólo informativo)
        QMessageBox.information(self, "Impresión", f"Enviando ticket a {printer_name}...")
        self.accept()

class DetalleVentaDialog(QDialog):
    def __init__(self, venta_id, parent=None, es_presupuesto=False):
        super().__init__(parent)
        title = f"Detalle de Presupuesto #{venta_id}" if es_presupuesto else f"Detalle de Venta #{venta_id}"
        self.setWindowTitle(title)
        self.resize(600, 400)
        from PyQt6.QtWidgets import QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView
        from database.conexion import get_session

        layout = QVBoxLayout(self)

        from PyQt6.QtWidgets import QHBoxLayout, QLabel
        # 2. Creación e Inyección Física de la Cabecera
        layout_cabecera = QHBoxLayout()
        self.lbl_cliente = QLabel("Cliente: Cargando...")
        self.lbl_metodo_pago = QLabel("Pago: Cargando...")
        self.lbl_fecha = QLabel("Fecha: Cargando...")
        layout_cabecera.addWidget(self.lbl_cliente)
        layout_cabecera.addWidget(self.lbl_metodo_pago)
        layout_cabecera.addWidget(self.lbl_fecha)
        layout.addLayout(layout_cabecera)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(4)
        self.tabla.setHorizontalHeaderLabels(["Producto", "Cantidad", "Precio Unitario", "Subtotal"])
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.tabla)

        with get_session() as session:
            if es_presupuesto:
                from database.models.presupuestos import DetallePresupuesto, Presupuesto
                from sqlalchemy.orm import joinedload
                doc = session.query(Presupuesto).options(joinedload(Presupuesto.cliente)).filter(Presupuesto.id == venta_id).first()
                detalles = session.query(DetallePresupuesto).filter(DetallePresupuesto.presupuesto_id == venta_id).all()
                if doc:
                    c_nom = doc.cliente.nombre if doc.cliente else "Consumidor Final / Genérico"
                    self.lbl_cliente.setText(f"<b>Cliente:</b> {c_nom}")
                    self.lbl_metodo_pago.setText(f"<b>Pago:</b> N/A")
                    self.lbl_fecha.setText(f"<b>Fecha:</b> {doc.fecha.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                from database.models.venta import DetalleVenta, Venta
                from sqlalchemy.orm import joinedload
                doc = session.query(Venta).options(joinedload(Venta.cliente)).filter(Venta.id == venta_id).first()
                detalles = session.query(DetalleVenta).filter(DetalleVenta.venta_id == venta_id).all()
                if doc:
                    c_nom = doc.cliente.nombre if doc.cliente else "Consumidor Final"
                    self.lbl_cliente.setText(f"<b>Cliente:</b> {c_nom}")
                    self.lbl_metodo_pago.setText(f"<b>Pago:</b> {doc.metodo_pago}")
                    self.lbl_fecha.setText(f"<b>Fecha:</b> {doc.fecha.strftime('%Y-%m-%d %H:%M:%S')}")

            self.tabla.setRowCount(len(detalles))
            for i, det in enumerate(detalles):
                self.tabla.setItem(i, 0, QTableWidgetItem(det.descripcion))
                self.tabla.setItem(i, 1, QTableWidgetItem(f"{det.cantidad:.2f}"))
                self.tabla.setItem(i, 2, QTableWidgetItem(f"$ {det.precio_unitario:.2f}"))
                self.tabla.setItem(i, 3, QTableWidgetItem(f"$ {det.subtotal:.2f}"))

class DetalleCajaDialog(QDialog):
    def __init__(self, caja_id, parent=None):
        super().__init__(parent)
        self.caja_id = caja_id
        self.setWindowTitle(f"Auditoría de Caja #{caja_id}")
        self.resize(800, 600)
        self.setup_ui()

    def setup_ui(self):
        from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit
        from database.conexion import get_session
        from database.models.caja import Caja, MovimientoCaja

        layout = QVBoxLayout(self)

        with get_session() as session:
            from sqlalchemy.orm import joinedload
            caja = session.query(Caja).options(joinedload(Caja.movimientos)).filter(Caja.id == self.caja_id).first()
            if not caja:
                layout.addWidget(QLabel("Error: Caja no encontrada."))
                return

            # Header Details
            form = QFormLayout()
            form.addRow("Fecha Apertura:", QLabel(caja.fecha_apertura.strftime("%Y-%m-%d %H:%M:%S")))
            form.addRow("Fecha Cierre:", QLabel(caja.fecha_cierre.strftime("%Y-%m-%d %H:%M:%S") if caja.fecha_cierre else "Pendiente"))
            form.addRow("Monto Inicial:", QLabel(f"${caja.saldo_inicial:.2f}"))
            form.addRow("Monto Esperado (Sistema):", QLabel(f"${caja.saldo_final_esperado:.2f}"))
            form.addRow("Monto Real (Físico):", QLabel(f"${caja.saldo_final_real:.2f}"))

            lbl_dif = QLabel(f"${caja.diferencia:.2f}")
            if caja.diferencia < 0: lbl_dif.setStyleSheet("color: red; font-weight: bold;")
            elif caja.diferencia > 0: lbl_dif.setStyleSheet("color: green; font-weight: bold;")
            form.addRow("Diferencia:", lbl_dif)

            layout.addLayout(form)

            layout.addWidget(QLabel("Observaciones de Cierre:"))
            txt_obs = QTextEdit()
            txt_obs.setReadOnly(True)
            txt_obs.setPlainText(caja.notas if caja.notas else "Sin observaciones registradas.")
            txt_obs.setMaximumHeight(80)
            layout.addWidget(txt_obs)

            layout.addWidget(QLabel("Movimientos de Turno:"))

            # Grid
            self.tabla_movimientos = QTableWidget(0, 5)
            tabla = self.tabla_movimientos
            tabla.setHorizontalHeaderLabels(["Hora", "Tipo", "Concepto", "Método", "Monto"])
            tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            tabla.cellDoubleClicked.connect(self._abrir_detalle_venta)
            layout.addWidget(tabla)

            # Insert data
            movimientos = sorted(caja.movimientos, key=lambda m: m.fecha)
            tabla.setRowCount(len(movimientos))
            for i, mov in enumerate(movimientos):
                from PyQt6.QtCore import Qt
                item_hora = QTableWidgetItem(mov.fecha.strftime("%H:%M:%S"))
                if getattr(mov, 'venta_id', None):
                    item_hora.setData(Qt.ItemDataRole.UserRole, mov.venta_id)
                tabla.setItem(i, 0, item_hora)
                tabla.setItem(i, 1, QTableWidgetItem(mov.tipo))
                tabla.setItem(i, 2, QTableWidgetItem(mov.concepto))
                tabla.setItem(i, 3, QTableWidgetItem(mov.metodo))
                tabla.setItem(i, 4, QTableWidgetItem(f"${mov.monto:.2f}"))

            from PyQt6.QtWidgets import QPushButton
            btn_box = QHBoxLayout()
            btn_export = QPushButton("Exportar Movimientos")
            btn_export.clicked.connect(self._exportar_movimientos)
            btn_cerrar = QPushButton("Cerrar")
            btn_cerrar.clicked.connect(self.accept)
            btn_box.addWidget(btn_export)
            btn_box.addStretch()
            btn_box.addWidget(btn_cerrar)
            layout.addLayout(btn_box)

    def _exportar_movimientos(self):
        from utils.export_utils import ExportUtils
        ExportUtils.exportar_tabla_csv(self.tabla_movimientos, self, f"Caja_Turno_{self.caja_id}")

    def _abrir_detalle_venta(self, row, col):
        from PyQt6.QtCore import Qt
        item_hora = self.tabla_movimientos.item(row, 0)
        if not item_hora: return
        venta_id = item_hora.data(Qt.ItemDataRole.UserRole)
        if not venta_id: return

        dlg = DetalleVentaDialog(venta_id, self)
        dlg.exec()

class CierreCajaDialog(QDialog):
    def __init__(self, caja_id, parent=None):
        super().__init__(parent)
        self.caja_id = caja_id
        self.setWindowTitle(f"Arqueo y Cierre de Caja #{caja_id}")
        self.resize(800, 700)
        self.saldo_esperado = 0.0
        self.setup_ui()

    def setup_ui(self):
        from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QDoubleSpinBox, QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit, QPushButton
        from PyQt6.QtCore import Qt
        from database.conexion import get_session
        from database.models.caja import Caja
        from services.caja_service import CajaService

        layout = QVBoxLayout(self)

        self.saldo_esperado = CajaService.calcular_saldo_efectivo(self.caja_id)

        # 1. Sección Superior (Cálculo)
        form = QFormLayout()
        lbl_esperado = QLabel(f"${self.saldo_esperado:.2f}")
        lbl_esperado.setStyleSheet("font-size: 20px; font-weight: bold; color: #2980b9;")
        form.addRow("Monto Esperado (Efectivo):", lbl_esperado)

        self.spin_real = QDoubleSpinBox()
        self.spin_real.setRange(0, 100000000)
        self.spin_real.setDecimals(2)
        self.spin_real.setPrefix("$ ")
        self.spin_real.setStyleSheet("font-size: 20px; padding: 5px;")
        self.spin_real.valueChanged.connect(self._actualizar_diferencia)
        form.addRow("Monto Físico Declarado:", self.spin_real)

        self.lbl_dif = QLabel("$0.00")
        self.lbl_dif.setStyleSheet("font-size: 20px; font-weight: bold;")
        form.addRow("Diferencia:", self.lbl_dif)
        layout.addLayout(form)

        # 2. Sección Central (Auditoría Activa)
        layout.addWidget(QLabel("Movimientos de este Turno:"))
        self.tabla_movimientos = QTableWidget(0, 5)
        self.tabla_movimientos.setHorizontalHeaderLabels(["Hora", "Tipo", "Concepto", "Método", "Monto"])
        self.tabla_movimientos.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla_movimientos.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_movimientos.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_movimientos.cellDoubleClicked.connect(self._abrir_detalle_venta)
        layout.addWidget(self.tabla_movimientos)

        # Cargar Movimientos
        with get_session() as session:
            from sqlalchemy.orm import joinedload
            caja = session.query(Caja).options(joinedload(Caja.movimientos)).filter(Caja.id == self.caja_id).first()
            if caja:
                movs = sorted(caja.movimientos, key=lambda m: m.fecha)
                self.tabla_movimientos.setRowCount(len(movs))
                for i, mov in enumerate(movs):
                    item_hora = QTableWidgetItem(mov.fecha.strftime("%H:%M:%S"))
                    if getattr(mov, 'venta_id', None):
                        item_hora.setData(Qt.ItemDataRole.UserRole, mov.venta_id)
                    self.tabla_movimientos.setItem(i, 0, item_hora)
                    self.tabla_movimientos.setItem(i, 1, QTableWidgetItem(mov.tipo))
                    self.tabla_movimientos.setItem(i, 2, QTableWidgetItem(mov.concepto))
                    self.tabla_movimientos.setItem(i, 3, QTableWidgetItem(mov.metodo))
                    self.tabla_movimientos.setItem(i, 4, QTableWidgetItem(f"${mov.monto:.2f}"))

        # 3. Sección Inferior (Justificación y Guardado)
        layout.addWidget(QLabel("Observaciones (Justificar faltantes o sobrantes):"))
        self.txt_obs = QTextEdit()
        self.txt_obs.setMaximumHeight(80)
        layout.addWidget(self.txt_obs)

        btn_box = QHBoxLayout()
        btn_cerrar = QPushButton("Confirmar y Cerrar Caja")
        btn_cerrar.setStyleSheet("background-color: #d35400; color: white; font-weight: bold; height: 40px; font-size: 16px;")
        btn_cerrar.clicked.connect(self.accept)
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)

        btn_box.addStretch()
        btn_box.addWidget(btn_cancelar)
        btn_box.addWidget(btn_cerrar)
        layout.addLayout(btn_box)

        self._actualizar_diferencia()

    def _actualizar_diferencia(self):
        dif = self.monto_declarado - self.saldo_esperado
        self.lbl_dif.setText(f"${dif:.2f}")
        if dif < 0:
            self.lbl_dif.setStyleSheet("font-size: 20px; font-weight: bold; color: red;")
        elif dif > 0:
            self.lbl_dif.setStyleSheet("font-size: 20px; font-weight: bold; color: green;")
        else:
            self.lbl_dif.setStyleSheet("font-size: 20px; font-weight: bold; color: black;")

    def _abrir_detalle_venta(self, row, col):
        from PyQt6.QtCore import Qt
        item_hora = self.tabla_movimientos.item(row, 0)
        if not item_hora: return
        venta_id = item_hora.data(Qt.ItemDataRole.UserRole)
        if not venta_id: return

        dlg = DetalleVentaDialog(venta_id, self)
        dlg.exec()

    def get_data(self):
        return self.spin_real.value(), self.txt_obs.toPlainText().strip()

class PanelArqueoCajaDialog(QDialog):
    def __init__(self, caja_id, monto_declarado, parent=None):
        super().__init__(parent)
        self.caja_id = caja_id
        self.monto_declarado = monto_declarado
        self.setWindowTitle(f"Arqueo y Cierre de Caja #{caja_id}")
        self.resize(800, 700)
        self.saldo_esperado = 0.0
        self.setup_ui()

    def setup_ui(self):
        from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QDoubleSpinBox, QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit, QPushButton, QMessageBox
        from PyQt6.QtCore import Qt
        from database.conexion import get_session
        from database.models.caja import Caja
        from services.caja_service import CajaService

        layout = QVBoxLayout(self)

        self.saldo_esperado = CajaService.calcular_saldo_efectivo(self.caja_id)

        # 1. Sección Superior (Cálculo)
        form = QFormLayout()
        lbl_esperado = QLabel(f"${self.saldo_esperado:.2f}")
        lbl_esperado.setStyleSheet("font-size: 20px; font-weight: bold; color: #2980b9;")
        form.addRow("Monto Esperado (Sistema):", lbl_esperado)

        lbl_declarado = QLabel(f"${self.monto_declarado:.2f}")
        lbl_declarado.setStyleSheet("font-size: 20px; font-weight: bold; color: #f39c12;")
        form.addRow("Monto Declarado (Físico):", lbl_declarado)

        self.lbl_dif = QLabel("$0.00")
        self.lbl_dif.setStyleSheet("font-size: 20px; font-weight: bold;")
        form.addRow("Diferencia:", self.lbl_dif)
        layout.addLayout(form)

        # 2. Sección Central (Auditoría Activa)
        layout.addWidget(QLabel("Movimientos de este Turno:"))
        self.tabla_movimientos = QTableWidget(0, 5)
        self.tabla_movimientos.setHorizontalHeaderLabels(["Hora", "Tipo", "Concepto", "Método", "Monto"])
        self.tabla_movimientos.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla_movimientos.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_movimientos.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_movimientos.cellDoubleClicked.connect(self._abrir_detalle_venta)
        layout.addWidget(self.tabla_movimientos)

        # Cargar Movimientos
        with get_session() as session:
            from sqlalchemy.orm import joinedload
            caja = session.query(Caja).options(joinedload(Caja.movimientos)).filter(Caja.id == self.caja_id).first()
            if caja:
                movs = sorted(caja.movimientos, key=lambda m: m.fecha)
                self.tabla_movimientos.setRowCount(len(movs))
                for i, mov in enumerate(movs):
                    item_hora = QTableWidgetItem(mov.fecha.strftime("%H:%M:%S"))
                    if getattr(mov, 'venta_id', None):
                        item_hora.setData(Qt.ItemDataRole.UserRole, mov.venta_id)
                    self.tabla_movimientos.setItem(i, 0, item_hora)
                    self.tabla_movimientos.setItem(i, 1, QTableWidgetItem(mov.tipo))
                    self.tabla_movimientos.setItem(i, 2, QTableWidgetItem(mov.concepto))
                    self.tabla_movimientos.setItem(i, 3, QTableWidgetItem(mov.metodo))
                    self.tabla_movimientos.setItem(i, 4, QTableWidgetItem(f"${mov.monto:.2f}"))

        # 3. Sección Inferior (Justificación y Guardado)
        layout.addWidget(QLabel("Observaciones y justificaciones:"))
        self.txt_obs = QTextEdit()
        self.txt_obs.setMaximumHeight(80)
        layout.addWidget(self.txt_obs)

        btn_box = QHBoxLayout()
        btn_cerrar = QPushButton("Confirmar y Cerrar Turno Definitivamente")
        btn_cerrar.setStyleSheet("background-color: #d35400; color: white; font-weight: bold; height: 40px; font-size: 16px;")
        btn_cerrar.clicked.connect(self.ejecutar_cierre)
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)

        btn_box.addStretch()
        btn_box.addWidget(btn_cancelar)
        btn_box.addWidget(btn_cerrar)
        layout.addLayout(btn_box)

        self._actualizar_diferencia()

    def _actualizar_diferencia(self):
        dif = self.monto_declarado - self.saldo_esperado
        self.lbl_dif.setText(f"${dif:.2f}")
        if dif < 0:
            self.lbl_dif.setStyleSheet("font-size: 20px; font-weight: bold; color: red;")
        elif dif > 0:
            self.lbl_dif.setStyleSheet("font-size: 20px; font-weight: bold; color: green;")
        else:
            self.lbl_dif.setStyleSheet("font-size: 20px; font-weight: bold; color: black;")

    def _abrir_detalle_venta(self, row, col):
        from PyQt6.QtCore import Qt
        item_hora = self.tabla_movimientos.item(row, 0)
        if not item_hora: return
        venta_id = item_hora.data(Qt.ItemDataRole.UserRole)
        if not venta_id: return

        dlg = DetalleVentaDialog(venta_id, self)
        dlg.exec()

    def ejecutar_cierre(self):
        from services.caja_service import CajaService
        from PyQt6.QtWidgets import QMessageBox

        monto_real = self.monto_declarado
        dif = monto_real - self.saldo_esperado
        observaciones = self.txt_obs.toPlainText().strip()

        if abs(dif) > 0.01 and not observaciones:
            QMessageBox.warning(self, "Auditoría Fallida", "Existe una diferencia en caja. DEBE ingresar una justificación en las observaciones antes de poder cerrar el turno.")
            self.txt_obs.setFocus()
            return

        try:
            CajaService.cerrar_caja(self.caja_id, monto_real, observaciones)
            QMessageBox.information(self, "Éxito", "Caja cerrada correctamente.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al cerrar caja:\n{str(e)}")

class CargarChequeDialog(QDialog):
    def __init__(self, monto_sugerido, parent=None):
        super().__init__(parent)
        self.monto_sugerido = monto_sugerido
        self.setWindowTitle("Registrar Cheque")
        self.resize(450, 450)
        self.setup_ui()

    def setup_ui(self):
        from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QComboBox, QDoubleSpinBox, QPushButton, QDateEdit
        from PyQt6.QtCore import QDate

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_banco = QLineEdit()
        self.txt_numero = QLineEdit()

        self.date_conformacion = QDateEdit()
        self.date_conformacion.setCalendarPopup(True)
        self.date_conformacion.setDate(QDate.currentDate())

        self.date_vencimiento = QDateEdit()
        self.date_vencimiento.setCalendarPopup(True)
        self.date_vencimiento.setDate(QDate.currentDate().addDays(30))

        self.combo_tipo = QComboBox()
        self.combo_tipo.addItems(["Diferido", "Al Día"])

        self.txt_nombre = QLineEdit()
        self.txt_cuit = QLineEdit()
        self.txt_endoso = QLineEdit()
        self.txt_endoso.setPlaceholderText("Opcional")

        self.spin_monto = QDoubleSpinBox()
        self.spin_monto.setRange(0, 100000000)
        self.spin_monto.setDecimals(2)
        self.spin_monto.setPrefix("$ ")
        self.spin_monto.setValue(self.monto_sugerido)
        # Assuming we can allow partials for mixed payments, we'll leave it editable

        form.addRow("Banco:", self.txt_banco)
        form.addRow("Número:", self.txt_numero)
        form.addRow("F. Conformación:", self.date_conformacion)
        form.addRow("F. Vencimiento:", self.date_vencimiento)
        form.addRow("Tipo:", self.combo_tipo)
        form.addRow("Emisor:", self.txt_nombre)
        form.addRow("CUIT:", self.txt_cuit)
        form.addRow("Endoso:", self.txt_endoso)
        form.addRow("Monto:", self.spin_monto)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_ok = QPushButton("Registrar")
        btn_ok.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; height: 35px;")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)

        btn_box.addStretch()
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_ok)
        layout.addLayout(btn_box)

    def get_data(self):
        return {
            "banco": self.txt_banco.text().strip(),
            "numero_cheque": self.txt_numero.text().strip(),
            "fecha_conformacion": self.date_conformacion.date().toPyDate(),
            "fecha_vencimiento": self.date_vencimiento.date().toPyDate(),
            "tipo_cheque": self.combo_tipo.currentText(),
            "nombre_emisor": self.txt_nombre.text().strip(),
            "cuit": self.txt_cuit.text().strip(),
            "endoso": self.txt_endoso.text().strip(),
            "monto": self.spin_monto.value()
        }


class CobroCombinadoDialog(QDialog):
    def __init__(self, total_venta, parent=None):
        super().__init__(parent)
        self.total_venta = total_venta
        self.setWindowTitle("Cobro Combinado")
        self.resize(450, 450)

        from PyQt6.QtWidgets import QVBoxLayout, QFormLayout, QDoubleSpinBox, QLabel, QPushButton, QHBoxLayout, QMessageBox, QComboBox
        from PyQt6.QtCore import Qt

        self.layout = QVBoxLayout(self)
        self.form = QFormLayout()

        self.spin_efectivo = QDoubleSpinBox()
        self.spin_transferencia = QDoubleSpinBox()
        self.spin_debito = QDoubleSpinBox()
        self.spin_credito = QDoubleSpinBox()
        self.spin_cta_cte = QDoubleSpinBox()
        self.spin_cheque = QDoubleSpinBox()

        for spin in [self.spin_efectivo, self.spin_transferencia, self.spin_debito, self.spin_credito, self.spin_cta_cte, self.spin_cheque]:
            spin.setRange(0.0, 9999999.0)
            spin.setDecimals(2)
            spin.setPrefix("$ ")
            spin.valueChanged.connect(self._calcular_totales)

        self.combo_tarjeta = QComboBox()
        self.combo_tarjeta.setEnabled(False)

        self.combo_plan = QComboBox()
        self.combo_plan.setEnabled(False)

        self.lbl_detalle_cuotas = QLabel("")
        self.lbl_detalle_cuotas.setStyleSheet("color: #7f8c8d; font-style: italic; font-weight: bold;")
        self.lbl_detalle_cuotas.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.spin_credito.valueChanged.connect(self._toggle_credito)
        self.spin_credito.valueChanged.connect(self._actualizar_detalle_cuotas)
        self.combo_plan.currentTextChanged.connect(self._actualizar_detalle_cuotas)

        self.form.addRow("Efectivo:", self.spin_efectivo)
        self.form.addRow("Transferencia:", self.spin_transferencia)
        self.form.addRow("Débito:", self.spin_debito)
        self.form.addRow("Tarjeta de Crédito:", self.spin_credito)
        self.form.addRow("  - Tarjeta:", self.combo_tarjeta)
        self.form.addRow("  - Plan:", self.combo_plan)
        self.form.addRow("", self.lbl_detalle_cuotas)
        self.form.addRow("Cuenta Corriente:", self.spin_cta_cte)
        self.form.addRow("Cheque:", self.spin_cheque)

        self.layout.addLayout(self.form)

        self.lbl_total = QLabel(f"Total a Pagar: $ {self.total_venta:.2f}")
        self.lbl_total.setStyleSheet("font-weight: bold; font-size: 16px;")

        self.lbl_diferencia = QLabel("Diferencia: $ 0.00")
        self.lbl_diferencia.setStyleSheet("font-weight: bold; font-size: 16px; color: red;")

        self.layout.addWidget(self.lbl_total)
        self.layout.addWidget(self.lbl_diferencia)

        btn_box = QHBoxLayout()
        self.btn_confirmar = QPushButton("Confirmar Cobro")
        self.btn_confirmar.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.btn_confirmar.setEnabled(False)
        self.btn_confirmar.clicked.connect(self._intentar_confirmar)

        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.clicked.connect(self.reject)

        btn_box.addWidget(self.btn_confirmar)
        btn_box.addWidget(self.btn_cancelar)

        self.layout.addLayout(btn_box)

        self.datos_cheque = None
        self._cargar_tarjetas()
        self.combo_tarjeta.currentTextChanged.connect(self._actualizar_planes_tarjeta)
        self._calcular_totales()

    def _cargar_tarjetas(self):
        from database.conexion import get_session
        from database.models import ConfiguracionTarjeta

        self.combo_tarjeta.blockSignals(True)
        self.combo_tarjeta.clear()
        try:
            with get_session() as session:
                bancos = session.query(ConfiguracionTarjeta.banco_tarjeta).distinct().all()
                if bancos:
                    for b in bancos:
                        self.combo_tarjeta.addItem(b[0])
                else:
                    self.combo_tarjeta.addItem("Sin Configurar")
        except Exception:
            pass
        finally:
            self.combo_tarjeta.blockSignals(False)
            self._actualizar_planes_tarjeta()

    def _actualizar_planes_tarjeta(self):
        from database.conexion import get_session
        from database.models import ConfiguracionTarjeta

        self.combo_plan.blockSignals(True)
        self.combo_plan.clear()

        tarjeta_sel = self.combo_tarjeta.currentText()
        if not tarjeta_sel or tarjeta_sel == "Sin Configurar":
            self.combo_plan.addItem("Sin Configurar")
            self.combo_plan.blockSignals(False)
            self._actualizar_detalle_cuotas()
            return

        try:
            with get_session() as session:
                planes = session.query(ConfiguracionTarjeta).where(ConfiguracionTarjeta.banco_tarjeta == tarjeta_sel).all()
                if planes:
                    for p in planes:
                        self.combo_plan.addItem(f"{p.cuotas} Cuotas")
                else:
                    self.combo_plan.addItem("Sin Configurar")
        except Exception:
            pass
        finally:
            self.combo_plan.blockSignals(False)
            self._actualizar_detalle_cuotas()

    def _toggle_credito(self):
        val = self.spin_credito.value() > 0
        self.combo_tarjeta.setEnabled(val)
        self.combo_plan.setEnabled(val)

    def _actualizar_detalle_cuotas(self):
        monto = self.spin_credito.value()
        plan_str = self.combo_plan.currentText()

        if monto <= 0 or not plan_str:
            self.lbl_detalle_cuotas.setText("")
            return

        try:
            if "Pago" in plan_str:
                cuotas = 1
            else:
                cuotas = int(plan_str.split()[0])

            if cuotas > 1:
                valor_cuota = monto / cuotas
                self.lbl_detalle_cuotas.setText(f"({cuotas} cuotas de ${valor_cuota:.2f})")
            else:
                self.lbl_detalle_cuotas.setText("")
        except (ValueError, ZeroDivisionError):
            self.lbl_detalle_cuotas.setText("")

    def _calcular_totales(self):
        suma = (self.spin_efectivo.value() + self.spin_transferencia.value() +
                self.spin_debito.value() + self.spin_credito.value() +
                self.spin_cta_cte.value() + self.spin_cheque.value())

        diff = self.total_venta - suma
        self.lbl_diferencia.setText(f"Diferencia: $ {diff:.2f}")

        if abs(diff) < 0.01:
            self.lbl_diferencia.setStyleSheet("font-weight: bold; font-size: 16px; color: green;")
            self.btn_confirmar.setEnabled(True)
        else:
            self.lbl_diferencia.setStyleSheet("font-weight: bold; font-size: 16px; color: red;")
            self.btn_confirmar.setEnabled(False)

    def _intentar_confirmar(self):
        if self.spin_cheque.value() > 0:
            from ui.components.dialogs import CargarChequeDialog
            from PyQt6.QtWidgets import QDialog
            dlg = CargarChequeDialog(self.spin_cheque.value(), self)
            if dlg.exec() == int(QDialog.DialogCode.Accepted):
                self.datos_cheque = dlg.get_data()
            else:
                return # Abort

        self.accept()

    def get_datos(self):
        datos = {
            "Efectivo": self.spin_efectivo.value(),
            "Transferencia": self.spin_transferencia.value(),
            "Débito": self.spin_debito.value(),
            "Tarjeta de Crédito": self.spin_credito.value(),
            "Cuenta Corriente": self.spin_cta_cte.value(),
            "Cheque": self.spin_cheque.value(),
            "datos_cheque": self.datos_cheque
        }

        if self.spin_credito.value() > 0:
            datos["datos_tarjeta"] = {
                "tarjeta": self.combo_tarjeta.currentText(),
                "plan": self.combo_plan.currentText()
            }

        return datos

class ConfirmacionPosnetDialog(QDialog):
    def __init__(self, monto_financiar, parent=None):
        super().__init__(parent)
        self.monto_financiar = monto_financiar
        self.setWindowTitle("Intercepción Posnet")
        self.resize(350, 200)
        self.setup_ui()

    def setup_ui(self):
        from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton, QLabel, QMessageBox

        layout = QVBoxLayout(self)

        lbl_instruccion = QLabel(f"1. Pase la tarjeta por el terminal físico por el monto exacto de:\n\n$ {self.monto_financiar:.2f}")
        lbl_instruccion.setStyleSheet("font-size: 16px; font-weight: bold; color: #d35400; margin-bottom: 10px;")
        lbl_instruccion.setWordWrap(True)
        layout.addWidget(lbl_instruccion)

        lbl_instruccion2 = QLabel("2. Una vez aprobado, ingrese los datos del comprobante impreso:")
        layout.addWidget(lbl_instruccion2)

        form = QFormLayout()
        self.txt_lote = QLineEdit()
        self.txt_lote.setPlaceholderText("Ej: 123")
        self.txt_cupon = QLineEdit()
        self.txt_cupon.setPlaceholderText("Ej: 4567")

        form.addRow("Nº Lote:", self.txt_lote)
        form.addRow("Nº Cupón:", self.txt_cupon)
        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_confirmar = QPushButton("Confirmar Cobro Aprobado")
        btn_confirmar.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px;")
        btn_confirmar.clicked.connect(self._validar)

        btn_cancelar = QPushButton("Tarjeta Rechazada / Cancelar")
        btn_cancelar.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; padding: 8px;")
        btn_cancelar.clicked.connect(self.reject)

        btn_box.addWidget(btn_confirmar)
        btn_box.addWidget(btn_cancelar)
        layout.addLayout(btn_box)

    def _validar(self):
        from PyQt6.QtWidgets import QMessageBox
        if not self.txt_lote.text().strip() or not self.txt_cupon.text().strip():
            QMessageBox.warning(self, "Datos Incompletos", "Debe ingresar el Lote y el Cupón del Posnet para continuar.")
            return
        self.accept()

    def get_datos(self):
        return {
            "lote": self.txt_lote.text().strip(),
            "cupon": self.txt_cupon.text().strip()
        }
