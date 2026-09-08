from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from services.producto_service import ProductoService
from services.venta_service import VentaService

class VentasTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.carrito = [] # Lista de diccionarios con info del producto

        # --- ZONA DE INGRESO (Escáner) ---
        self.box_ingreso = QHBoxLayout()
        self.txt_codigo = QLineEdit()
        self.txt_codigo.setPlaceholderText("Escanee o ingrese Código de Barras y presione Enter...")
        font_input = QFont()
        font_input.setPointSize(18)
        self.txt_codigo.setFont(font_input)
        self.txt_codigo.setMinimumHeight(50)

        self.btn_buscar = QPushButton("Buscar")
        self.btn_buscar.setMinimumHeight(50)

        self.box_ingreso.addWidget(self.txt_codigo)
        self.box_ingreso.addWidget(self.btn_buscar)

        self.layout.addLayout(self.box_ingreso)

        # --- GRILLA DEL CARRITO ---
        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels([
            "Código", "Producto", "Precio Unitario", "Cantidad", "Subtotal"
        ])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.setAlternatingRowColors(True)

        self.tabla.setColumnWidth(0, 150)
        self.tabla.setColumnWidth(1, 300)
        self.tabla.setColumnWidth(2, 120)
        self.tabla.setColumnWidth(3, 100)

        self.layout.addWidget(self.tabla)

        # --- PANEL DE TOTALES Y COBRO ---
        self.box_inferior = QHBoxLayout()

        self.lbl_total_texto = QLabel("TOTAL:")
        font_total = QFont()
        font_total.setPointSize(24)
        font_total.setBold(True)
        self.lbl_total_texto.setFont(font_total)

        self.lbl_total_valor = QLabel("$ 0.00")
        self.lbl_total_valor.setFont(font_total)
        self.lbl_total_valor.setStyleSheet("color: #2e7d32;") # Verde

        self.btn_cobrar = QPushButton("COBRAR (F12)")
        self.btn_cobrar.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; font-size: 20px; padding: 15px;")
        self.btn_cobrar.setMinimumWidth(200)
        self.btn_cobrar.setEnabled(False)

        self.box_inferior.addWidget(self.lbl_total_texto)
        self.box_inferior.addWidget(self.lbl_total_valor)
        self.box_inferior.addStretch()
        self.box_inferior.addWidget(self.btn_cobrar)

        self.layout.addLayout(self.box_inferior)

        # --- CONEXIONES ---
        self.txt_codigo.returnPressed.connect(self.agregar_al_carrito)
        self.btn_buscar.clicked.connect(self.agregar_al_carrito)
        self.tabla.itemChanged.connect(self.modificar_cantidad)
        self.btn_cobrar.clicked.connect(self.procesar_cobro)

    def agregar_al_carrito(self):
        codigo = self.txt_codigo.text().strip()
        if not codigo:
            return

        # Buscar en BD
        prod = ProductoService.buscar_por_codigo(codigo)
        if not prod:
            QMessageBox.warning(self, "No Encontrado", f"No se encontró un producto con el código: {codigo}")
            self.txt_codigo.clear()
            self.txt_codigo.setFocus()
            return

        # Verificar stock (Aviso, pero permitimos vender para no trabar el flujo)
        if prod.stock_maximo <= 0:
            QMessageBox.warning(self, "Stock Agotado", f"El producto '{prod.nombre}' tiene stock en 0 o negativo.")

        # Revisar si ya está en carrito
        encontrado = False
        for i, item in enumerate(self.carrito):
            if item['id'] == prod.id:
                item['cantidad'] += 1.0
                encontrado = True
                break

        if not encontrado:
            self.carrito.append({
                'id': prod.id,
                'codigo': prod.codigo_barras or "",
                'nombre': prod.nombre,
                'precio': prod.precio_minorista,
                'cantidad': 1.0
            })

        self.actualizar_ui()
        self.txt_codigo.clear()
        self.txt_codigo.setFocus()

    def actualizar_ui(self):
        # Desconectar temporalmente el evento para no ciclar al reescribir
        self.tabla.itemChanged.disconnect(self.modificar_cantidad)

        self.tabla.setRowCount(len(self.carrito))
        total = 0.0

        for r, item in enumerate(self.carrito):
            subtotal = item['cantidad'] * item['precio']
            total += subtotal

            i_cod = QTableWidgetItem(item['codigo'])
            i_cod.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            i_nom = QTableWidgetItem(item['nombre'])
            i_nom.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            i_pre = QTableWidgetItem(f"$ {item['precio']:.2f}")
            i_pre.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            # Cantidad es editable
            i_can = QTableWidgetItem(f"{item['cantidad']:.2f}")

            i_sub = QTableWidgetItem(f"$ {subtotal:.2f}")
            i_sub.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            self.tabla.setItem(r, 0, i_cod)
            self.tabla.setItem(r, 1, i_nom)
            self.tabla.setItem(r, 2, i_pre)
            self.tabla.setItem(r, 3, i_can)
            self.tabla.setItem(r, 4, i_sub)

        self.lbl_total_valor.setText(f"$ {total:.2f}")
        self.btn_cobrar.setEnabled(len(self.carrito) > 0)

        # Reconectar
        self.tabla.itemChanged.connect(self.modificar_cantidad)

    def modificar_cantidad(self, item):
        if item.column() == 3: # Columna Cantidad
            try:
                row = item.row()
                nueva_cant = float(item.text().replace(',', '.'))

                if nueva_cant <= 0:
                    # Eliminar del carrito si la cantidad es 0 o negativa
                    self.carrito.pop(row)
                else:
                    self.carrito[row]['cantidad'] = nueva_cant

                self.actualizar_ui()
            except ValueError:
                self.actualizar_ui() # Restaura el valor anterior si escribe letras

    def procesar_cobro(self):
        if not self.carrito:
            return

        reply = QMessageBox.question(
            self, "Cobrar",
            f"¿Confirma la venta por {self.lbl_total_valor.text()}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                detalles = []
                monto_total = 0.0
                for item in self.carrito:
                    detalles.append({
                        'producto_id': item['id'],
                        'cantidad': item['cantidad']
                    })
                    monto_total += item['cantidad'] * item['precio']

                # Ejecutar cobro vía servicio (Efectivo por defecto en esta fase)
                venta = VentaService.procesar_venta(detalles, metodo_pago="Efectivo", monto_abonado=monto_total)

                QMessageBox.information(self, "Venta Exitosa", f"Venta #{venta.id} registrada correctamente.")

                # Limpiar POS
                self.carrito = []
                self.actualizar_ui()
                self.txt_codigo.setFocus()

            except Exception as e:
                QMessageBox.critical(self, "Error de Venta", f"Ocurrió un error al procesar el cobro:\n{str(e)}")
