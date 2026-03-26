# -*- coding: utf-8 -*-
import os
import datetime as dt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QHeaderView, QLabel, QCheckBox,
    QDialog, QFormLayout, QDoubleSpinBox, QComboBox, QFileDialog,
    QGroupBox, QSplitter, QFrame, QSpinBox, QAbstractItemView
)
from PyQt5.QtCore import Qt, QSettings, QSizeF, QRectF, QTimer
from PyQt5.QtGui import QColor, QPainter, QFont, QPen, QBrush, QPageLayout, QPageSize
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewWidget

from db import SessionLocal, Producto
try:
    from db.models.productos import Marca
except ImportError:
    Marca = None

from .barcode_utils import get_code128_pattern

# =============================================================================
# Custom Dialog: Configuration + Preview + Quantity Selection
# =============================================================================
class EtiquetasPreviewDialog(QDialog):
    def __init__(self, items, parent=None):
        """
        items: list of dicts with {id, marca, nombre, code, equivalencia, sku, cod_prov, precio}
        """
        super().__init__(parent)
        self.setWindowTitle("Configuración e Impresión de Etiquetas")
        self.resize(1100, 700)
        self.settings = QSettings("BarterPlus", "LabelConfig")

        # Internal state
        self.items = items # Original items
        # Augment items with 'cantidad'
        for it in self.items:
            it['cantidad'] = 1

        self.printer = QPrinter(QPrinter.HighResolution)

        # Main Layout
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # --- LEFT PANEL: Config & Items ---
        left_widget = QWidget()
        left_lay = QVBoxLayout(left_widget)
        left_lay.setContentsMargins(0,0,0,0)

        # 1. Configuration Controls (Scrollable if needed, but fixed is fine)
        config_group = QGroupBox("Configuración de Etiqueta")
        form = QFormLayout(config_group)

        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["A4 (Grilla)", "Rollo / Térmica (Individual)"])

        # Dimensions
        hb_dim = QHBoxLayout()
        self.sp_width = QDoubleSpinBox(); self.sp_width.setRange(10, 300); self.sp_width.setSuffix(" mm"); self.sp_width.setToolTip("Ancho")
        self.sp_height = QDoubleSpinBox(); self.sp_height.setRange(10, 300); self.sp_height.setSuffix(" mm"); self.sp_height.setToolTip("Alto")
        hb_dim.addWidget(QLabel("W:")); hb_dim.addWidget(self.sp_width)
        hb_dim.addWidget(QLabel("H:")); hb_dim.addWidget(self.sp_height)

        # Offsets
        hb_off = QHBoxLayout()
        self.sp_off_x = QDoubleSpinBox(); self.sp_off_x.setRange(-50, 50); self.sp_off_x.setSuffix(" mm"); self.sp_off_x.setToolTip("Desfase Horizontal (X)")
        self.sp_off_y = QDoubleSpinBox(); self.sp_off_y.setRange(-50, 50); self.sp_off_y.setSuffix(" mm"); self.sp_off_y.setToolTip("Desfase Vertical (Y)")
        hb_off.addWidget(QLabel("X:")); hb_off.addWidget(self.sp_off_x)
        hb_off.addWidget(QLabel("Y:")); hb_off.addWidget(self.sp_off_y)

        # Font Scale
        self.sp_font_scale = QDoubleSpinBox(); self.sp_font_scale.setRange(0.1, 5.0); self.sp_font_scale.setSingleStep(0.1)

        # Fields
        self.chk_marca = QCheckBox("Marca")
        self.chk_nombre = QCheckBox("Nombre")
        self.chk_codigo = QCheckBox("Código Barras")
        self.chk_equivalencia = QCheckBox("Equivalencia")
        self.chk_sku = QCheckBox("SKU")
        self.chk_precio = QCheckBox("Precio")

        # Layout Config
        form.addRow("Modo:", self.cmb_mode)
        form.addRow("Tamaño:", hb_dim)
        form.addRow("Desfase (Centro):", hb_off)
        form.addRow("Escala Fuente:", self.sp_font_scale)

        # Grid for checkboxes
        gl = QHBoxLayout() # flow
        gl.addWidget(self.chk_marca); gl.addWidget(self.chk_nombre)
        gl.addWidget(self.chk_codigo); gl.addWidget(self.chk_precio)
        form.addRow(gl)
        gl2 = QHBoxLayout()
        gl2.addWidget(self.chk_equivalencia); gl2.addWidget(self.chk_sku)
        form.addRow(gl2)

        left_lay.addWidget(config_group)

        # 2. Items Table (Qty)
        left_lay.addWidget(QLabel("<b>Items a Imprimir:</b>"))
        self.tbl_items = QTableWidget()
        self.tbl_items.setColumnCount(3)
        self.tbl_items.setHorizontalHeaderLabels(["Producto", "Cant.", ""])
        self.tbl_items.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tbl_items.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tbl_items.setSelectionBehavior(QAbstractItemView.SelectRows)
        left_lay.addWidget(self.tbl_items)

        # 3. Action Buttons
        btn_box = QVBoxLayout()
        hb_print = QHBoxLayout()
        self.btn_print_direct = QPushButton("Imprimir Directo (Por Defecto)")
        self.btn_print_direct.setStyleSheet("font-weight:bold; height: 40px; background-color: #c8e6c9;")
        self.btn_print_direct.clicked.connect(self._print_direct)

        self.btn_print_dialog = QPushButton("Seleccionar Impresora...")
        self.btn_print_dialog.setStyleSheet("height: 40px; background-color: #e0f7fa;")
        self.btn_print_dialog.clicked.connect(self._print_dialog)

        hb_print.addWidget(self.btn_print_direct)
        hb_print.addWidget(self.btn_print_dialog)
        btn_box.addLayout(hb_print)

        self.btn_pdf = QPushButton("Exportar PDF")
        self.btn_pdf.clicked.connect(self._export_pdf)
        btn_box.addWidget(self.btn_pdf)

        left_lay.addLayout(btn_box)

        # --- RIGHT PANEL: Preview ---
        self.preview = QPrintPreviewWidget(self.printer)
        self.preview.paintRequested.connect(self._paint_preview)

        splitter.addWidget(left_widget)
        splitter.addWidget(self.preview)
        splitter.setStretchFactor(1, 2) # Give preview more space

        # Load Settings
        self._load_settings()
        self._populate_table()

        # Connect signals
        for w in [self.cmb_mode, self.sp_width, self.sp_height, self.sp_font_scale,
                  self.sp_off_x, self.sp_off_y,
                  self.chk_marca, self.chk_nombre, self.chk_codigo,
                  self.chk_equivalencia, self.chk_sku, self.chk_precio]:
            if isinstance(w, QDoubleSpinBox) or isinstance(w, QSpinBox):
                w.valueChanged.connect(self._trigger_update)
            elif isinstance(w, QComboBox):
                w.currentIndexChanged.connect(self._trigger_update)
            elif isinstance(w, QCheckBox):
                w.toggled.connect(self._trigger_update)

        # Initial update
        QTimer.singleShot(100, self._trigger_update)

    def _load_settings(self):
        self.cmb_mode.setCurrentText(self.settings.value("mode", "A4 (Grilla)"))
        self.sp_width.setValue(float(self.settings.value("width", 50.0)))
        self.sp_height.setValue(float(self.settings.value("height", 30.0)))
        self.sp_off_x.setValue(float(self.settings.value("offset_x", 0.0)))
        self.sp_off_y.setValue(float(self.settings.value("offset_y", 0.0)))
        self.sp_font_scale.setValue(float(self.settings.value("font_scale", 1.0)))

        self.chk_marca.setChecked(self.settings.value("show_marca", True, type=bool))
        self.chk_nombre.setChecked(self.settings.value("show_nombre", True, type=bool))
        self.chk_codigo.setChecked(self.settings.value("show_codigo", True, type=bool))
        self.chk_equivalencia.setChecked(self.settings.value("show_equivalencia", False, type=bool))
        self.chk_sku.setChecked(self.settings.value("show_sku", False, type=bool))
        self.chk_precio.setChecked(self.settings.value("show_precio", False, type=bool))

    def _save_settings(self):
        self.settings.setValue("mode", self.cmb_mode.currentText())
        self.settings.setValue("width", self.sp_width.value())
        self.settings.setValue("height", self.sp_height.value())
        self.settings.setValue("offset_x", self.sp_off_x.value())
        self.settings.setValue("offset_y", self.sp_off_y.value())
        self.settings.setValue("font_scale", self.sp_font_scale.value())

        self.settings.setValue("show_marca", self.chk_marca.isChecked())
        self.settings.setValue("show_nombre", self.chk_nombre.isChecked())
        self.settings.setValue("show_codigo", self.chk_codigo.isChecked())
        self.settings.setValue("show_equivalencia", self.chk_equivalencia.isChecked())
        self.settings.setValue("show_sku", self.chk_sku.isChecked())
        self.settings.setValue("show_precio", self.chk_precio.isChecked())

    def _populate_table(self):
        self.tbl_items.setRowCount(len(self.items))
        for r, item in enumerate(self.items):
            # Name
            lbl = f"{item['nombre']}"
            if item['marca']: lbl = f"[{item['marca']}] {lbl}"
            self.tbl_items.setItem(r, 0, QTableWidgetItem(lbl))

            # Qty Spinbox
            sb = QSpinBox()
            sb.setRange(0, 999)
            sb.setValue(item['cantidad'])
            sb.valueChanged.connect(lambda val, idx=r: self._update_qty(idx, val))
            self.tbl_items.setCellWidget(r, 1, sb)

            # Remove btn
            btn_del = QPushButton("X")
            btn_del.setFixedWidth(24)
            btn_del.setStyleSheet("color:red; font-weight:bold;")
            btn_del.clicked.connect(lambda _, idx=r: self._remove_row(idx))
            self.tbl_items.setCellWidget(r, 2, btn_del)

    def _update_qty(self, row, val):
        if 0 <= row < len(self.items):
            self.items[row]['cantidad'] = val
            self._trigger_update()

    def _remove_row(self, row):
        if 0 <= row < len(self.items):
            self.items[row]['cantidad'] = 0 # Just mark 0 to skip printing
            self.tbl_items.hideRow(row) # Hide visually
            self._trigger_update()

    def _trigger_update(self):
        self.preview.updatePreview()

    def _apply_printer_config(self, printer):
        """Applies page size and margins to the given printer based on UI settings."""
        mode = self.cmb_mode.currentText()
        w_mm = self.sp_width.value()
        h_mm = self.sp_height.value()

        if mode.startswith("Rollo"):
            # Set custom page size for thermal printer
            size = QPageSize(QSizeF(w_mm, h_mm), QPageSize.Millimeter)
            printer.setPageSize(size)
            # Minimal margins
            # Using older signature for compatibility: setPageMargins(left, top, right, bottom, unit)
            printer.setPageMargins(0.0, 0.0, 0.0, 0.0, QPrinter.Millimeter)
            printer.setFullPage(True) # Force full page drawing for roll printers to avoid driver margins
        else:
            # A4
            printer.setPageSize(QPageSize(QPageSize.A4))
            printer.setFullPage(False)

    def _paint_preview(self, printer):
        # Applies to actual print or preview
        self._save_settings() # Save current UI state to settings so drawing logic can read it if needed, or pass explicitly

        self._apply_printer_config(printer)

        painter = QPainter()
        if painter.begin(printer):
            self._draw_labels(painter, printer)
            painter.end()

    def _draw_labels(self, painter, printer):
        # Generate flat list of items to print based on quantity
        print_queue = []
        for it in self.items:
            qty = it.get('cantidad', 1)
            for _ in range(qty):
                print_queue.append(it)

        if not print_queue:
            return

        mode = self.cmb_mode.currentText()

        # Coordinate system setup
        # We want to draw in Millimeters to be resolution independent?
        # QPainter doesn't support 'setUnit(Millimeter)' directly, but we can set Window/Viewport.
        # Alternatively, calculate pixels per mm.

        dpi = printer.resolution()
        if dpi <= 0: dpi = 96 # Fallback if invalid printer resolution

        # 1 inch = 25.4 mm
        # pixels_per_mm = dpi / 25.4
        ppm = dpi / 25.4

        # Settings
        w_mm = self.sp_width.value()
        h_mm = self.sp_height.value()
        off_x_mm = self.sp_off_x.value()
        off_y_mm = self.sp_off_y.value()

        w_px = w_mm * ppm
        h_px = h_mm * ppm
        off_x_px = off_x_mm * ppm
        off_y_px = off_y_mm * ppm

        if w_px <= 0: w_px = 100 # Prevent division by zero
        if h_px <= 0: h_px = 50

        # Font scaling factor
        # If we use setPixelSize, it depends on DPI.
        # If we use setPointSize, it depends on LogicalDPI which might differ.
        # Let's use coordinate scaling.

        painter.save()

        # Draw Logic
        if mode.startswith("Rollo"):
            # Use pageRect() origin to respect physical margins and apply user offsets
            page_rect = printer.pageRect(QPrinter.DevicePixel)
            start_x = page_rect.x() + off_x_px
            start_y = page_rect.y() + off_y_px
            rect = QRectF(start_x, start_y, w_px, h_px)

            for i, item in enumerate(print_queue):
                if i > 0:
                    printer.newPage()
                self._draw_single_label(painter, rect, item, ppm)
        else:
            # A4 Grid
            page_rect = printer.pageRect(QPrinter.DevicePixel)
            start_x = page_rect.x() + off_x_px
            start_y = page_rect.y() + off_y_px

            cols = int(page_rect.width() / w_px)
            rows = int(page_rect.height() / h_px)
            if cols < 1: cols = 1
            if rows < 1: rows = 1

            items_per_page = cols * rows

            for i, item in enumerate(print_queue):
                if i > 0 and i % items_per_page == 0:
                    printer.newPage()

                idx_on_page = i % items_per_page
                c = idx_on_page % cols
                r = idx_on_page // cols

                x = start_x + (c * w_px)
                y = start_y + (r * h_px)

                # Draw only if within page (using page bounds roughly)
                if (y + h_px) <= (page_rect.y() + page_rect.height() + max(0, off_y_px)):
                    rect = QRectF(x, y, w_px, h_px)
                    self._draw_single_label(painter, rect, item, ppm)

        painter.restore()

    def _draw_single_label(self, painter, rect, item, ppm):
        painter.save() # Isolate state for each label

        # Reset pen and brush before drawing text to ensure visibility
        painter.setPen(QPen(Qt.black))
        painter.setBrush(Qt.NoBrush)

        # Draw white background (helpful for some contexts)
        painter.fillRect(rect, Qt.white)

        # Padding (approx 1mm or 2mm)
        pad = 1.0 * ppm
        inner = rect.adjusted(pad, pad, -pad, -pad)

        if inner.width() <= 0 or inner.height() <= 0:
            painter.restore()
            return

        # Settings
        font_scale = self.sp_font_scale.value()

        # Font setup
        # Base font size: 8pt ~ 2.8mm
        # Adjusted by ppm and scale
        # 1 pt = 1/72 inch.
        # pixels = pts * (dpi/72)

        dpi = ppm * 25.4
        def get_font(pts, bold=False, family="Arial"):
            px_size = pts * (dpi / 72.0) * font_scale
            f = QFont(family)
            f.setPixelSize(int(px_size))
            f.setBold(bold)
            return f, int(px_size)

        y_cursor = inner.y()

        # 1. Marca
        if self.chk_marca.isChecked() and item.get('marca'):
            f, px = get_font(10, True)
            painter.setFont(f)
            fm = painter.fontMetrics()
            try:
                txt = str(item['marca']).upper()
            except:
                txt = ""
            rect_txt = QRectF(inner.x(), y_cursor, inner.width(), fm.height())
            painter.drawText(rect_txt, Qt.AlignHCenter | Qt.AlignTop, txt)
            y_cursor += fm.height()

        # 2. Nombre
        if self.chk_nombre.isChecked() and item.get('nombre'):
            # Multiline?
            f, px = get_font(9, False)
            painter.setFont(f)
            fm = painter.fontMetrics()

            # Max 2 lines
            line_h = fm.height()
            max_h = line_h * 2

            # We can use drawText with WordWrap to rect
            rect_txt = QRectF(inner.x(), y_cursor, inner.width(), max_h)

            # Measure actual height needed
            bounding = painter.boundingRect(rect_txt, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, item['nombre'])

            painter.drawText(rect_txt, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, item['nombre'])
            y_cursor += min(bounding.height(), max_h) + (1 * ppm) # small spacing

        # 3. Extras line (Code, SKU, Price)
        extras = []
        if self.chk_equivalencia.isChecked() and item['equivalencia']:
            extras.append(f"Eq:{item['equivalencia']}")
        if self.chk_sku.isChecked() and item['sku']:
            extras.append(f"SKU:{item['sku']}")
        if self.chk_precio.isChecked():
            extras.append(f"${item['precio']:.2f}")

        if extras:
            line = " ".join(extras)
            f, px = get_font(7, False)
            painter.setFont(f)
            fm = painter.fontMetrics()
            rect_txt = QRectF(inner.x(), y_cursor, inner.width(), fm.height())
            painter.drawText(rect_txt, Qt.AlignHCenter | Qt.AlignTop, line)
            y_cursor += fm.height() + (1 * ppm)

        # 4. Barcode
        if self.chk_codigo.isChecked() and item['code']:
            # Remaining height
            remaining = inner.bottom() - y_cursor

            # Text part of barcode
            f_code, px_code = get_font(8, False, "Courier New")
            painter.setFont(f_code)
            fm_code = painter.fontMetrics()
            h_text = fm_code.height()

            h_bars = remaining - h_text

            if h_bars > (2 * ppm): # Draw bars if at least 2mm space
                # Draw bars
                self._draw_bars(painter, inner.x(), y_cursor, inner.width(), h_bars, item['code'])
                y_cursor += h_bars

                # Reset pen and brush after drawing bars, so text is visible
                painter.setPen(QPen(Qt.black))
                painter.setBrush(Qt.NoBrush)

                # Draw Text
                rect_txt = QRectF(inner.x(), y_cursor, inner.width(), h_text)
                painter.drawText(rect_txt, Qt.AlignHCenter | Qt.AlignTop, item['code'])

        painter.restore()

    def _draw_bars(self, painter, x, y, w, h, code):
        pattern = get_code128_pattern(code)
        if not pattern: return

        total_units = sum(int(c) for c in pattern)
        if total_units == 0: return

        unit_w = w / total_units

        curr_x = x
        is_bar = True

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(Qt.black))

        for char in pattern:
            width_units = int(char)
            width_px = width_units * unit_w

            if is_bar:
                # To prevent anti-aliasing gaps, round to nearest pixel or overlap slightly?
                # Floating point rects usually fine in QPainter high-res.
                painter.drawRect(QRectF(curr_x, y, width_px, h))

            curr_x += width_px
            is_bar = not is_bar

    def _print_direct(self):
        # Use a fresh QPrinter instance so it's not locked by QPrintPreviewWidget
        print_job = QPrinter(QPrinter.HighResolution)
        print_job.setOutputFormat(QPrinter.NativeFormat)
        self._apply_printer_config(print_job)
        painter = QPainter()
        if painter.begin(print_job):
            self._draw_labels(painter, print_job)
            painter.end()
        # Not calling self.accept() so the dialog stays open
        QMessageBox.information(self, "Impresión", "Enviado a la impresora por defecto.")

    def _print_dialog(self):
        # Open standard print dialog to select printer
        # Use a fresh QPrinter instance so it's not locked by QPrintPreviewWidget
        print_job = QPrinter(QPrinter.HighResolution)
        print_job.setOutputFormat(QPrinter.NativeFormat)
        dlg = QPrintDialog(print_job, self)
        if dlg.exec_() == QPrintDialog.Accepted:
            # Re-apply config in case dialog changed something or reset it
            self._apply_printer_config(print_job)
            # Print
            painter = QPainter()
            if painter.begin(print_job):
                self._draw_labels(painter, print_job)
                painter.end()
            # Not calling self.accept() to allow multiple prints

    def _export_pdf(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Exportar PDF", "", "PDF Files (*.pdf)")
        if filename:
            if not filename.endswith(".pdf"): filename += ".pdf"

            self.printer.setOutputFormat(QPrinter.PdfFormat)
            self.printer.setOutputFileName(filename)

            painter = QPainter()
            if painter.begin(self.printer):
                self._draw_labels(painter, self.printer)
                painter.end()
            QMessageBox.information(self, "PDF", f"Guardado en {filename}")


# =============================================================================
# Main Tab
# =============================================================================

from PyQt5.QtCore import QMarginsF # Import needed

class CodigosBarraTab(QWidget):
    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Toolbar
        bar = QHBoxLayout()

        self.btn_refresh = QPushButton("Actualizar")
        self.btn_refresh.clicked.connect(self._load_data)
        bar.addWidget(self.btn_refresh)

        self.chk_solo_sin_codigo = QCheckBox("Ver solo sin código")
        self.chk_solo_sin_codigo.stateChanged.connect(self._load_data)
        bar.addWidget(self.chk_solo_sin_codigo)

        bar.addStretch()

        # Combined button as requested
        self.btn_imprimir = QPushButton("Imprimir / Vista Previa")
        self.btn_imprimir.setStyleSheet("font-weight: bold; color: blue; padding: 6px 12px;")
        self.btn_imprimir.clicked.connect(self._open_print_preview)
        bar.addWidget(self.btn_imprimir)

        # Removed individual config/export buttons

        self.btn_generar = QPushButton("Asignar Códigos Auto")
        self.btn_generar.clicked.connect(self._asignar_codigos_faltantes)
        bar.addWidget(self.btn_generar)

        layout.addLayout(bar)

        # Tabla
        self.tbl = QTableWidget()
        self.tbl.setColumnCount(5)
        self.tbl.setHorizontalHeaderLabels(["Sel.", "ID", "Marca", "Producto", "Código Barras"])
        self.tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tbl.setColumnWidth(0, 40)
        self.tbl.setColumnWidth(1, 60)
        self.tbl.setColumnWidth(2, 120)
        layout.addWidget(self.tbl)

    def refresh(self):
        self._load_data()

    def _load_data(self):
        self.tbl.setRowCount(0)
        solo_sin = self.chk_solo_sin_codigo.isChecked()

        with SessionLocal() as s:
            if Marca:
                q = s.query(Producto, Marca.nombre).outerjoin(Marca, Producto.marca_id == Marca.id).filter(Producto.activo == True)
            else:
                q = s.query(Producto).filter(Producto.activo == True)

            prods = q.all()

            rows = []
            for row in prods:
                if Marca:
                    try: p, m_nombre = row
                    except: p = row[0]; m_nombre = row[1]
                else:
                    p = row; m_nombre = ""

                cb = (p.codigo_barras or "").strip()
                if solo_sin and cb:
                    continue
                rows.append((p, m_nombre))

            self.tbl.setRowCount(len(rows))
            for r, (p, m_nombre) in enumerate(rows):
                ck = QTableWidgetItem()
                ck.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                ck.setCheckState(Qt.Checked if not p.codigo_barras else Qt.Unchecked)
                self.tbl.setItem(r, 0, ck)

                self.tbl.setItem(r, 1, QTableWidgetItem(str(p.id)))
                self.tbl.setItem(r, 2, QTableWidgetItem(m_nombre or ""))
                self.tbl.setItem(r, 3, QTableWidgetItem(p.nombre))

                cb_text = p.codigo_barras if p.codigo_barras else ""
                item_cb = QTableWidgetItem(cb_text)
                if not cb_text:
                    item_cb.setBackground(QColor("#fff9c4"))
                self.tbl.setItem(r, 4, item_cb)

                self.tbl.item(r, 1).setData(Qt.UserRole, p.id)

    def _asignar_codigos_faltantes(self):
        count = 0
        with SessionLocal() as s:
            prods = s.query(Producto).filter(Producto.activo == True).all()
            for p in prods:
                if not p.codigo_barras or not p.codigo_barras.strip():
                    nuevo_codigo = f"INT{p.id:06d}"
                    existing = s.query(Producto).filter(Producto.codigo_barras == nuevo_codigo).first()
                    if existing and existing.id != p.id:
                        base = f"INT{p.id:06d}_"
                        idx = 1
                        while True:
                            test_codigo = f"{base}{idx}"
                            if not s.query(Producto).filter(Producto.codigo_barras == test_codigo).first():
                                nuevo_codigo = test_codigo
                                break
                            idx += 1

                    p.codigo_barras = nuevo_codigo
                    count += 1
            if count > 0:
                s.commit()
                QMessageBox.information(self, "Generar", f"Se generaron {count} códigos nuevos.")
                self._load_data()
            else:
                QMessageBox.information(self, "Generar", "No había productos sin código.")
    def _get_selected_ids(self):
        ids = []
        for r in range(self.tbl.rowCount()):
            if self.tbl.item(r, 0).checkState() == Qt.Checked:
                pid = self.tbl.item(r, 1).data(Qt.UserRole)
                ids.append(pid)
        return ids

    def _open_print_preview(self):
        ids = self._get_selected_ids()
        if not ids:
            QMessageBox.warning(self, "Imprimir", "Seleccione al menos un producto.")
            return

        # Fetch data
        items = []
        with SessionLocal() as s:
            if Marca:
                q = s.query(Producto, Marca.nombre).outerjoin(Marca, Producto.marca_id == Marca.id).filter(Producto.id.in_(ids))
            else:
                q = s.query(Producto).filter(Producto.id.in_(ids))

            for row in q.all():
                if Marca:
                    try:
                        p, m_nombre = row
                    except:
                        # Fallback for unexpected row structure
                        try:
                            p = row[0]
                            m_nombre = row[1]
                        except:
                            # If all else fails, assume row is just Producto?
                            # Or skip to avoid crash
                            p = row
                            m_nombre = ""
                else:
                    p = row; m_nombre = ""

                if not hasattr(p, 'codigo_barras'):
                     # If p is not a Producto (e.g. row structure failed completely), skip
                     continue

                code = (p.codigo_barras or "").strip()
                if not code: code = f"INT{p.id:06d}"

                items.append({
                    "id": p.id,
                    "marca": m_nombre,
                    "nombre": p.nombre,
                    "code": code,
                    "equivalencia": p.codigo_equivalencia,
                    "sku": p.sku,
                    "cod_prov": p.codigo_proveedor,
                    "precio": p.precio_minorista
                })

        # Open the new Unified Dialog
        dlg = EtiquetasPreviewDialog(items, self)
        dlg.exec_()
