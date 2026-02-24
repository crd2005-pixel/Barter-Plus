# -*- coding: utf-8 -*-
import os
import datetime as dt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QHeaderView, QLabel, QCheckBox,
    QDialog, QFormLayout, QDoubleSpinBox, QComboBox, QFileDialog,
    QGroupBox, QScrollArea
)
from PyQt5.QtCore import Qt, QSettings, QSizeF, QRectF
from PyQt5.QtGui import QColor, QPainter, QFont, QPen, QBrush
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog

from db import SessionLocal, Producto
try:
    from db.models.productos import Marca
except ImportError:
    Marca = None

from .barcode_utils import get_code128_pattern

class LabelConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración de Etiquetas")
        self.resize(450, 400)
        self.settings = QSettings("BarterPlus", "LabelConfig")

        lay = QVBoxLayout(self)

        # --- Dimensiones ---
        gb_dim = QGroupBox("Dimensiones y Modo")
        form_dim = QFormLayout(gb_dim)

        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["A4 (Grilla)", "Rollo / Térmica (Individual)"])

        self.sp_width = QDoubleSpinBox(); self.sp_width.setRange(10, 300); self.sp_width.setSuffix(" mm")
        self.sp_height = QDoubleSpinBox(); self.sp_height.setRange(10, 300); self.sp_height.setSuffix(" mm")

        form_dim.addRow("Modo Impresión:", self.cmb_mode)
        form_dim.addRow("Ancho Etiqueta:", self.sp_width)
        form_dim.addRow("Alto Etiqueta:", self.sp_height)
        lay.addWidget(gb_dim)

        # --- Contenido ---
        gb_cont = QGroupBox("Contenido Visible")
        v_cont = QVBoxLayout(gb_cont)

        self.chk_marca = QCheckBox("Marca")
        self.chk_nombre = QCheckBox("Nombre Producto")
        self.chk_codigo = QCheckBox("Código de Barras (Gráfico + Texto)")
        self.chk_equivalencia = QCheckBox("Código Equivalencia")
        self.chk_sku = QCheckBox("SKU / Código Interno")
        self.chk_cod_prov = QCheckBox("Código Proveedor")
        self.chk_precio = QCheckBox("Precio Final")

        v_cont.addWidget(self.chk_marca)
        v_cont.addWidget(self.chk_nombre)
        v_cont.addWidget(self.chk_codigo)
        v_cont.addWidget(self.chk_equivalencia)
        v_cont.addWidget(self.chk_sku)
        v_cont.addWidget(self.chk_cod_prov)
        v_cont.addWidget(self.chk_precio)
        lay.addWidget(gb_cont)

        # --- Ajustes ---
        gb_adj = QGroupBox("Ajustes")
        form_adj = QFormLayout(gb_adj)

        self.sp_font_scale = QDoubleSpinBox(); self.sp_font_scale.setRange(0.5, 3.0); self.sp_font_scale.setSingleStep(0.1)
        self.sp_margin = QDoubleSpinBox(); self.sp_margin.setRange(0, 20); self.sp_margin.setSuffix(" mm")

        form_adj.addRow("Escala Fuente:", self.sp_font_scale)
        form_adj.addRow("Margen Interno:", self.sp_margin)
        lay.addWidget(gb_adj)

        # Defaults
        mode = self.settings.value("mode", "A4 (Grilla)")
        w = float(self.settings.value("width", 50.0))
        h = float(self.settings.value("height", 30.0))

        self.cmb_mode.setCurrentText(mode)
        self.sp_width.setValue(w)
        self.sp_height.setValue(h)

        self.chk_marca.setChecked(self.settings.value("show_marca", True, type=bool))
        self.chk_nombre.setChecked(self.settings.value("show_nombre", True, type=bool))
        self.chk_codigo.setChecked(self.settings.value("show_codigo", True, type=bool))
        self.chk_equivalencia.setChecked(self.settings.value("show_equivalencia", False, type=bool))
        self.chk_sku.setChecked(self.settings.value("show_sku", False, type=bool))
        self.chk_cod_prov.setChecked(self.settings.value("show_cod_prov", False, type=bool))
        self.chk_precio.setChecked(self.settings.value("show_precio", False, type=bool))

        self.sp_font_scale.setValue(float(self.settings.value("font_scale", 1.0)))
        self.sp_margin.setValue(float(self.settings.value("margin_mm", 1.0)))

        btns = QHBoxLayout()
        btn_ok = QPushButton("Guardar"); btn_ok.clicked.connect(self._save)
        btn_cancel = QPushButton("Cancelar"); btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_ok); btns.addWidget(btn_cancel)
        lay.addLayout(btns)

    def _save(self):
        self.settings.setValue("mode", self.cmb_mode.currentText())
        self.settings.setValue("width", self.sp_width.value())
        self.settings.setValue("height", self.sp_height.value())

        self.settings.setValue("show_marca", self.chk_marca.isChecked())
        self.settings.setValue("show_nombre", self.chk_nombre.isChecked())
        self.settings.setValue("show_codigo", self.chk_codigo.isChecked())
        self.settings.setValue("show_equivalencia", self.chk_equivalencia.isChecked())
        self.settings.setValue("show_sku", self.chk_sku.isChecked())
        self.settings.setValue("show_cod_prov", self.chk_cod_prov.isChecked())
        self.settings.setValue("show_precio", self.chk_precio.isChecked())

        self.settings.setValue("font_scale", self.sp_font_scale.value())
        self.settings.setValue("margin_mm", self.sp_margin.value())

        self.accept()

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

        self.btn_config = QPushButton("Config. Etiquetas")
        self.btn_config.clicked.connect(self._config_labels)
        bar.addWidget(self.btn_config)

        self.btn_generar = QPushButton("Asignar Códigos Auto")
        self.btn_generar.setToolTip("Genera códigos 'INT-ID' para productos sin código")
        self.btn_generar.clicked.connect(self._asignar_codigos_faltantes)
        bar.addWidget(self.btn_generar)

        self.btn_preview = QPushButton("Vista Previa")
        self.btn_preview.clicked.connect(self._preview)
        bar.addWidget(self.btn_preview)

        self.btn_exportar = QPushButton("Exportar PDF")
        self.btn_exportar.clicked.connect(self._exportar_pdf)
        bar.addWidget(self.btn_exportar)

        self.btn_imprimir = QPushButton("Imprimir")
        self.btn_imprimir.setStyleSheet("font-weight: bold; color: blue;")
        self.btn_imprimir.clicked.connect(self._imprimir)
        bar.addWidget(self.btn_imprimir)

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
                    # Fix: Handle Row object unpacking manually or safely
                    # SQLAlchemy Row behaves like tuple but let's be safe
                    try:
                        p, m_nombre = row
                    except:
                        # Fallback if unpacking fails (should not happen with query(P, M.name))
                        p = row[0]; m_nombre = row[1]
                else:
                    p = row
                    m_nombre = ""

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
                    p.codigo_barras = nuevo_codigo
                    count += 1
            if count > 0:
                s.commit()
                QMessageBox.information(self, "Generar", f"Se generaron {count} códigos nuevos.")
                self._load_data()
            else:
                QMessageBox.information(self, "Generar", "No había productos sin código.")

    def _config_labels(self):
        LabelConfigDialog(self).exec_()

    def _get_selected_ids(self):
        ids = []
        for r in range(self.tbl.rowCount()):
            if self.tbl.item(r, 0).checkState() == Qt.Checked:
                pid = self.tbl.item(r, 1).data(Qt.UserRole)
                ids.append(pid)
        return ids

    def _preview(self):
        ids = self._get_selected_ids()
        if not ids:
            QMessageBox.warning(self, "Vista Previa", "No hay items seleccionados.")
            return

        printer = QPrinter(QPrinter.HighResolution)
        self._configure_printer(printer)

        dlg = QPrintPreviewDialog(printer, self)
        dlg.paintRequested.connect(self._print_preview_slot)
        dlg.exec_()

    def _print_preview_slot(self, printer):
        self._run_printing_logic(printer, is_preview=True)

    def _imprimir(self):
        ids = self._get_selected_ids()
        if not ids:
            QMessageBox.warning(self, "Imprimir", "No hay items seleccionados.")
            return

        printer = QPrinter(QPrinter.HighResolution)
        self._configure_printer(printer)

        dlg = QPrintDialog(printer, self)
        if dlg.exec_() == QPrintDialog.Accepted:
            self._run_printing_logic(printer, is_preview=False)

    def _exportar_pdf(self):
        ids = self._get_selected_ids()
        if not ids:
            QMessageBox.warning(self, "Exportar", "No hay items seleccionados.")
            return

        filename, _ = QFileDialog.getSaveFileName(self, "Exportar Etiquetas PDF", "", "PDF Files (*.pdf)")
        if not filename:
            return
        if not filename.endswith(".pdf"):
            filename += ".pdf"

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(filename)
        self._configure_printer(printer)

        self._run_printing_logic(printer, is_preview=False)
        QMessageBox.information(self, "Exportar", f"PDF guardado en: {filename}")

    def _configure_printer(self, printer):
        settings = QSettings("BarterPlus", "LabelConfig")
        mode = settings.value("mode", "A4 (Grilla)")

        if mode == "Rollo / Térmica (Individual)":
            try:
                w_mm = float(settings.value("width", 50.0))
                h_mm = float(settings.value("height", 30.0))
                printer.setPaperSize(QSizeF(w_mm, h_mm), QPrinter.Millimeter)
                printer.setPageMargins(1.0, 1.0, 1.0, 1.0, QPrinter.Millimeter) # Minimal margins
            except: pass
        else:
            printer.setPageSize(QPrinter.A4)

    def _run_printing_logic(self, printer, is_preview=False):
        # Fetch fresh data
        ids = self._get_selected_ids()
        items = []
        with SessionLocal() as s:
            if Marca:
                q = s.query(Producto, Marca.nombre).outerjoin(Marca, Producto.marca_id == Marca.id).filter(Producto.id.in_(ids))
            else:
                q = s.query(Producto).filter(Producto.id.in_(ids))

            for row in q.all():
                if Marca:
                    try: p, m_nombre = row
                    except: p = row[0]; m_nombre = row[1]
                else:
                    p = row; m_nombre = ""

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
                    "precio": p.precio_minorista # Assuming simple retail price for label
                })

        painter = QPainter()
        if not painter.begin(printer):
            if not is_preview:
                QMessageBox.critical(self, "Error", "No se pudo iniciar la impresión.")
            return

        try:
            settings = QSettings("BarterPlus", "LabelConfig")
            mode = settings.value("mode", "A4 (Grilla)")

            if mode.startswith("Rollo"):
                self._print_roll(painter, printer, items, settings)
            else:
                self._print_a4(painter, printer, items, settings)
        except Exception as e:
            if not is_preview:
                QMessageBox.critical(self, "Error", f"Error imprimiendo: {e}")
            import traceback; traceback.print_exc()
        finally:
            painter.end()

    def _print_roll(self, painter, printer, items, settings):
        rect = printer.pageRect(QPrinter.DevicePixel)
        for i, item in enumerate(items):
            if i > 0:
                printer.newPage()
            self._draw_label_content(painter, rect, item, settings)

    def _print_a4(self, painter, printer, items, settings):
        page_rect = printer.pageRect(QPrinter.DevicePixel)

        # Determine grid size based on label size (approx) or fixed?
        # A4 is approx 210x297mm.
        # Use settings w/h if valid, else default.
        w_mm = float(settings.value("width", 50.0))
        h_mm = float(settings.value("height", 30.0))

        # Convert mm to pixels (approx, based on printer resolution)
        # But QPrinter handles coordinate system if we set paper size correctly.
        # However, for A4 grid, we need to know how many fit.

        # Logic:
        # page_rect.width() is in DevicePixels.
        # We need to know how many pixels is w_mm.
        # We can use logic: w_px = (w_mm / 210) * page_rect.width() ? No, A4 width is 210mm.

        # Better: define cols/rows fixed for standard label sheets (e.g. 3x8) OR dynamic.
        # Dynamic is better.

        # DPI calculation
        # 1 inch = 25.4 mm
        # dpi = printer.resolution()
        # px = (mm / 25.4) * dpi

        dpi = printer.resolution()
        w_px = (w_mm / 25.4) * dpi
        h_px = (h_mm / 25.4) * dpi

        cols = int(page_rect.width() / w_px)
        rows = int(page_rect.height() / h_px)

        if cols < 1: cols = 1
        if rows < 1: rows = 1

        items_per_page = cols * rows

        idx = 0
        for item in items:
            if idx > 0 and idx % items_per_page == 0:
                printer.newPage()

            page_idx = idx % items_per_page
            c = page_idx % cols
            r = page_idx // cols

            x = c * w_px
            y = r * h_px

            rect = QRectF(x, y, w_px, h_px)
            # Add margin between labels? For now, assume contiguous.

            self._draw_label_content(painter, rect, item, settings)
            idx += 1

    def _draw_label_content(self, painter, rect, item, settings):
        # Config
        show_marca = settings.value("show_marca", True, type=bool)
        show_nombre = settings.value("show_nombre", True, type=bool)
        show_codigo = settings.value("show_codigo", True, type=bool)
        show_equiv = settings.value("show_equivalencia", False, type=bool)
        show_sku = settings.value("show_sku", False, type=bool)
        show_cod_prov = settings.value("show_cod_prov", False, type=bool)
        show_precio = settings.value("show_precio", False, type=bool)

        font_scale = float(settings.value("font_scale", 1.0))
        margin_mm = float(settings.value("margin_mm", 1.0))

        # Margin in pixels
        # Estimate ratio based on rect size vs mm size?
        # Hard to know DPI inside here easily without printer ref, but rect is what we have.
        # Use relative margin.

        # If rect is small (A4 grid), 1mm is small.
        # Let's assume standard density.

        margin = rect.width() * 0.02 * margin_mm # Heuristic
        inner = rect.adjusted(margin, margin, -margin, -margin)

        h = inner.height()
        w = inner.width()

        # Helper for drawing text lines
        # Stack elements: Marca -> Nombre -> Extra Fields -> Barcode

        elements = []

        if show_marca and item["marca"]:
            elements.append({"type": "text", "text": item["marca"].upper(), "bold": True, "size_factor": 0.14})

        if show_nombre and item["nombre"]:
            elements.append({"type": "text", "text": item["nombre"], "bold": False, "size_factor": 0.12, "wrap": True})

        # Extra fields (small)
        extras = []
        if show_equiv and item["equivalencia"]:
            extras.append(f"Eq: {item['equivalencia']}")
        if show_sku and item["sku"]:
            extras.append(f"SKU: {item['sku']}")
        if show_cod_prov and item["cod_prov"]:
            extras.append(f"Prov: {item['cod_prov']}")
        if show_precio:
            extras.append(f"${item['precio']:.2f}")

        if extras:
            elements.append({"type": "text", "text": " | ".join(extras), "bold": False, "size_factor": 0.08})

        if show_codigo:
            elements.append({"type": "barcode", "code": item["code"], "size_factor": 0.35})

        # Layout calculation
        # Distribute available height? Or just stack from top?
        # Stacking from top with fixed spacing is safer.

        y_cursor = inner.y()

        painter.setPen(Qt.black)

        for el in elements:
            # Check remaining space
            if y_cursor >= inner.bottom(): break

            base_size = h * el["size_factor"] * font_scale
            if base_size < 6: base_size = 6 # Min legible size

            font = QFont("Arial", 10)
            if el.get("bold"): font.setBold(True)
            if el["type"] == "barcode": font = QFont("Courier New", 10)

            font.setPointSizeF(base_size) # This is approximate in QPainter coordinate system?
            # Better to setPixelSize if we want strict control relative to rect height
            # font.setPixelSize(int(base_size)) # Use pixel size for robustness
            # But point size is better for printing generally.

            painter.setFont(font)
            fm = painter.fontMetrics()

            if el["type"] == "text":
                flags = Qt.AlignCenter
                if el.get("wrap"):
                    flags |= Qt.TextWordWrap
                    # Limit height for wrapped text (e.g. 2 lines)
                    line_h = fm.height()
                    allowed_h = line_h * 2.2
                    draw_rect = QRectF(inner.x(), y_cursor, w, allowed_h)

                    # Calculate actual needed height
                    needed_rect = fm.boundingRect(QRectF(0,0,w,1000), flags, el["text"])
                    actual_h = min(needed_rect.height(), allowed_h)

                    painter.drawText(draw_rect, flags, el["text"])
                    y_cursor += actual_h + (h * 0.02)
                else:
                    line_h = fm.height()
                    draw_rect = QRectF(inner.x(), y_cursor, w, line_h)
                    painter.drawText(draw_rect, flags, el["text"])
                    y_cursor += line_h + (h * 0.02)

            elif el["type"] == "barcode":
                # Barcode takes remaining space or fixed ratio?
                # Let's give it fixed ratio but push it to bottom if possible?
                # Current logic stacks.

                # Draw text below barcode?
                # The 'code' text is part of barcode element usually.

                code_h = fm.height()

                # Barcode bars height
                bars_h = (h * el["size_factor"]) - code_h
                if bars_h < 10: bars_h = 10

                # Check if we have space
                needed = bars_h + code_h
                if (y_cursor + needed) > inner.bottom():
                    # Shrink bars if needed
                    bars_h = inner.bottom() - y_cursor - code_h

                if bars_h > 2:
                    self._draw_barcode_bars(painter, inner.x(), y_cursor, w, bars_h, el["code"])

                # Draw code text
                y_text = y_cursor + bars_h
                rect_text = QRectF(inner.x(), y_text, w, code_h)
                painter.drawText(rect_text, Qt.AlignCenter, el["code"])

                y_cursor += needed + (h * 0.02)

    def _draw_barcode_bars(self, painter, x, y, w, h, code):
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
                painter.drawRect(QRectF(curr_x, y, width_px, h))

            curr_x += width_px
            is_bar = not is_bar
