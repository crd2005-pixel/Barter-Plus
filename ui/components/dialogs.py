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

        self.sp_logo_width = QSpinBox()
        self.sp_logo_width.setRange(10, 500)
        self.sp_logo_width.setSuffix(" px")
        self.sp_logo_width.setToolTip("Ancho del Logo en pixeles")

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
        layout.addRow("Ancho Logo:", self.sp_logo_width)
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
        self.sp_logo_width.setValue(int(self.settings.value("logo_width", 150)))
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
        self.settings.setValue("logo_width", self.sp_logo_width.value())
        self.settings.setValue("logo_path", self.txt_logo.text())
        self.settings.setValue("address", self.txt_address.text())
        self.settings.setValue("phone", self.txt_phone.text())
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Guardado", "Parámetros actualizados.")
        self.accept()

class TicketPreviewDialog(QDialog):
    def __init__(self, venta, detalles_final, cliente_nombre, parent=None):
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
        dlg = TicketConfigDialog(self)
        if dlg.exec():
            self.preview.updatePreview()


    def paint_preview(self, printer):
        from PyQt6.QtGui import QPainter, QFont, QFontMetricsF, QImage
        from PyQt6.QtCore import QSizeF, QRectF, Qt
        from PyQt6.QtPrintSupport import QPrinter
        import datetime
        import os

        # 1. Cargar Configuración Base
        w_mm = float(self.settings.value("width", 78.0))
        margin_x_mm = float(self.settings.value("margin_x", 2.0))
        margin_y_mm = float(self.settings.value("margin_y", 2.0))
        fs_pt = int(self.settings.value("font_size", 10))
        fs_title = int(fs_pt * 1.5)
        logo_path = self.settings.value("logo_path", "")
        logo_width_px = int(self.settings.value("logo_width", 150))
        address = self.settings.value("address", "")
        phone = self.settings.value("phone", "")
        leyenda = self.venta.tipo_comprobante if self.venta.tipo_comprobante else "Remito"

        # Use client name captured directly from the POS interface, overriding the default.
        cliente_nombre = self.cliente_nombre if hasattr(self, 'cliente_nombre') else "Consumidor Final"

        # 2. Configurar Fuentes y Métricas
        # The physical width inside margins
        w_inner_mm = w_mm - (margin_x_mm * 2)

        # Calculate pixels per mm based on logical DPI (standardizing drawing resolution)
        dpi = 96.0
        ppm = dpi / 25.4

        inner_width_px = w_inner_mm * ppm

        font_normal = QFont("Arial", fs_pt)
        font_bold = QFont("Arial", fs_pt)
        font_bold.setBold(True)
        font_title = QFont("Arial", fs_title)
        font_title.setBold(True)
        font_small = QFont("Arial", int(fs_pt * 0.8))

        # 3. Pre-cálculo de Altura (Acumulador Y)
        # Usamos un QImage temporal para tener un contexto de dibujo y medir las fuentes
        temp_img = QImage(int(inner_width_px), 1000, QImage.Format.Format_RGB32)
        p_measure = QPainter(temp_img)

        fm_normal = p_measure.fontMetrics()

        y_cursor_px = 0.0

        # Measure Logo
        if logo_path and os.path.exists(logo_path):
            img = QImage(logo_path)
            if not img.isNull():
                scaled_h = int(img.height() * (logo_width_px / img.width()))
                y_cursor_px += scaled_h + (5 * ppm)

        # Measure Title
        p_measure.setFont(font_title)
        fm_t = p_measure.fontMetrics()
        y_cursor_px += fm_t.height() + (5 * ppm)

        # Measure Cliente
        p_measure.setFont(font_bold)
        fm_b = p_measure.fontMetrics()
        y_cursor_px += fm_b.height() + (5 * ppm)

        # Measure separator + ID + Fecha + separator
        p_measure.setFont(font_normal)
        fm_n = p_measure.fontMetrics()
        line_height = fm_n.height()

        y_cursor_px += line_height * 4 + (10 * ppm)

        # Measure Items
        for item in self.detalles_final:
            nombre = item.get('nombre', '')
            texto_izq = f"{item['cantidad']}x {nombre}"
            rect_item = p_measure.boundingRect(QRectF(0, 0, inner_width_px * 0.7, 1000), Qt.TextFlag.TextWordWrap, texto_izq)
            y_cursor_px += rect_item.height() + (2 * ppm)

        y_cursor_px += line_height + (5 * ppm) # separator

        # Measure Total
        p_measure.setFont(font_title)
        y_cursor_px += p_measure.fontMetrics().height() + (10 * ppm)

        # Measure Disclaimers and Address
        p_measure.setFont(font_small)
        y_cursor_px += p_measure.fontMetrics().height() * 2 + (10 * ppm)

        if address or phone:
            p_measure.setFont(font_normal)
            if address: y_cursor_px += line_height
            if phone: y_cursor_px += line_height
            y_cursor_px += (5 * ppm)

        # Final Thank You
        p_measure.setFont(font_normal)
        y_cursor_px += line_height + (5 * ppm)

        p_measure.end()

        # Convert calculated pixel height to mm
        alto_total_mm = y_cursor_px / ppm

        # 4. Margen de Corte
        alto_total_mm += 10.0 + margin_y_mm * 2

        # 5. Inyección Dinámica al Spooler
        from PyQt6.QtGui import QPageSize, QPageLayout
        from PyQt6.QtCore import QMarginsF
        size = QPageSize(QSizeF(w_mm, alto_total_mm), QPageSize.Unit.Millimeter, "", QPageSize.SizeMatchPolicy.ExactMatch)
        printer.setPageSize(size)
        # Forzamos los margenes de la libreria vieja a 0 nativos usando PyQt6
        printer.setPageMargins(QMarginsF(0.0, 0.0, 0.0, 0.0), QPageLayout.Unit.Millimeter)
        printer.setFullPage(True)

        # Ahora sí, iniciar el painter real
        painter = QPainter()
        if painter.begin(printer):
            # Scale coordinates so we can draw in our logical DPI dimensions regardless of actual printer resolution
            actual_dpi = printer.resolution()
            scale_factor = actual_dpi / dpi
            painter.scale(scale_factor, scale_factor)

            # Trasladar según margen X, Y
            start_x = margin_x_mm * ppm
            start_y = margin_y_mm * ppm
            y = start_y

            # Función auxiliar para dibujar texto y avanzar Y
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

            # --- DIBUJAR CONTENIDO ---

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

            # Ítems
            painter.setFont(font_normal)
            for item in self.detalles_final:
                nombre = item.get('nombre', '')
                texto_izq = f"{item['cantidad']}x {nombre}"
                texto_der = f"${item['subtotal']:.2f}"

                # Draw right text first
                fm = painter.fontMetrics()
                rect_der = QRectF(start_x + (inner_width_px * 0.7), y, inner_width_px * 0.3, fm.height())
                painter.drawText(rect_der, Qt.AlignmentFlag.AlignRight, texto_der)

                # Draw left text wrapped
                rect_izq_bound = QRectF(start_x, y, inner_width_px * 0.65, 1000)
                bounding = painter.boundingRect(rect_izq_bound, Qt.TextFlag.TextWordWrap, texto_izq)
                painter.drawText(rect_izq_bound, Qt.TextFlag.TextWordWrap, texto_izq)

                y += bounding.height() + (2 * ppm)

            draw_line(4)

            # Total
            painter.setFont(font_title)
            fm = painter.fontMetrics()
            painter.drawText(QRectF(start_x, y, inner_width_px, fm.height()), Qt.AlignmentFlag.AlignRight, f"TOTAL: ${self.venta.total:.2f}")
            y += fm.height() + (10 * ppm)

            # Footer Disclaimers
            draw_text_center("ESTE COMPROBANTE NO ES VÁLIDO COMO FACTURA", font_small, 5)

            if address or phone:
                if address: draw_text_center(address, font_normal, 1)
                if phone: draw_text_center(phone, font_normal, 1)
                y += (5 * ppm)

            draw_text_center("¡Lo esperamos nuevamente!", font_normal, 2)

            painter.end()
            del painter

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
