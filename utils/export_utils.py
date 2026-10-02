import csv
from PyQt6.QtWidgets import QTableWidget, QFileDialog, QMessageBox
from typing import Optional

class ExportUtils:
    @staticmethod
    def exportar_tabla_csv(tabla: QTableWidget, parent=None, base_name: str = "exportacion"):
        """
        Extrae los datos de un QTableWidget y abre un diálogo para guardarlos en CSV.
        """
        if tabla.rowCount() == 0:
            QMessageBox.warning(parent, "Sin Datos", "La tabla está vacía. No hay datos para exportar.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            parent,
            "Exportar Datos",
            f"{base_name}.csv",
            "CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return

        try:
            with open(file_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # Extraer Cabeceras
                headers = []
                for c in range(tabla.columnCount()):
                    header_item = tabla.horizontalHeaderItem(c)
                    headers.append(header_item.text() if header_item else str(c))
                writer.writerow(headers)

                # Extraer Filas
                for r in range(tabla.rowCount()):
                    row_data = []
                    for c in range(tabla.columnCount()):
                        item = tabla.item(r, c)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)

            QMessageBox.information(parent, "Éxito", f"Datos exportados correctamente a:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(parent, "Error de Exportación", f"No se pudo exportar el archivo:\n{str(e)}")

    @staticmethod
    def exportar_tabla_a_pdf(tabla: QTableWidget, titulo_reporte: str, filepath: str):
        from PyQt6.QtPrintSupport import QPrinter
        from PyQt6.QtGui import QTextDocument, QPageSize
        from datetime import datetime

        html = f"""
        <html><head><style>
            body {{ font-family: sans-serif; color: black; }}
            h2 {{ text-align: center; color: #333; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 10px; }}
            th, td {{ border: 1px solid #aaa; padding: 5px; text-align: left; }}
            th {{ background-color: #f0f0f0; font-weight: bold; }}
        </style></head><body>
        <h2>{titulo_reporte}</h2>
        <p>Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        <table><thead><tr>
        """
        for col in range(tabla.columnCount()):
            item = tabla.horizontalHeaderItem(col)
            html += f"<th>{item.text() if item else ''}</th>"
        html += "</tr></thead><tbody>"

        for row in range(tabla.rowCount()):
            html += "<tr>"
            for col in range(tabla.columnCount()):
                item = tabla.item(row, col)
                html += f"<td>{item.text() if item else ''}</td>"
            html += "</tr>"
        html += "</tbody></table></body></html>"

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(filepath)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))

        doc = QTextDocument()
        doc.setHtml(html)
        doc.print(printer)
