# -*- coding: utf-8 -*-
import os
import datetime as dt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QHeaderView, QLabel, QCheckBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from db import SessionLocal, Producto

# ReportLab imports
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.graphics.barcode import code128
from reportlab.lib.units import mm

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

        self.btn_generar = QPushButton("Asignar Códigos Auto (a faltantes)")
        self.btn_generar.setToolTip("Genera códigos tipo 'INT-ID' para productos sin código")
        self.btn_generar.clicked.connect(self._asignar_codigos_faltantes)
        bar.addWidget(self.btn_generar)

        self.btn_exportar = QPushButton("Exportar PDF Etiquetas")
        self.btn_exportar.clicked.connect(self._exportar_pdf)
        bar.addWidget(self.btn_exportar)

        layout.addLayout(bar)

        # Tabla
        self.tbl = QTableWidget()
        self.tbl.setColumnCount(4)
        self.tbl.setHorizontalHeaderLabels(["Sel.", "ID", "Producto", "Código Barras"])
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tbl.setColumnWidth(0, 40)
        self.tbl.setColumnWidth(1, 60)
        layout.addWidget(self.tbl)

    def refresh(self):
        self._load_data()

    def _load_data(self):
        self.tbl.setRowCount(0)
        solo_sin = self.chk_solo_sin_codigo.isChecked()

        with SessionLocal() as s:
            q = s.query(Producto).filter(Producto.activo == True)
            prods = q.all()

            # Filtro en memoria para evitar complejidad en query
            rows = []
            for p in prods:
                cb = (p.codigo_barras or "").strip()
                if solo_sin and cb:
                    continue
                rows.append(p)

            self.tbl.setRowCount(len(rows))
            for r, p in enumerate(rows):
                # Checkbox
                ck = QTableWidgetItem()
                ck.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                # Por defecto chequeado si no tiene código, para facilitar
                if not p.codigo_barras:
                    ck.setCheckState(Qt.Checked)
                else:
                    ck.setCheckState(Qt.Unchecked)
                self.tbl.setItem(r, 0, ck)

                # ID
                self.tbl.setItem(r, 1, QTableWidgetItem(str(p.id)))

                # Nombre
                self.tbl.setItem(r, 2, QTableWidgetItem(p.nombre))

                # Codigo
                cb_text = p.codigo_barras if p.codigo_barras else ""
                item_cb = QTableWidgetItem(cb_text)
                if not cb_text:
                    item_cb.setBackground(QColor("#fff9c4")) # Amarillo suave
                self.tbl.setItem(r, 3, item_cb)

                # Guardamos ID en data por si acaso
                self.tbl.item(r, 1).setData(Qt.UserRole, p.id)

    def _asignar_codigos_faltantes(self):
        # Genera códigos automáticos para los que no tienen
        # Formato propuesto: "INT-{id}" o solo números si se prefiere Code128 numérico.
        # Code128 soporta alfanumérico.

        count = 0
        with SessionLocal() as s:
            # Iterar filas chequeadas o todas las faltantes? Mejor solo lo que se ve
            # Pero para ser consistente con la DB, mejor buscar en DB
            prods = s.query(Producto).filter(Producto.activo == True).all()
            for p in prods:
                if not p.codigo_barras or not p.codigo_barras.strip():
                    # Generar código. Usaremos formato '20000000' + ID (tipo EAN8 fake) o 'INT'+ID
                    # Para simplificar y compatibilidad Code128: INT{ID}
                    # O mejor, un numero simple de 8 digitos basado en ID
                    nuevo_codigo = f"INT{p.id:06d}"
                    p.codigo_barras = nuevo_codigo
                    count += 1
            if count > 0:
                s.commit()
                QMessageBox.information(self, "Generar", f"Se generaron {count} códigos nuevos.")
                self._load_data()
            else:
                QMessageBox.information(self, "Generar", "No había productos sin código (o no se pudieron generar).")

    def _exportar_pdf(self):
        items_a_imprimir = []

        # Recorrer tabla
        for r in range(self.tbl.rowCount()):
            if self.tbl.item(r, 0).checkState() == Qt.Checked:
                pid = self.tbl.item(r, 1).data(Qt.UserRole)
                # Buscar datos frescos o usar los de la tabla
                nom = self.tbl.item(r, 2).text()
                code = self.tbl.item(r, 3).text().strip()

                if not code:
                    # Si el usuario seleccionó uno sin código y NO le generó código antes,
                    # podemos generarlo al vuelo solo para el PDF o saltarlo.
                    # El requerimiento dice "cree códigos... y exporte".
                    # Si el botón de arriba lo hace en BD, aquí asumimos que ya deberían tener.
                    # Si no tiene, generamos uno temporal? Mejor avisar.
                    # O generar temporal basado en ID.
                    code = f"INT{pid:06d}"

                items_a_imprimir.append({"nombre": nom, "code": code})

        if not items_a_imprimir:
            QMessageBox.warning(self, "PDF", "No hay items seleccionados.")
            return

        filename = f"etiquetas_barras_{dt.datetime.now():%H%M%S}.pdf"
        try:
            self._generar_pdf_reportlab(filename, items_a_imprimir)
            QMessageBox.information(self, "PDF", f"PDF generado: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al generar PDF: {e}")

    def _generar_pdf_reportlab(self, filename, items):
        c = canvas.Canvas(filename, pagesize=A4)
        width, height = A4

        # Configuración de etiquetas (ejemplo: 3 columnas x 8 filas = 24 por página)
        # O simplemente una lista continua. Haremos una grilla simple.
        cols = 3
        rows = 8
        margin_x = 10 * mm
        margin_y = 15 * mm

        cw = (width - 2 * margin_x) / cols
        ch = (height - 2 * margin_y) / rows

        x_off = margin_x
        y_off = height - margin_y - ch

        col_idx = 0
        row_idx = 0

        for it in items:
            # Dibujar celda
            self._dibujar_etiqueta(c, x_off, y_off, cw, ch, it)

            # Avanzar
            col_idx += 1
            x_off += cw

            if col_idx >= cols:
                col_idx = 0
                x_off = margin_x
                row_idx += 1
                y_off -= ch

            if row_idx >= rows:
                c.showPage()
                row_idx = 0
                col_idx = 0
                x_off = margin_x
                y_off = height - margin_y - ch

        c.save()

    def _dibujar_etiqueta(self, c, x, y, w, h, item):
        # Marco para depuración (opcional)
        # c.rect(x, y, w, h)

        nombre = item["nombre"]
        code_val = item["code"]

        # Recortar nombre si es muy largo
        if len(nombre) > 25:
            nombre = nombre[:22] + "..."

        # Texto nombre
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(x + w/2, y + h - 15, nombre)

        # Codigo de barras
        # Usamos Code128
        try:
            barcode = code128.Code128(code_val, barHeight=15*mm, barWidth=1.2)
            # Centrar barcode
            # Ancho aprox del barcode = len(code) * ...
            # reportlab dibuja desde esquina inferior izquierda
            # b_width = barcode.width # no siempre preciso antes de dibujar
            # forzamos posición
            bc_x = x + (w - barcode.width) / 2
            bc_y = y + 15
            barcode.drawOn(c, bc_x, bc_y)

            # Texto del código abajo
            c.setFont("Helvetica", 8)
            c.drawCentredString(x + w/2, y + 5, code_val)

        except Exception as e:
            c.drawString(x + 5, y + h/2, f"Error Barcode: {code_val}")
