from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QInputDialog, QDialog,
    QFormLayout, QLineEdit, QComboBox, QTabWidget, QSpinBox, QDateEdit, QCompleter, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QDate, QStringListModel
from PyQt6.QtGui import QFont
from services.compras_service import ComprasService
from services.proveedor_service import ProveedorService
from services.producto_service import ProductoService
import datetime as dt

class SugerenciasTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.cargar_datos()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Botonera
        btn_lay = QHBoxLayout()
        self.btn_recargar = QPushButton("Recargar Sugerencias")
        self.btn_recargar.clicked.connect(self.cargar_datos)

        self.btn_exportar = QPushButton("Exportar Pedido (Texto/Clipboard)")
        self.btn_exportar.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        self.btn_exportar.clicked.connect(self.exportar_pedido)

        btn_lay.addWidget(self.btn_recargar)
        btn_lay.addStretch()
        btn_lay.addWidget(self.btn_exportar)
        layout.addLayout(btn_lay)

        # Grilla
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["SKU", "Proveedor", "Producto", "Stock Actual", "Stock Mínimo", "Cant. Sugerida"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        layout.addWidget(self.table)

    def cargar_datos(self):
        sugerencias = ComprasService.obtener_sugerencias_pedido()
        self.table.setRowCount(len(sugerencias))

        for row, s in enumerate(sugerencias):
            p = s['producto']
            cant = s['cantidad_sugerida']

            prov_nom = p.proveedor.nombre if p.proveedor else "Sin Proveedor"

            self.table.setItem(row, 0, QTableWidgetItem(p.sku or "-"))
            self.table.setItem(row, 1, QTableWidgetItem(prov_nom))
            self.table.setItem(row, 2, QTableWidgetItem(p.nombre))

            i_act = QTableWidgetItem(str(p.stock_actual))
            if p.stock_actual <= 0:
                i_act.setForeground(Qt.GlobalColor.red)
            self.table.setItem(row, 3, i_act)

            self.table.setItem(row, 4, QTableWidgetItem(str(p.stock_minimo)))

            i_sug = QTableWidgetItem(str(cant))
            font = QFont()
            font.setBold(True)
            i_sug.setFont(font)
            self.table.setItem(row, 5, i_sug)

    def exportar_pedido(self):
        from PyQt6.QtWidgets import QApplication
        filas = self.table.rowCount()
        if filas == 0:
            QMessageBox.warning(self, "Vacio", "No hay sugerencias para exportar.")
            return

        lineas = ["--- PEDIDO SUGERIDO ---"]
        for r in range(filas):
            prov = self.table.item(r, 1).text()
            prod = self.table.item(r, 2).text()
            cant = self.table.item(r, 5).text()
            lineas.append(f"[{prov}] {prod} -> Pedir: {cant}")

        texto_final = "\n".join(lineas)
        clipboard = QApplication.clipboard()
        clipboard.setText(texto_final)

        QMessageBox.information(self, "Exportado", "El pedido ha sido copiado al portapapeles. Puede pegarlo en WhatsApp o Email.")


class IngresoFacturaTab(QWidget):
    def __init__(self):
        super().__init__()
        self.carrito = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Cabecera de Factura
        header_form = QFormLayout()

        self.combo_proveedor = QComboBox()
        self.combo_proveedor.setEditable(True)
        self.combo_proveedor.setPlaceholderText("Seleccionar Proveedor...")
        self.completer_prov = QCompleter()
        self.completer_prov.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer_prov.setFilterMode(Qt.MatchFlag.MatchContains)
        self.combo_proveedor.setCompleter(self.completer_prov)

        self.txt_factura = QLineEdit()
        self.txt_factura.setPlaceholderText("0001-00000001")

        self.date_factura = QDateEdit()
        self.date_factura.setCalendarPopup(True)
        self.date_factura.setDate(QDate.currentDate())

        header_form.addRow("Proveedor:", self.combo_proveedor)
        header_form.addRow("Nº Factura:", self.txt_factura)
        header_form.addRow("Fecha:", self.date_factura)

        layout.addLayout(header_form)

        # Buscador de Productos
        buscar_lay = QHBoxLayout()
        self.txt_buscar = QLineEdit()
        self.txt_buscar.setPlaceholderText("Ingresar Nombre, SKU o Cód. Barras...")

        self.completer_prod = QCompleter()
        self.completer_prod.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer_prod.setFilterMode(Qt.MatchFlag.MatchContains)
        self.txt_buscar.setCompleter(self.completer_prod)

        self.spin_cant = QDoubleSpinBox()
        self.spin_cant.setRange(0.01, 99999.0)
        self.spin_cant.setValue(1.0)

        self.btn_agregar = QPushButton("Agregar al Ingreso")
        self.btn_agregar.clicked.connect(self.agregar_item)

        buscar_lay.addWidget(QLabel("Producto:"))
        buscar_lay.addWidget(self.txt_buscar)
        buscar_lay.addWidget(QLabel("Cant:"))
        buscar_lay.addWidget(self.spin_cant)
        buscar_lay.addWidget(self.btn_agregar)

        layout.addLayout(buscar_lay)

        # Grilla editable
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Producto", "Cant. Comprada", "Nuevo Costo Unitario", "Subtotal"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.table.itemChanged.connect(self.recalcular_totales)

        # Panel inferior
        bot_lay = QHBoxLayout()
        self.lbl_total = QLabel("Total Factura: $0.00")
        self.lbl_total.setStyleSheet("font-size: 20px; font-weight: bold;")

        self.btn_guardar = QPushButton("Guardar Ingreso de Stock")
        self.btn_guardar.setStyleSheet("background-color: #0275d8; color: white; font-weight: bold; padding: 10px;")
        self.btn_guardar.clicked.connect(self.procesar_compra)

        bot_lay.addStretch()
        bot_lay.addWidget(self.lbl_total)
        bot_lay.addWidget(self.btn_guardar)

        layout.addLayout(bot_lay)

        self.cargar_datos_base()

    def cargar_datos_base(self):
        # Cargar Proveedores
        from database.conexion import get_session
        from database.models.proveedor import Proveedor
        from sqlalchemy import select
        with get_session() as session:
            provs = session.scalars(select(Proveedor)).all()
            self.combo_proveedor.clear()
            nombres_p = []
            for p in provs:
                self.combo_proveedor.addItem(p.nombre, p.id)
                nombres_p.append(p.nombre)
            self.completer_prov.setModel(QStringListModel(nombres_p))

        # Cargar completador de productos
        prods = ProductoService.listar_nombres()
        self.completer_prod.setModel(QStringListModel(prods))

    def agregar_item(self):
        query = self.txt_buscar.text().strip()
        if not query: return

        prod = ProductoService.buscar_por_query_flexible(query)
        if not prod:
            QMessageBox.warning(self, "No encontrado", "Producto no encontrado.")
            return

        cant = self.spin_cant.value()

        # Check if exists in cart
        for item in self.carrito:
            if item['id'] == prod.id:
                item['cantidad'] += cant
                self.render_carrito()
                self.txt_buscar.clear()
                self.spin_cant.setValue(1.0)
                return

        self.carrito.append({
            'id': prod.id,
            'nombre': prod.nombre,
            'cantidad': cant,
            'costo': prod.costo
        })
        self.render_carrito()
        self.txt_buscar.clear()
        self.spin_cant.setValue(1.0)

    def render_carrito(self):
        self.table.itemChanged.disconnect(self.recalcular_totales)
        self.table.setRowCount(len(self.carrito))

        total = 0.0
        for r, item in enumerate(self.carrito):
            i_id = QTableWidgetItem(str(item['id']))
            i_id.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            i_nom = QTableWidgetItem(item['nombre'])
            i_nom.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            i_can = QTableWidgetItem(str(item['cantidad']))
            i_cos = QTableWidgetItem(str(item['costo']))

            sub = item['cantidad'] * item['costo']
            total += sub
            i_sub = QTableWidgetItem(f"${sub:.2f}")
            i_sub.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            self.table.setItem(r, 0, i_id)
            self.table.setItem(r, 1, i_nom)
            self.table.setItem(r, 2, i_can)
            self.table.setItem(r, 3, i_cos)
            self.table.setItem(r, 4, i_sub)

        self.lbl_total.setText(f"Total Factura: ${total:.2f}")
        self.table.itemChanged.connect(self.recalcular_totales)

    def recalcular_totales(self, item):
        row = item.row()
        col = item.column()

        if col in [2, 3]:
            try:
                val = float(item.text().replace(',', '.'))
                if val < 0: val = 0.0

                if col == 2:
                    self.carrito[row]['cantidad'] = val
                else:
                    self.carrito[row]['costo'] = val

                self.render_carrito()
            except ValueError:
                self.render_carrito()

    def procesar_compra(self):
        if not self.carrito:
            QMessageBox.warning(self, "Vacío", "No hay productos en el ingreso.")
            return

        prov_id = self.combo_proveedor.currentData()
        if not prov_id:
            QMessageBox.warning(self, "Error", "Debe seleccionar un Proveedor válido.")
            return

        num_fac = self.txt_factura.text().strip()
        if not num_fac:
            QMessageBox.warning(self, "Error", "Debe indicar el Nº de Factura.")
            return

        total_float = sum(i['cantidad']*i['costo'] for i in self.carrito)

        reply = QMessageBox.question(
            self, "Confirmar Ingreso",
            f"Se registrará la compra por ${total_float:.2f}\nEl stock será actualizado matemáticamente.\n¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                detalles = []
                for i in self.carrito:
                    detalles.append({
                        'producto_id': i['id'],
                        'cantidad': i['cantidad'],
                        'nuevo_costo': i['costo']
                    })

                ComprasService.ingresar_factura_compra(prov_id, num_fac, detalles, total_float)
                QMessageBox.information(self, "Éxito", "Factura procesada. Stock y Costos actualizados.")

                # Reset
                self.carrito = []
                self.txt_factura.clear()
                self.render_carrito()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

class ProveedoresView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.tab_sugerencias = SugerenciasTab()
        self.tab_compras = IngresoFacturaTab()

        self.tabs.addTab(self.tab_sugerencias, "Sugerencias y Pedidos")
        self.tabs.addTab(self.tab_compras, "Facturas de Compra (Ingreso de Stock)")

        layout.addWidget(self.tabs)

    def showEvent(self, event):
        super().showEvent(event)
        self.tab_sugerencias.cargar_datos()
        self.tab_compras.cargar_datos_base()
