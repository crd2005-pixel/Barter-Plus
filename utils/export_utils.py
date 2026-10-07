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
