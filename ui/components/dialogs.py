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
from PyQt6.QtGui import QPainter, QFont, QPageSize, QPixmap, QFontMetrics, QPageLayout
from PyQt6.QtCore import QSizeF, QSettings, Qt, QRectF, QTimer, QMarginsF
import os
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

        self.printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        self.preview = QPrintPreviewWidget(self.printer)
        self.preview.paintRequested.connect(self.paint_preview)

        main_layout.addWidget(self.preview)

        QTimer.singleShot(100, self.preview.updatePreview)

    def open_config(self):
        # Assumes ConfiguracionTicketDialog exists (e.g. imported from codigos_barra)
        try:
            from src.lubricentro.productos.codigos_barra import ConfiguracionTicketDialog
            dlg = ConfiguracionTicketDialog(self)
            if dlg.exec():
                self.preview.updatePreview()
        except ImportError:
            QMessageBox.warning(self, "Error", "Módulo de configuración no encontrado.")

    def paint_preview(self, printer):
        from PyQt6.QtGui import QPainter, QFont, QFontMetricsF, QImage, QPen
        from PyQt6.QtCore import QSizeF, QRectF, Qt
        from PyQt6.QtPrintSupport import QPrinter
        import os

        w_mm = float(self.settings.value("width", 58.0))
        margin_x_mm = float(self.settings.value("margin_x", 2.0))
        margin_y_mm = float(self.settings.value("margin_y", 2.0))
        fs_pt = int(self.settings.value("font_size", 8))
        fs_title = int(fs_pt * 1.5)
        logo_path = self.settings.value("logo_path", "")
        logo_width_px = int(self.settings.value("logo_width", 150))
        address = self.settings.value("address", "")
        phone = self.settings.value("phone", "")
        leyenda = self.venta.tipo_comprobante if self.venta.tipo_comprobante else "Remito"

        cliente_nombre = getattr(self, 'cliente_nombre', "Consumidor Final")
        if not cliente_nombre: cliente_nombre = "Consumidor Final"

        w_inner_mm = w_mm - (margin_x_mm * 2)

        dpi = 96.0
        ppm = dpi / 25.4

        inner_width_px = w_inner_mm * ppm

        font_normal = QFont("Arial")
        font_normal.setPixelSize(int(fs_pt * (96.0 / 72.0)))

        font_bold = QFont("Arial")
        font_bold.setPixelSize(int(fs_pt * (96.0 / 72.0)))
        font_bold.setBold(True)

        font_title = QFont("Arial")
        font_title.setPixelSize(int(fs_title * (96.0 / 72.0)))
        font_title.setBold(True)

        font_small = QFont("Arial")
        font_small.setPixelSize(int(fs_pt * 0.8 * (96.0 / 72.0)))

        temp_img = QImage(int(inner_width_px), 1000, QImage.Format.Format_RGB32)
        p_measure = QPainter(temp_img)

        y_cursor_px = 0.0

        if logo_path and os.path.exists(logo_path):
            img = QImage(logo_path)
            if not img.isNull():
                scaled_h = int(img.height() * (logo_width_px / img.width()))
                y_cursor_px += scaled_h + (5 * ppm)

        p_measure.setFont(font_title)
        fm_t = p_measure.fontMetrics()
        y_cursor_px += fm_t.height() + (5 * ppm)

        p_measure.setFont(font_bold)
        fm_b = p_measure.fontMetrics()
        y_cursor_px += fm_b.height() + (5 * ppm)

        p_measure.setFont(font_normal)
        fm_n = p_measure.fontMetrics()
        line_height = fm_n.height()

        y_cursor_px += line_height * 4 + (10 * ppm)

        for item in self.detalles_final:
            nombre = item.get('nombre', '')
            texto_izq = f"{item['cantidad']}x {nombre}"
            rect_item = p_measure.boundingRect(QRectF(0, 0, inner_width_px * 0.7, 1000), Qt.TextFlag.TextWordWrap, texto_izq)
            y_cursor_px += rect_item.height() + (2 * ppm)

        y_cursor_px += line_height + (5 * ppm)

        p_measure.setFont(font_title)
        y_cursor_px += p_measure.fontMetrics().height() + (10 * ppm)

        p_measure.setFont(font_small)
        y_cursor_px += p_measure.fontMetrics().height() * 2 + (10 * ppm)

        if address or phone:
            p_measure.setFont(font_normal)
            if address: y_cursor_px += line_height
            if phone: y_cursor_px += line_height
            y_cursor_px += (5 * ppm)

        p_measure.setFont(font_normal)
        y_cursor_px += line_height + (5 * ppm)

        p_measure.end()

        alto_total_mm = y_cursor_px / ppm
        alto_total_mm += 10.0 + margin_y_mm * 2

        from PyQt6.QtGui import QPageSize, QPageLayout
        from PyQt6.QtCore import QMarginsF
        size = QPageSize(QSizeF(w_mm, alto_total_mm), QPageSize.Unit.Millimeter, "", QPageSize.SizeMatchPolicy.ExactMatch)
        printer.setPageSize(size)
        printer.setPageMargins(QMarginsF(0.0, 0.0, 0.0, 0.0), QPageLayout.Unit.Millimeter)
        printer.setFullPage(True)

        painter = QPainter()
        if painter.begin(printer):
            painter.setPen(QPen(Qt.GlobalColor.black))

            actual_dpi = printer.resolution()
            painter.setWindow(0, 0, int(w_mm * (96.0 / 25.4)), int(alto_total_mm * (96.0 / 25.4)))
            painter.setViewport(0, 0, int(w_mm * (actual_dpi / 25.4)), int(alto_total_mm * (actual_dpi / 25.4)))

            start_x = margin_x_mm * ppm
            start_y = margin_y_mm * ppm
            y = start_y

            def draw_text_center(text, font, advance_padding_mm=2):
                nonlocal y
                painter.setFont(font)
                fm = painter.fontMetrics()
                painter.drawText(QRectF(start_x, y, inner_width_px, fm.height()), Qt.AlignmentFlag.AlignCenter, text)
                y += fm.height() + (advance_padding_mm * ppm)

            def draw_text_left(text, font, advance_padding_mm=2):
                nonlocal y
                painter.setFont(font)
                fm = painter.fontMetrics()
                painter.drawText(QRectF(start_x, y, inner_width_px, fm.height()), Qt.AlignmentFlag.AlignLeft, text)
                y += fm.height() + (advance_padding_mm * ppm)

            def draw_line(advance_padding_mm=4):
                nonlocal y
                y += (advance_padding_mm * ppm) / 2
                painter.drawLine(int(start_x), int(y), int(start_x + inner_width_px), int(y))
                y += (advance_padding_mm * ppm) / 2

            if logo_path and os.path.exists(logo_path):
                img = QImage(logo_path)
                if not img.isNull():
                    scaled_h = int(img.height() * (logo_width_px / img.width()))
                    x_img = start_x + (inner_width_px - logo_width_px) / 2
                    painter.drawImage(QRectF(x_img, y, logo_width_px, scaled_h), img)
                    y += scaled_h + (5 * ppm)

            draw_text_center(f"[X] {leyenda}", font_title, 2)
            draw_text_center(f"Cliente: {cliente_nombre}", font_bold, 2)
            draw_line(4)
            draw_text_left(f"Venta ID: {self.venta.id}", font_normal, 0)
            draw_text_left(f"Fecha: {self.venta.fecha.strftime('%d/%m/%Y %H:%M')}", font_normal, 2)
            draw_line(4)

            painter.setFont(font_normal)
            for item in self.detalles_final:
                nombre = item.get('nombre', '')
                texto_izq = f"{item['cantidad']}x {nombre}"
                texto_der = f"${item['subtotal']:.2f}"

                fm = painter.fontMetrics()
                rect_der = QRectF(start_x + (inner_width_px * 0.7), y, inner_width_px * 0.3, fm.height())
                painter.drawText(rect_der, Qt.AlignmentFlag.AlignRight, texto_der)

                rect_izq_bound = QRectF(start_x, y, inner_width_px * 0.65, 1000)
                bounding = painter.boundingRect(rect_izq_bound, Qt.TextFlag.TextWordWrap, texto_izq)
                painter.drawText(rect_izq_bound, Qt.TextFlag.TextWordWrap, texto_izq)

                y += bounding.height() + (2 * ppm)

            draw_line(4)

            painter.setFont(font_title)
            fm = painter.fontMetrics()
            painter.drawText(QRectF(start_x, y, inner_width_px, fm.height()), Qt.AlignmentFlag.AlignRight, f"TOTAL: ${self.venta.total:.2f}")
            y += fm.height() + (10 * ppm)

            draw_text_center("ESTE COMPROBANTE NO ES VÁLIDO COMO FACTURA", font_small, 5)

            if address or phone:
                if address: draw_text_center(address, font_normal, 1)
                if phone: draw_text_center(phone, font_normal, 1)
                y += (5 * ppm)

            draw_text_center("¡Lo esperamos nuevamente!", font_normal, 2)

            painter.end()

    def imprimir(self):
        from PyQt6.QtPrintSupport import QPrinter
        from PyQt6.QtWidgets import QMessageBox
        print_job = QPrinter(QPrinter.PrinterMode.HighResolution)
        print_job.setOutputFormat(QPrinter.OutputFormat.NativeFormat)
        printer_name = self.settings.value("printer_name", "")
        if printer_name:
            print_job.setPrinterName(printer_name)

        self.paint_preview(print_job)
        QMessageBox.information(self, "Impresión", "Ticket enviado a la impresora.")
        self.accept()
