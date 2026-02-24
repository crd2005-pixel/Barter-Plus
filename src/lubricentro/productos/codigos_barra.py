# -*- coding: utf-8 -*-
import os
import datetime as dt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QHeaderView, QLabel, QCheckBox,
    QDialog, QFormLayout, QDoubleSpinBox, QComboBox, QFileDialog
)
from PyQt5.QtCore import Qt, QSettings, QSizeF, QRectF
from PyQt5.QtGui import QColor, QPainter, QFont, QPen, QBrush
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog

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
        self.resize(350, 250)
        self.settings = QSettings("BarterPlus", "LabelConfig")

        lay = QVBoxLayout(self)
        form = QFormLayout()

        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["A4 (Grilla)", "Rollo / Térmica (Individual)"])

        self.sp_width = QDoubleSpinBox(); self.sp_width.setRange(10, 300); self.sp_width.setSuffix(" mm")
        self.sp_height = QDoubleSpinBox(); self.sp_height.setRange(10, 300); self.sp_height.setSuffix(" mm")

        # Defaults
        mode = self.settings.value("mode", "A4 (Grilla)")
        w = float(self.settings.value("width", 50.0))
        h = float(self.settings.value("height", 30.0))

        self.cmb_mode.setCurrentText(mode)
        self.sp_width.setValue(w)
        self.sp_height.setValue(h)

        form.addRow("Modo Impresión:", self.cmb_mode)
        form.addRow("Ancho Etiqueta:", self.sp_width)
        form.addRow("Alto Etiqueta:", self.sp_height)

        lay.addLayout(form)

        btns = QHBoxLayout()
        btn_ok = QPushButton("Guardar"); btn_ok.clicked.connect(self._save)
        btn_cancel = QPushButton("Cancelar"); btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_ok); btns.addWidget(btn_cancel)
        lay.addLayout(btns)

    def _save(self):
        self.settings.setValue("mode", self.cmb_mode.currentText())
        self.settings.setValue("width", self.sp_width.value())
        self.settings.setValue("height", self.sp_height.value())
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

        self.btn_exportar = QPushButton("Exportar PDF")
        self.btn_exportar.clicked.connect(self._exportar_pdf)
        bar.addWidget(self.btn_exportar)

        self.btn_imprimir = QPushButton("Imprimir")
        self.btn_imprimir.setStyleSheet("font-weight: bold; color: blue;")
        self.btn_imprimir.clicked.connect(self._imprimir)
        bar.addWidget(self.btn_imprimir)

        layout.addLayout(bar)

        # Tabla
        # Cols: Check, ID, Marca, Producto, Código
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
            # Join Marca if possible
            if Marca:
                q = s.query(Producto, Marca.nombre).outerjoin(Marca, Producto.marca_id == Marca.id).filter(Producto.activo == True)
            else:
                q = s.query(Producto).filter(Producto.activo == True)

            prods = q.all()

            rows = []
            for row in prods:
                if Marca:
                    # row is (Producto, Marca.nombre), either tuple or SQLAlchemy Row (unpackable)
                    p, m_nombre = row
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

    def _get_selected_items(self):
        items = []
        for r in range(self.tbl.rowCount()):
            if self.tbl.item(r, 0).checkState() == Qt.Checked:
                pid = self.tbl.item(r, 1).data(Qt.UserRole)
                marca = self.tbl.item(r, 2).text()
                nom = self.tbl.item(r, 3).text()
                code = self.tbl.item(r, 4).text().strip()
                if not code:
                    code = f"INT{pid:06d}"
                items.append({
                    "id": pid, "marca": marca, "nombre": nom, "code": code
                })
        return items

    def _imprimir(self):
        self._run_print_job(to_pdf=False)

    def _exportar_pdf(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Exportar Etiquetas PDF", "", "PDF Files (*.pdf)")
        if not filename:
            return
        if not filename.endswith(".pdf"):
            filename += ".pdf"
        self._run_print_job(to_pdf=True, pdf_filename=filename)

    def _run_print_job(self, to_pdf=False, pdf_filename=""):
        items = self._get_selected_items()
        if not items:
            QMessageBox.warning(self, "Imprimir", "No hay items seleccionados.")
            return

        settings = QSettings("BarterPlus", "LabelConfig")
        mode = settings.value("mode", "A4 (Grilla)")

        printer = QPrinter(QPrinter.HighResolution)

        if to_pdf:
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(pdf_filename)

        # Configurar tamaño si es rollo
        if mode == "Rollo / Térmica (Individual)":
            try:
                w_mm = float(settings.value("width", 50.0))
                h_mm = float(settings.value("height", 30.0))
                printer.setPaperSize(QSizeF(w_mm, h_mm), QPrinter.Millimeter)
                printer.setPageMargins(1.0, 1.0, 1.0, 1.0, QPrinter.Millimeter)
            except: pass
        else:
            # A4
            printer.setPageSize(QPrinter.A4)

        if not to_pdf:
            dlg = QPrintDialog(printer, self)
            if dlg.exec_() != QPrintDialog.Accepted:
                return

        painter = QPainter()
        if not painter.begin(printer):
            QMessageBox.critical(self, "Error", "No se pudo iniciar la impresión.")
            return

        try:
            if mode.startswith("Rollo"):
                self._print_roll(painter, printer, items)
            else:
                self._print_a4(painter, printer, items)

            if to_pdf:
                QMessageBox.information(self, "Exportar", f"PDF guardado en: {pdf_filename}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error imprimiendo: {e}")
            import traceback; traceback.print_exc()
        finally:
            painter.end()

    def _draw_label_content(self, painter, rect, item):
        # rect es QRectF en pixeles

        # Margen interno
        margin = rect.width() * 0.05
        inner = rect.adjusted(margin, margin, -margin, -margin)

        h = inner.height()

        # 1. Marca (Top, Bold)
        font_marca = QFont("Arial", 10, QFont.Bold)
        font_marca.setPointSizeF(max(6, h * 0.12))
        painter.setFont(font_marca)

        fm = painter.fontMetrics()
        marca_txt = (item["marca"] or "").upper()
        rect_marca = QRectF(inner.x(), inner.y(), inner.width(), fm.height())
        painter.drawText(rect_marca, Qt.AlignCenter, marca_txt)

        # 2. Descripcion (Below Marca)
        y_cursor = rect_marca.bottom() + (h * 0.02)

        font_desc = QFont("Arial", 8)
        font_desc.setPointSizeF(max(5, h * 0.10))
        painter.setFont(font_desc)
        fm_desc = painter.fontMetrics()

        desc_h = fm_desc.height() * 2 # Max 2 lineas
        rect_desc = QRectF(inner.x(), y_cursor, inner.width(), desc_h)

        opts = Qt.AlignCenter | Qt.TextWordWrap
        painter.drawText(rect_desc, opts, item["nombre"])

        # 3. Barcode + Code Text (Bottom)
        # Calculate space from bottom

        font_code = QFont("Courier New", 8)
        font_code.setPointSizeF(max(5, h * 0.08))
        painter.setFont(font_code)
        fm_code = painter.fontMetrics()
        code_h = fm_code.height()

        rect_code = QRectF(inner.x(), inner.bottom() - code_h, inner.width(), code_h)

        # Barcode above text
        y_bar_bottom = rect_code.top() - (h * 0.02)
        y_bar_top = rect_desc.bottom() + (h * 0.02)
        bar_h = y_bar_bottom - y_bar_top

        if bar_h > 5: # Min height for barcode
            self._draw_barcode_bars(painter, inner.x(), y_bar_top, inner.width(), bar_h, item["code"])

        painter.drawText(rect_code, Qt.AlignCenter, item["code"])

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
                # Draw rect slightly larger to avoid gaps due to float rounding?
                # No, standard rect is fine.
                painter.drawRect(QRectF(curr_x, y, width_px, h))

            curr_x += width_px
            is_bar = not is_bar

    def _print_roll(self, painter, printer, items):
        rect = printer.pageRect(QPrinter.DevicePixel)
        for i, item in enumerate(items):
            if i > 0:
                printer.newPage()
            self._draw_label_content(painter, rect, item)

    def _print_a4(self, painter, printer, items):
        page_rect = printer.pageRect(QPrinter.DevicePixel)
        cols = 3
        rows = 8

        cell_w = page_rect.width() / cols
        cell_h = page_rect.height() / rows

        idx = 0
        for item in items:
            if idx > 0 and idx % (cols*rows) == 0:
                printer.newPage()

            c = idx % cols
            r = (idx // cols) % rows # Reset row index per page
            # Calculation of r needs to be relative to page start
            # But idx grows indefinitely.
            # Page index logic:
            items_per_page = cols * rows
            page_idx = idx // items_per_page
            item_idx_on_page = idx % items_per_page

            c = item_idx_on_page % cols
            r = item_idx_on_page // cols

            x = c * cell_w
            y = r * cell_h

            rect = QRectF(x, y, cell_w, cell_h)
            self._draw_label_content(painter, rect, item)

            idx += 1
