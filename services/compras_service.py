from database.conexion import get_session
from database.models.producto import Producto
from database.models.proveedor import Proveedor, ProveedorCuentaCorriente
from database.models.contabilidad import PedidoManual, LibroIVA
from sqlalchemy import select, and_, or_, update
from typing import List, Dict, Optional
import datetime as dt

class ComprasService:

    @staticmethod
    def auditar_necesidades_reposicion():
        """
        Evalúa y marca `requiere_reposicion = True` para los productos que cumplan la regla:
        (stock_actual <= stock_minimo AND stock_minimo > 0) OR (stock_actual < 0).
        """
        with get_session() as session:
            try:
                # 1. Marcar los que necesitan entrar
                stmt_in = update(Producto).where(
                    or_(
                        and_(Producto.stock_actual <= Producto.stock_minimo, Producto.stock_minimo > 0),
                        Producto.stock_actual < 0
                    )
                ).values(requiere_reposicion=True)
                session.execute(stmt_in)

                # 2. Desmarcar los que ya superaron su maximo (Regla de persistencia)
                stmt_out = update(Producto).where(
                    and_(
                        Producto.requiere_reposicion == True,
                        Producto.stock_actual >= Producto.stock_maximo,
                        Producto.stock_maximo > 0 # Para que no se quite si el maximo es 0 y nunca llega
                    )
                ).values(requiere_reposicion=False)
                session.execute(stmt_out)

                session.commit()
            except Exception as e:
                session.rollback()
                print(f"Error auditando reposicion: {e}")

    @staticmethod
    def obtener_pedidos_activos(proveedor_id: Optional[int] = None) -> List[dict]:
        """
        Retorna productos donde requiere_reposicion == True o están en PedidosManuales.
        Si proveedor_id está dado, filtra por él.
        """
        ComprasService.auditar_necesidades_reposicion()
        from sqlalchemy.orm import joinedload

        with get_session() as session:
            stmt = select(Producto).options(joinedload(Producto.proveedor)).where(Producto.requiere_reposicion == True)
            if proveedor_id:
                stmt = stmt.where(Producto.proveedor_id == proveedor_id)

            productos = session.scalars(stmt).all()

            sugerencias = []
            for p in productos:
                # Sugerencia base: llegar al maximo si esta configurado
                if p.stock_maximo > 0:
                    cant = p.stock_maximo - p.stock_actual
                elif p.stock_minimo > 0:
                    cant = p.stock_minimo - p.stock_actual + 5
                else:
                    cant = abs(p.stock_actual) + 5

                if cant <= 0: cant = 1

                session.expunge(p)
                sugerencias.append({
                    'producto': p,
                    'cantidad_sugerida': cant
                })

            return sugerencias

    @staticmethod
    def generar_pdf_pedido(filepath: str, datos: List[Dict], proveedor_nombre: str):
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet

        doc = SimpleDocTemplate(filepath, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        titulo = Paragraph("Orden de Pedido - Barter Plus", styles['Title'])
        fecha = Paragraph(f"Fecha: {dt.date.today().strftime('%d/%m/%Y')}", styles['Normal'])
        prov = Paragraph(f"Proveedor: {proveedor_nombre}", styles['Normal'])

        elements.extend([titulo, Spacer(1, 12), fecha, prov, Spacer(1, 12)])

        data_table = [["SKU", "Producto", "Cant. a Pedir"]]
        for d in datos:
            data_table.append([str(d['sku']), str(d['nombre']), str(d['cantidad'])])

        t = Table(data_table, colWidths=[100, 300, 100])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,1), (-1,-1), colors.beige),
            ('GRID', (0,0), (-1,-1), 1, colors.black)
        ]))

        elements.append(t)
        doc.build(elements)

    @staticmethod
    def ingresar_factura_compra(proveedor_id: int, num_factura: str, tipo_comprobante: str, monto_iva: float, detalles: List[Dict], total_factura: float):
        """
        Ingresa una factura.
        `detalles` es lista de dicts: {'producto_id': int, 'cantidad': float, 'nuevo_costo': float}
        Reglas:
        - Sumar cantidad al stock_actual.
        - Sobrescribir costo base.
        - Registrar deuda en proveedor_cuenta_corriente.
        """
        with get_session() as session:
            try:
                for item in detalles:
                    prod = session.get(Producto, item['producto_id'])
                    if not prod:
                        raise ValueError(f"Producto ID {item['producto_id']} no encontrado.")

                    prod.stock_actual += item['cantidad']

                    # Cierre logico de reposición (si ya superó su límite al ingresar esto)
                    if prod.stock_maximo > 0 and prod.stock_actual >= prod.stock_maximo:
                        prod.requiere_reposicion = False

                    if item['nuevo_costo'] > 0:
                        prod.costo = item['nuevo_costo']

                ultimo_mov = session.query(ProveedorCuentaCorriente)\
                    .filter_by(proveedor_id=proveedor_id)\
                    .order_by(ProveedorCuentaCorriente.id.desc())\
                    .first()

                saldo_anterior = ultimo_mov.saldo if ultimo_mov else 0.0
                nuevo_saldo = saldo_anterior + total_factura

                mov_cc = ProveedorCuentaCorriente(
                    proveedor_id=proveedor_id,
                    concepto=f"Factura Compra #{num_factura}",
                    debe=0.0,
                    haber=total_factura,
                    saldo=nuevo_saldo
                )
                session.add(mov_cc)

                # Impacto Fiscal (Libro IVA)
                if tipo_comprobante.startswith("Factura"):
                    libro_iva = LibroIVA(
                        fecha=dt.datetime.utcnow(),
                        tipo="Compra",
                        comprobante=f"{tipo_comprobante} {num_factura}",
                        neto_gravado=total_factura,
                        iva_21=monto_iva,
                        total=total_factura + monto_iva
                    )
                    session.add(libro_iva)

                session.commit()
            except Exception as e:
                session.rollback()
                raise e
