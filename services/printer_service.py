import sys
import os
import datetime as dt
from database.conexion import get_session
from database.models.producto import Producto
from database.models.venta import Venta
from ui.components.printer.barcode_utils import get_code128_pattern

class PrinterService:
    @staticmethod
    def _obtener_impresora(tipo: str) -> str:
        from PyQt6.QtCore import QSettings
        settings = QSettings("BarterPlus", "HardwareConfig")

        if tipo == "Etiquetas":
            printer_name = settings.value("printer_etiquetas", "").strip()
        else:
            printer_name = settings.value("printer_tickets", "").strip()

        if printer_name:
            return printer_name

        if sys.platform == 'win32':
            import win32print
            try:
                return win32print.GetDefaultPrinter()
            except:
                pass

        raise ValueError(f"No se pudo detectar una impresora configurada para {tipo}.")

    @staticmethod
    def imprimir_etiqueta(producto_id: int):
        if sys.platform != 'win32':
            raise OSError("La impresión directa por spool está limitada a Windows (requiere pywin32).")

        import win32print
        import win32ui

        with get_session() as session:
            prod = session.get(Producto, producto_id)
            if not prod:
                raise ValueError("Producto no encontrado.")

            printer_name = PrinterService._obtener_impresora("Etiquetas")

            codigo = prod.codigo_proveedor or prod.codigo_barras or f"INT{prod.id:06d}"

            hprinter = win32print.OpenPrinter(printer_name)
            try:
                hdc = win32ui.CreateDC()
                hdc.CreatePrinterDC(printer_name)
                hdc.StartDoc("Etiqueta Barter Plus")
                hdc.StartPage()

                dpi = hdc.GetDeviceCaps(88) # LOGPIXELSX

                font = win32ui.CreateFont({"name": "Arial", "height": int(dpi * 0.12), "weight": 700})
                hdc.SelectObject(font)
                nombre_corto = (prod.nombre[:25] + '..') if len(prod.nombre) > 25 else prod.nombre
                hdc.TextOut(10, 10, nombre_corto)

                try:
                    pattern = get_code128_pattern(codigo)
                    curr_x = 20
                    y_bar = int(dpi * 0.25)
                    h_bar = int(dpi * 0.3)
                    bar_w = 2
                    is_bar = True
                    for width_val in pattern:
                        if is_bar:
                            hdc.Rectangle((curr_x, y_bar, curr_x + (width_val * bar_w), y_bar + h_bar))
                        curr_x += (width_val * bar_w)
                        is_bar = not is_bar
                except Exception as e:
                    hdc.TextOut(10, int(dpi * 0.3), f"Err Barcode: {codigo}")

                font2 = win32ui.CreateFont({"name": "Arial", "height": int(dpi * 0.1), "weight": 400})
                hdc.SelectObject(font2)
                hdc.TextOut(10, int(dpi * 0.6), f"COD: {codigo}")

                if hasattr(prod, 'equivalencias') and prod.equivalencias:
                    font_eq = win32ui.CreateFont({"name": "Arial", "height": int(dpi * 0.08), "weight": 400})
                    hdc.SelectObject(font_eq)
                    hdc.TextOut(10, int(dpi * 0.72), f"EQ: {prod.equivalencias}")

                font3 = win32ui.CreateFont({"name": "Arial", "height": int(dpi * 0.15), "weight": 800})
                hdc.SelectObject(font3)
                hdc.TextOut(10, int(dpi * 0.82), f"$ {prod.precio_minorista:.2f}")

                hdc.EndPage()
                hdc.EndDoc()
                hdc.DeleteDC()
            finally:
                win32print.ClosePrinter(hprinter)

    @staticmethod
    def imprimir_comprobante_venta(venta_id: int):
        if sys.platform != 'win32':
            return # Silent skip for non-Windows environments

        import win32print
        import win32ui
        from sqlalchemy.orm import joinedload
        from sqlalchemy import select

        with get_session() as session:
            venta = session.scalars(
                select(Venta).options(joinedload(Venta.detalles)).where(Venta.id == venta_id)
            ).first()
            if not venta:
                raise ValueError("Venta no encontrada.")

            try:
                printer_name = PrinterService._obtener_impresora("Tickets")
            except ValueError:
                return # Si no hay impresora de tickets, fallamos silenciosamente

            hprinter = win32print.OpenPrinter(printer_name)
            try:
                hdc = win32ui.CreateDC()
                hdc.CreatePrinterDC(printer_name)
                hdc.StartDoc("Ticket Venta")
                hdc.StartPage()

                dpi = hdc.GetDeviceCaps(88) # LOGPIXELSX
                y = 10

                # Header
                font_title = win32ui.CreateFont({"name": "Arial", "height": int(dpi * 0.15), "weight": 800})
                hdc.SelectObject(font_title)
                hdc.TextOut(10, y, "BARTER PLUS")
                y += int(dpi * 0.2)

                font_normal = win32ui.CreateFont({"name": "Arial", "height": int(dpi * 0.1), "weight": 400})
                hdc.SelectObject(font_normal)

                f_str = venta.fecha.strftime("%Y-%m-%d %H:%M")
                hdc.TextOut(10, y, f"Fecha: {f_str}")
                y += int(dpi * 0.15)
                hdc.TextOut(10, y, f"Ticket N: {venta.id}")
                y += int(dpi * 0.15)
                hdc.TextOut(10, y, f"Tipo: {venta.tipo_comprobante}")
                y += int(dpi * 0.2)

                hdc.TextOut(10, y, "-"*30)
                y += int(dpi * 0.15)

                # Items
                for d in venta.detalles:
                    desc = (d.descripcion[:20] + '..') if len(d.descripcion) > 20 else d.descripcion
                    line1 = f"{d.cantidad}x {desc}"
                    line2 = f"   $ {d.precio_unitario:.2f}  ->  $ {d.subtotal:.2f}"
                    hdc.TextOut(10, y, line1)
                    y += int(dpi * 0.15)
                    hdc.TextOut(10, y, line2)
                    y += int(dpi * 0.15)

                hdc.TextOut(10, y, "-"*30)
                y += int(dpi * 0.15)

                # Totales
                font_bold = win32ui.CreateFont({"name": "Arial", "height": int(dpi * 0.12), "weight": 700})
                hdc.SelectObject(font_bold)
                hdc.TextOut(10, y, f"TOTAL: $ {venta.total:.2f}")
                y += int(dpi * 0.2)

                hdc.SelectObject(font_normal)
                hdc.TextOut(10, y, f"Pago en: {venta.metodo_pago}")
                y += int(dpi * 0.15)

                # Si pagó con tarjeta buscar el lote
                if venta.metodo_pago in ['Tarjeta', 'Débito']:
                    from database.models.contabilidad import IngresoDiferido
                    ingreso = session.scalars(select(IngresoDiferido).where(IngresoDiferido.venta_id == venta.id)).first()
                    if ingreso:
                        hdc.TextOut(10, y, f"Lote: {ingreso.lote} / Cupón: {ingreso.cupon}")
                        y += int(dpi * 0.15)

                hdc.TextOut(10, y, "-"*30)
                y += int(dpi * 0.15)
                hdc.TextOut(10, y, "¡Gracias por su compra!")

                hdc.EndPage()
                hdc.EndDoc()
                hdc.DeleteDC()
            finally:
                win32print.ClosePrinter(hprinter)
