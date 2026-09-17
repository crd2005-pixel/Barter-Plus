from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QCheckBox, QPushButton, QMessageBox, QHBoxLayout, QLabel, QDoubleSpinBox
)
from services.cliente_service import ClienteService

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
from PyQt6.QtGui import QPainter, QFont, QPageSize, QPixmap, QFontMetrics, QPageLayout, QPen, QColor
from PyQt6.QtCore import QSizeF, QSettings, Qt, QRectF, QTimer, QMarginsF
import os
class TicketConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración Predeterminada de Ticket")
        self.resize(400, 300)
        self.settings = QSettings("BarterPlus", "TicketConfig")

        layout = QFormLayout(self)

        self.cmb_printer = QComboBox()
        from PyQt6.QtPrintSupport import QPrinterInfo
        self.cmb_printer.addItems([p.printerName() for p in QPrinterInfo.availablePrinters()])

        self.sp_width = QDoubleSpinBox()
        self.sp_width.setRange(20, 200)
        self.sp_width.setSuffix(" mm")

        self.sp_height = QDoubleSpinBox()
        self.sp_height.setRange(20, 500)
        self.sp_height.setSuffix(" mm")
        self.sp_height.setToolTip("Largo de Papel (min: 130mm)")


        self.sp_margin_x = QDoubleSpinBox()
        self.sp_margin_x.setRange(0, 50)
        self.sp_margin_x.setSuffix(" mm")

        self.sp_margin_y = QDoubleSpinBox()
        self.sp_margin_y.setRange(0, 50)
        self.sp_margin_y.setSuffix(" mm")

        self.sp_spacing = QDoubleSpinBox()
        self.sp_spacing.setRange(0, 20)
        self.sp_spacing.setSuffix(" mm")
        self.sp_spacing.setToolTip("Espaciado entre lineas")

        self.sp_font_size = QSpinBox()
        self.sp_font_size.setRange(5, 30)

        self.txt_logo = QLineEdit()
        self.btn_logo = QPushButton("...")
        self.btn_logo.clicked.connect(self.browse_logo)
        lay_logo = QHBoxLayout()
        lay_logo.addWidget(self.txt_logo)
        lay_logo.addWidget(self.btn_logo)

        self.txt_address = QLineEdit()
        self.txt_phone = QLineEdit()

        layout.addRow("Impresora:", self.cmb_printer)

        layout.addRow("Ancho Papel:", self.sp_width)
        layout.addRow("Largo Papel:", self.sp_height)

        layout.addRow("Margen X:", self.sp_margin_x)
        layout.addRow("Margen Y:", self.sp_margin_y)
        layout.addRow("Interlineado:", self.sp_spacing)
        layout.addRow("Tamaño Fuente:", self.sp_font_size)
        layout.addRow("Logo:", lay_logo)
        layout.addRow("Dirección:", self.txt_address)
        layout.addRow("Teléfono:", self.txt_phone)

        self.btn_save = QPushButton("Guardar Configuración")
        self.btn_save.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; height: 35px;")
        self.btn_save.clicked.connect(self.save_and_close)
        layout.addRow(self.btn_save)

        self.load_settings()

    def browse_logo(self):
        import os
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar Logo", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.txt_logo.setText(path)

    def load_settings(self):
        printer_name = self.settings.value("printer_name", "")
        idx = self.cmb_printer.findText(printer_name)
        if idx >= 0: self.cmb_printer.setCurrentIndex(idx)

        # Forzamos 2.0 si no existe para arreglar el 10.0 heredado
        val_x = self.settings.value("margin_x", 2.0)
        val_y = self.settings.value("margin_y", 2.0)


        self.sp_width.setValue(float(self.settings.value("width", 78.0)))
        self.sp_height.setValue(float(self.settings.value("height_mm", 130.0)))

        self.sp_margin_x.setValue(float(val_x))
        self.sp_margin_y.setValue(float(val_y))
        self.sp_spacing.setValue(float(self.settings.value("spacing", 1.0)))
        self.sp_font_size.setValue(int(self.settings.value("font_size", 8)))
        self.txt_logo.setText(self.settings.value("logo_path", ""))
        self.txt_address.setText(self.settings.value("address", ""))
        self.txt_phone.setText(self.settings.value("phone", ""))

    def save_and_close(self):
        self.settings.setValue("printer_name", self.cmb_printer.currentText())

        self.settings.setValue("width", self.sp_width.value())
        self.settings.setValue("height_mm", self.sp_height.value())

        self.settings.setValue("margin_x", self.sp_margin_x.value())
        self.settings.setValue("margin_y", self.sp_margin_y.value())
        self.settings.setValue("spacing", self.sp_spacing.value())
        self.settings.setValue("font_size", self.sp_font_size.value())
        self.settings.setValue("logo_path", self.txt_logo.text())
        self.settings.setValue("address", self.txt_address.text())
        self.settings.setValue("phone", self.txt_phone.text())
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Guardado", "Parámetros actualizados.")
        self.accept()

