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
from PyQt6.QtGui import QPainter, QFont, QPageSize, QPixmap, QFontMetrics
from PyQt6.QtCore import QSizeF, QSettings, Qt, QRectF, QTimer, QMarginsF
import os
class TicketPreviewDialog(QDialog):
    def __init__(self, venta, detalles_final, parent=None):
        super().__init__(parent)
        self.venta = venta
        self.detalles_final = detalles_final
        self.setWindowTitle("Impresión de Ticket")
        self.resize(800, 600)

        self.settings = QSettings("BarterPlus", "TicketConfig")

        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        left_widget = QWidget()
        left_lay = QVBoxLayout(left_widget)

        form = QFormLayout()

        self.cmb_printer = QComboBox()
        from PyQt6.QtPrintSupport import QPrinterInfo
        self.cmb_printer.addItems([p.printerName() for p in QPrinterInfo.availablePrinters()])

        self.sp_width = QDoubleSpinBox()
        self.sp_width.setRange(20, 200)
        self.sp_width.setSuffix(" mm")

        self.sp_margin_x = QDoubleSpinBox()
        self.sp_margin_x.setRange(0, 50)
        self.sp_margin_x.setSuffix(" mm")

        self.sp_margin_y = QDoubleSpinBox()
        self.sp_margin_y.setRange(0, 50)
        self.sp_margin_y.setSuffix(" mm")

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

        form.addRow("Impresora:", self.cmb_printer)
        form.addRow("Ancho:", self.sp_width)
        form.addRow("Margen X:", self.sp_margin_x)
        form.addRow("Margen Y:", self.sp_margin_y)
        form.addRow("Tamaño Fuente:", self.sp_font_size)
        form.addRow("Logo:", lay_logo)
        form.addRow("Dirección:", self.txt_address)
        form.addRow("Teléfono:", self.txt_phone)

        left_lay.addLayout(form)

        self.btn_imprimir = QPushButton("Imprimir Ticket")
        self.btn_imprimir.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; height: 40px;")
        self.btn_imprimir.clicked.connect(self.imprimir)
        left_lay.addStretch()
        left_lay.addWidget(self.btn_imprimir)

        self.printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        self.preview = QPrintPreviewWidget(self.printer)
        self.preview.paintRequested.connect(self.paint_preview)

        splitter.addWidget(left_widget)
        splitter.addWidget(self.preview)
        splitter.setStretchFactor(1, 2)

        self.load_settings()

        for w in [self.cmb_printer, self.sp_width, self.sp_margin_x, self.sp_margin_y, self.sp_font_size, self.txt_logo, self.txt_address, self.txt_phone]:
            if isinstance(w, QSpinBox) or isinstance(w, QDoubleSpinBox):
                w.valueChanged.connect(self.update_preview)
            elif isinstance(w, QComboBox):
                w.currentIndexChanged.connect(self.update_preview)
            elif isinstance(w, QLineEdit):
                w.textChanged.connect(self.update_preview)

        QTimer.singleShot(100, self.update_preview)

    def browse_logo(self):
        import os
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar Logo", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.txt_logo.setText(path)

    def load_settings(self):
        printer_name = self.settings.value("printer_name", "")
        idx = self.cmb_printer.findText(printer_name)
        if idx >= 0: self.cmb_printer.setCurrentIndex(idx)

        self.sp_width.setValue(float(self.settings.value("width", 58.0)))
        self.sp_margin_x.setValue(float(self.settings.value("margin_x", 2.0)))
        self.sp_margin_y.setValue(float(self.settings.value("margin_y", 5.0)))
        self.sp_font_size.setValue(int(self.settings.value("font_size", 8)))
        self.txt_logo.setText(self.settings.value("logo_path", ""))
        self.txt_address.setText(self.settings.value("address", ""))
        self.txt_phone.setText(self.settings.value("phone", ""))

    def save_settings(self):
        self.settings.setValue("printer_name", self.cmb_printer.currentText())
        self.settings.setValue("width", self.sp_width.value())
        self.settings.setValue("margin_x", self.sp_margin_x.value())
        self.settings.setValue("margin_y", self.sp_margin_y.value())
        self.settings.setValue("font_size", self.sp_font_size.value())
        self.settings.setValue("logo_path", self.txt_logo.text())
        self.settings.setValue("address", self.txt_address.text())
        self.settings.setValue("phone", self.txt_phone.text())

    def update_preview(self):
        self.save_settings()
        self.preview.updatePreview()

    def apply_printer_config(self, target_printer):
        import os
        dpi = target_printer.resolution()
        if dpi <= 0: dpi = 96
        ppm = dpi / 25.4

        w_mm = self.sp_width.value()

        font_title = QFont("Arial", int(self.sp_font_size.value() * 1.5))
        font_title.setBold(True)
        font_body = QFont("Arial", int(self.sp_font_size.value()))
        fm_t = QFontMetrics(font_title)
        fm_b = QFontMetrics(font_body)

        y = self.sp_margin_y.value() * ppm
        if self.txt_logo.text() and os.path.exists(self.txt_logo.text()):
            y += 30 * ppm
            y += 2 * ppm

        y += fm_t.height() + (2 * ppm)
        if self.txt_address.text(): y += fm_b.height()
        if self.txt_phone.text(): y += fm_b.height()
        y += 2 * ppm
        y += fm_b.height() * 2 + (2 * ppm)
        y += 2 * ppm
        for item in self.detalles_final:
            y += fm_b.height() * 2
        y += 4 * ppm
        y += fm_t.height()
        if self.venta.metodo_pago == "Efectivo":
            y += fm_b.height() * 2
        y += 5 * ppm
        y += fm_b.height()

        h_mm = (y / ppm) + 15 # buffer extra para evitar cortes prematuros

        size = QPageSize(QSizeF(w_mm, h_mm), QPageSize.Unit.Millimeter)
        target_printer.setPageSize(size)
        target_printer.setPageMargins(QMarginsF(0,0,0,0), QPageLayout.Unit.Millimeter)
        target_printer.setFullPage(True)

    def paint_preview(self, printer):
        self.apply_printer_config(printer)
        painter = QPainter(printer)
        if painter.isActive():
            self._draw(painter, printer)
        painter.end()
        del painter

    def _draw(self, painter, printer):
        import os
        dpi = printer.resolution()
        if dpi <= 0: dpi = 96
        ppm = dpi / 25.4

        w_px = self.sp_width.value() * ppm
        margin_x = self.sp_margin_x.value() * ppm

        eff_w = w_px - (margin_x * 2)
        start_x = margin_x
        y = self.sp_margin_y.value() * ppm

        fs = self.sp_font_size.value()
        font_title = QFont("Arial", int(fs * 1.5))
        font_title.setBold(True)
        font_body = QFont("Arial", fs)
        fm_t = QFontMetrics(font_title)
        fm_b = QFontMetrics(font_body)

        logo_path = self.txt_logo.text()
        if logo_path and os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                logo_h = 30 * ppm
                scaled = pixmap.scaledToHeight(int(logo_h), Qt.TransformationMode.SmoothTransformation)
                lx = start_x + (eff_w - scaled.width()) / 2
                painter.drawPixmap(int(lx), int(y), scaled)
                y += logo_h + (2 * ppm)

        painter.setFont(font_title)
        box_size = fm_t.height()
        box_x = start_x + (eff_w / 2) - (box_size / 2) - (15 * ppm)
        rect_box = QRectF(box_x, y, box_size, box_size)
        painter.drawRect(rect_box)
        painter.drawText(rect_box, Qt.AlignmentFlag.AlignCenter, "X")

        leyenda = self.venta.tipo_comprobante if self.venta.tipo_comprobante else "Remito"
        painter.drawText(QRectF(box_x + box_size + (2*ppm), y, eff_w, box_size), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, leyenda)

        y += box_size + (2 * ppm)

        painter.setFont(font_body)
        if self.txt_address.text():
            painter.drawText(QRectF(start_x, y, eff_w, fm_b.height()), Qt.AlignmentFlag.AlignHCenter, self.txt_address.text())
            y += fm_b.height()
        if self.txt_phone.text():
            painter.drawText(QRectF(start_x, y, eff_w, fm_b.height()), Qt.AlignmentFlag.AlignHCenter, self.txt_phone.text())
            y += fm_b.height()

        y += (2 * ppm)
        painter.drawLine(int(start_x), int(y), int(start_x + eff_w), int(y))
        y += (2 * ppm)

        painter.drawText(QRectF(start_x, y, eff_w, fm_b.height()), Qt.AlignmentFlag.AlignLeft, f"Venta ID: {self.venta.id}")
        y += fm_b.height()
        painter.drawText(QRectF(start_x, y, eff_w, fm_b.height()), Qt.AlignmentFlag.AlignLeft, f"Fecha: {self.venta.fecha.strftime('%d/%m/%Y %H:%M')}")
        y += fm_b.height() + (2 * ppm)

        painter.drawLine(int(start_x), int(y), int(start_x + eff_w), int(y))
        y += (2 * ppm)

        for item in self.detalles_final:
            painter.drawText(QRectF(start_x, y, eff_w, fm_b.height()), Qt.AlignmentFlag.AlignLeft, f"{item['cantidad']}x {item['nombre']}")
            y += fm_b.height()
            painter.drawText(QRectF(start_x, y, eff_w, fm_b.height()), Qt.AlignmentFlag.AlignRight, f"${item['subtotal']:.2f}")
            y += fm_b.height()

        y += (2 * ppm)
        painter.drawLine(int(start_x), int(y), int(start_x + eff_w), int(y))
        y += (2 * ppm)

        painter.setFont(font_title)
        painter.drawText(QRectF(start_x, y, eff_w, fm_t.height()), Qt.AlignmentFlag.AlignRight, f"TOTAL: ${self.venta.total:.2f}")
        y += fm_t.height()

        if self.venta.metodo_pago == "Efectivo":
            painter.setFont(font_body)
            painter.drawText(QRectF(start_x, y, eff_w, fm_b.height()), Qt.AlignmentFlag.AlignRight, f"Abonado: ${self.venta.pago_efectivo:.2f}")
            y += fm_b.height()
            painter.drawText(QRectF(start_x, y, eff_w, fm_b.height()), Qt.AlignmentFlag.AlignRight, f"Vuelto: ${self.venta.vuelto:.2f}")
            y += fm_b.height()

        y += (5 * ppm)
        painter.setFont(font_body)
        painter.drawText(QRectF(start_x, y, eff_w, fm_b.height()), Qt.AlignmentFlag.AlignHCenter, "¡Gracias por su compra!")

    def imprimir(self):
        print_job = QPrinter(QPrinter.PrinterMode.HighResolution)
        print_job.setOutputFormat(QPrinter.OutputFormat.NativeFormat)
        printer_name = self.cmb_printer.currentText()
        if printer_name:
            print_job.setPrinterName(printer_name)

        self.apply_printer_config(print_job)
        painter = QPainter(print_job)
        if painter.isActive():
            self._draw(painter, print_job)
        painter.end()
        del painter
        QMessageBox.information(self, "Impresión", "Ticket enviado a la impresora.")
        self.accept()
