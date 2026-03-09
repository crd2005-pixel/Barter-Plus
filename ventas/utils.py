# ventas/utils.py
import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from db import SessionLocal, Venta

def generar_remito_pdf(venta: Venta, path=None):
    if path is None:
        path = f"remito_{venta.numero or venta.id}.pdf"
    c = canvas.Canvas(path, pagesize=A4)
    y = 820
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, f"Remito N° {venta.numero or venta.id}"); y -= 24
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Fecha: {venta.fecha.strftime('%d/%m/%Y %H:%M')}"); y -= 16
    cliente = venta.cliente.nombre if getattr(venta, "cliente", None) else "Consumidor Final"
    c.drawString(50, y, f"Cliente: {cliente}"); y -= 24

    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Detalle"); y -= 14
    c.setFont("Helvetica", 10)

    with SessionLocal() as s:
        v = s.query(Venta).filter(Venta.id == venta.id).first()
        for it in v.items:
            nombre = it.producto.nombre if getattr(it, "producto", None) else ""
            c.drawString(50, y, f"{it.cantidad} x {nombre}")
            c.drawRightString(550, y, f"${it.subtotal:.2f}")
            y -= 14

    y -= 10
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(550, y, f"TOTAL: ${venta.total:.2f}")
    c.showPage()
    c.save()
    return path

def exportar_historial_pdf(path="historial_ventas.pdf", ventas=None):
    c = canvas.Canvas(path, pagesize=A4)
    y = 820
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Historial de Ventas"); y -= 24
    c.setFont("Helvetica", 10)
    if ventas is None:
        with SessionLocal() as s:
            ventas = s.query(Venta).order_by(Venta.fecha.desc()).limit(500).all()
    for v in ventas:
        cliente = v.cliente.nombre if getattr(v, "cliente", None) else ""
        c.drawString(50, y, f"{v.numero or v.id} {v.fecha.strftime('%d/%m/%Y %H:%M')}  {cliente}")
        c.drawRightString(550, y, f"${v.total:.2f}")
        y -= 14
        if y < 80:
            c.showPage()
            y = 820
            c.setFont("Helvetica", 10)
    c.save()
    return path

exportar_venta_pdf = exportar_historial_pdf

def calcular_totales(items):
    return sum(x[3] for x in items)