class TicketPreviewDialog(QDialog):
    def __init__(self, venta, detalles_final, parent=None):
        super().__init__(parent)
        self.venta = venta
        self.detalles_final = detalles_final
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

        self.printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        self.preview = QPrintPreviewWidget(self.printer)
        self.preview.paintRequested.connect(self.paint_preview)

        main_layout.addWidget(self.preview)

        QTimer.singleShot(100, self.preview.updatePreview)

    def open_config(self):
        dlg = TicketConfigDialog(self)
        if dlg.exec():
            self.preview.updatePreview()

    def _generate_html(self):
        w_mm = float(self.settings.value("width", 78.0))
        # Para HTML en mm, usualmente es mejor usar el width 100% y manejar el tamano via printer

        fs = int(self.settings.value("font_size", 10))

        fs_title = int(fs * 1.5)

        # Scale font sizes for HighResolution DPI
        # A standard point is 1/72 of an inch. We will use the font size as a logical unit
        # and scale it based on printer's likely DPI ratio relative to standard screen (96).
        # We'll just define the style directly using standard pt. In QPrinter Native Format, it should theoretically scale.
        # However, due to HighResolution bug, sometimes we need an explicit larger size if it's too small.
        # We will use pt, but if it looks tiny on the user's screen, we might need a large multiplier.
        # But wait! If we do `doc.setDefaultFont()` we can pass a QFont with a point size that is aware of the device!
        # Let's just fix the `doc.setTextWidth()` first and use `font-size: {fs}pt;`.

        address = self.settings.value("address", "")

        phone = self.settings.value("phone", "")
        leyenda = self.venta.tipo_comprobante if self.venta.tipo_comprobante else "Remito"
        logo_path = self.settings.value("logo_path", "")


        spacing = float(self.settings.value("spacing", 1.5))


        html = f"""
        <html>
        <head>
        <style>
            body {{
                font-family: 'Arial', sans-serif;
                font-size: {fs}pt;
                color: black;
                margin: 0;
                padding: 0;
                line-height: {spacing};
            }}
            .center {{ text-align: center; }}
            .right {{ text-align: right; }}
            .left {{ text-align: left; }}
            .bold {{ font-weight: bold; }}
            .title {{ font-size: {fs_title}pt; font-weight: bold; margin-bottom: 5px; }}
            .line {{ border-bottom: 1px solid black; margin: 10px 0; }}
            table {{ width: 100%; border-collapse: collapse; }}
            td {{ vertical-align: top; padding: 4px 0; }}
            .logo {{ max-height: 100px; max-width: 80%; display: block; margin: 0 auto 10px auto; }}
        </style>
        </head>
        <body>
        """


        if logo_path:
            # HTML doesn't reliably load local absolute paths in QTextDocument without specific resource loading,
            # but we can try file:///
            import os
            if os.path.exists(logo_path):
                # Format to file URI
                uri = "file:///" + logo_path.replace("\\", "/")
                html += f'<div class="center"><img src="{uri}" width="150"></div>'

        html += f"""
        <div class="center">
            <div class="title">[X] {leyenda}</div>
        """

        if address:
            html += f"<div>{address}</div>"
        if phone:
            html += f"<div>{phone}</div>"

        html += f"""
        </div>
        <div class="line"></div>
        <div class="left">Venta ID: {self.venta.id}</div>
        <div class="left">Fecha: {self.venta.fecha.strftime('%d/%m/%Y %H:%M')}</div>
        <div class="line"></div>
        <table>
        """

        for item in self.detalles_final:
            nombre_prod = item.get('nombre', '')
            html += f"""
            <tr>
                <td class="left" style="width: 70%;">{item['cantidad']}x {nombre_prod}</td>
                <td class="right" style="width: 30%;">${item['subtotal']:.2f}</td>
            </tr>
            """

        html += f"""
        </table>
        <div class="line"></div>
        <div class="right title">TOTAL: ${self.venta.total:.2f}</div>
        """

        if self.venta.metodo_pago == "Efectivo":
            html += f"""
            <div class="right">Abonado: ${self.venta.pago_efectivo:.2f}</div>
            <div class="right">Vuelto: ${self.venta.vuelto:.2f}</div>
            """

        html += f"""
        <br><br>
        <div class="center">¡Gracias por su compra!</div>
        <br><br><br>
        </body>
        </html>
        """
        return html

    def paint_preview(self, printer):
        from PyQt6.QtGui import QTextDocument
        from PyQt6.QtCore import QSizeF

        # Load user settings
        w_mm = float(self.settings.value("width", 78.0))
        margin_x_mm = float(self.settings.value("margin_x", 2.0))
        margin_y_mm = float(self.settings.value("margin_y", 2.0))
        min_h_mm = float(self.settings.value("height_mm", 130.0))

        # We start with the minimum size to give the printer an initial canvas
        initial_size = QPageSize(QSizeF(w_mm, min_h_mm), QPageSize.Unit.Millimeter, "", QPageSize.SizeMatchPolicy.ExactMatch)
        printer.setPageSize(initial_size)
        printer.setFullPage(True)
        printer.setPageMargins(QMarginsF(margin_x_mm, margin_y_mm, margin_x_mm, margin_y_mm), QPageLayout.Unit.Millimeter)

        doc = QTextDocument()
        doc.setHtml(self._generate_html())

        # IMPORTANT: Instead of manually calculating pixels and DPI which is error-prone,
        # simply tell QTextDocument to use the printer's page layout width.
        # By setting the exact printable width (pageRect width minus margins natively calculated by Qt),
        # QTextDocument will wrap the text perfectly according to the physical paper size.
        printable_rect = printer.pageLayout().paintRectPixels(printer.resolution())
        doc.setTextWidth(printable_rect.width())

        # Now query the exact height needed by the document to render all text without cutting it
        doc_height_pixels = doc.size().height()

        # Convert the pixel height back to physical millimeters based on the printer's resolution
        dynamic_h_mm = (doc_height_pixels / printer.resolution()) * 25.4

        # Add a comfortable cutting margin at the bottom (e.g. 20mm)
        dynamic_h_mm += 20.0

        # Final height ensures the paper is at least min_h_mm long
        h_mm = max(dynamic_h_mm, min_h_mm)

        # Finally, update the printer page size to match the true height
        final_size = QPageSize(QSizeF(w_mm, h_mm), QPageSize.Unit.Millimeter, "", QPageSize.SizeMatchPolicy.ExactMatch)
        printer.setPageSize(final_size)

        # Print directly
        doc.print(printer)




    def imprimir(self):
        from PyQt6.QtWidgets import QMessageBox
        print_job = QPrinter(QPrinter.PrinterMode.HighResolution)
        print_job.setOutputFormat(QPrinter.OutputFormat.NativeFormat)
        printer_name = self.settings.value("printer_name", "")
        if printer_name:
            print_job.setPrinterName(printer_name)

        self.paint_preview(print_job)
        QMessageBox.information(self, "Impresión", "Ticket enviado a la impresora.")
        self.accept()
