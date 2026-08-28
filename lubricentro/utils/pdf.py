# -*- coding: utf-8 -*-
import os
import datetime as dt
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet

def generar_pedidos_proveedores_pdf(groups: dict, filepath: str):
    """
    Genera un PDF con los pedidos agrupados por proveedor.
    groups: dict { "Proveedor": [ {producto, cantidad, costo_unit, subtotal}, ... ] }
    """
    doc = SimpleDocTemplate(filepath, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # Título
    elements.append(Paragraph("<b>Pedidos a Proveedores</b>", styles["Title"]))
    elements.append(Paragraph(f"Fecha de generación: {dt.datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    grand_total = 0.0

    for proveedor, items in groups.items():
        # Encabezado del proveedor
        elements.append(Paragraph(f"<b>Proveedor: {proveedor}</b>", styles["Heading2"]))

        # Tabla de items
        data = [["Producto", "Cant", "Costo", "Subtotal"]]
        prov_total = 0.0

        for it in items:
            nom = str(it.get("producto", ""))
            cant = float(it.get("cantidad", 0))
            uni = str(it.get("unidad", ""))
            cost = float(it.get("costo_unit", 0))
            sub = float(it.get("subtotal", 0))
            prov_total += sub
            grand_total += sub

            cant_str = f"{cant:.2f} {uni}" if uni else f"{cant:.2f}"
            data.append([
                nom[:40],
                cant_str,
                f"{cost:.2f}",
                f"{sub:.2f}"
            ])

        # Total proveedor
        data.append(["", "", "Total Proveedor:", f"{prov_total:.2f}"])

        t = Table(data, colWidths=[250, 80, 80, 80])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.black),
            ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'), # Fila total
        ]))
        elements.append(t)
        elements.append(Spacer(1, 12))

    # Total general
    elements.append(Paragraph(f"<b>TOTAL GENERAL: {grand_total:,.2f}</b>", styles["Heading1"]))

    doc.build(elements)
