# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QHBoxLayout, QDialog, QFormLayout, QLineEdit, QLabel, QMessageBox, QFileDialog
from PyQt5.QtCore import Qt
import datetime as dt
from db import SessionLocal, CierreCaja, CierreCajaItem, CierreCajaAjuste

def _fmt(n):
    try: return f"${float(n):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception: return "$0,00"

class HistorialCajaTab(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        self.tbl = QTableWidget(0, 8)
        self.tbl.setHorizontalHeaderLabels(["ID","Desde","Hasta","Total","Efectivo","Transf.","Débito","Tarjeta"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self.tbl)

        hb = QHBoxLayout()
        self.btn_ver = QPushButton("Ver detalle"); self.btn_pdf = QPushButton("Re-PDF")
        self.btn_aj = QPushButton("Agregar ajuste")
        hb.addStretch(); hb.addWidget(self.btn_ver); hb.addWidget(self.btn_pdf); hb.addWidget(self.btn_aj)
        lay.addLayout(hb)

        self.btn_ver.clicked.connect(self._ver_detalle)
        self.btn_pdf.clicked.connect(self._re_pdf)
        self.btn_aj.clicked.connect(self._ajuste)
        self.cargar()

    def cargar(self):
        self.tbl.setRowCount(0)
        with SessionLocal() as s:
            rows = s.query(CierreCaja).order_by(CierreCaja.id.desc()).all()
            for c in rows:
                r = self.tbl.rowCount(); self.tbl.insertRow(r)
                self.tbl.setItem(r,0,QTableWidgetItem(str(c.id)))
                self.tbl.setItem(r,1,QTableWidgetItem(c.fecha_desde.strftime("%d/%m/%Y %H:%M")))
                self.tbl.setItem(r,2,QTableWidgetItem(c.fecha_hasta.strftime("%d/%m/%Y %H:%M")))
                self.tbl.setItem(r,3,QTableWidgetItem(_fmt(c.total)))
                self.tbl.setItem(r,4,QTableWidgetItem(_fmt(c.total_efectivo)))
                self.tbl.setItem(r,5,QTableWidgetItem(_fmt(c.total_transferencia)))
                self.tbl.setItem(r,6,QTableWidgetItem(_fmt(c.total_debito)))
                self.tbl.setItem(r,7,QTableWidgetItem(_fmt(c.total_credito)))

    def _selected_id(self):
        rows = self.tbl.selectionModel().selectedRows()
        if not rows: return None
        try: return int(self.tbl.item(rows[0].row(),0).text())
        except Exception: return None

    def _ver_detalle(self):
        cid = self._selected_id()
        if not cid: return
        dlg = QDialog(self); dlg.setWindowTitle(f"Detalle cierre #{cid}"); layout = QVBoxLayout(dlg)
        tbl = QTableWidget(0,6); tbl.setHorizontalHeaderLabels(["N°","Fecha","Cliente","Pago","Total","Estado"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); layout.addWidget(tbl)
        with SessionLocal() as s:
            items = s.query(CierreCajaItem).filter_by(cierre_id=cid).all()
            for it in items:
                r = tbl.rowCount(); tbl.insertRow(r)
                for c, val in enumerate([it.numero, it.fecha_txt, it.cliente, it.forma, _fmt(it.total), it.estado]):
                    tbl.setItem(r, c, QTableWidgetItem(val))
        b = QPushButton("Cerrar"); b.clicked.connect(dlg.accept); layout.addWidget(b)
        dlg.exec_()

    def _re_pdf(self):
        from db import CierreCajaPago
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import cm
        cid = self._selected_id()
        if not cid: return
        with SessionLocal() as s:
            c = s.get(CierreCaja, cid)
            items = s.query(CierreCajaItem).filter_by(cierre_id=cid).all()
            pagos = s.query(CierreCajaPago).filter_by(cierre_id=cid).all()
            aj = s.query(CierreCajaAjuste).filter_by(cierre_id=cid).all()
        path, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", f"cierre_{cid}.pdf", "PDF (*.pdf)")
        if not path: return
        cv = canvas.Canvas(path, pagesize=A4); w,h = A4; y = h-2*cm
        cv.setFont("Helvetica-Bold",14); cv.drawString(2*cm,y, f"Cierre de Caja #{cid}"); y -= 0.8*cm
        cv.setFont("Helvetica",10)
        cv.drawString(2*cm,y, f"Período: {c.fecha_desde.strftime('%d/%m/%Y %H:%M')} a {c.fecha_hasta.strftime('%d/%m/%Y %H:%M')}"); y -= 0.6*cm
        cv.drawString(2*cm,y, f"Total: {_fmt(c.total)}  Efec:{_fmt(c.total_efectivo)} Transf:{_fmt(c.total_transferencia)} Déb:{_fmt(c.total_debito)} Tar:{_fmt(c.total_credito)} CtaCte:{_fmt(c.total_ctacte)}"); y -= 0.8*cm
        cv.setFont("Helvetica-Bold",11); cv.drawString(2*cm,y,"Ventas"); y -= 0.5*cm; cv.setFont("Helvetica",9)
        for it in items:
            line = f"{it.numero} | {it.fecha_txt} | {it.cliente} | {it.forma} | {_fmt(it.total)} | {it.estado}"
            if y < 2*cm: cv.showPage(); y = h-2*cm; cv.setFont("Helvetica",9)
            cv.drawString(2*cm,y,line); y -= 0.35*cm
        if aj:
            y -= 0.4*cm; cv.setFont("Helvetica-Bold",11); cv.drawString(2*cm,y,"Ajustes"); y -= 0.5*cm; cv.setFont("Helvetica",9)
            for a in aj:
                line = f"{a.creado_en.strftime('%d/%m/%Y %H:%M')} | {_fmt(a.monto)} | {a.nota or ''}"
                if y < 2*cm: cv.showPage(); y = h-2*cm; cv.setFont("Helvetica",9)
                cv.drawString(2*cm,y,line); y -= 0.35*cm
        cv.save(); QMessageBox.information(self,"Caja","PDF generado.")

    def _ajuste(self):
        cid = self._selected_id()
        if not cid: return
        dlg = QDialog(self); dlg.setWindowTitle("Nuevo ajuste"); f = QFormLayout(dlg)
        inp_monto = QLineEdit(); inp_nota = QLineEdit()
        ok = QPushButton("Guardar"); ok.clicked.connect(dlg.accept)
        f.addRow("Monto (+/-):", inp_monto); f.addRow("Nota:", inp_nota); f.addRow("", ok)
        if dlg.exec_() == dlg.Accepted:
            try:
                monto = float(inp_monto.text().replace(",", "."))
            except Exception:
                QMessageBox.warning(self, "Caja", "Monto inválido."); return
            with SessionLocal() as s:
                s.add(CierreCajaAjuste(cierre_id=cid, monto=monto, nota=inp_nota.text().strip()))
                s.commit()
            QMessageBox.information(self, "Caja", "Ajuste guardado.")
