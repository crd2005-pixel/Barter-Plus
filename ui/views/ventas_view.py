from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QMessageBox,
    QComboBox, QFormLayout, QGroupBox, QInputDialog, QSplitter
)
from PyQt6.QtCore import Qt, QStringListModel
from PyQt6.QtGui import QFont, QColor, QBrush, QShortcut, QKeySequence
from PyQt6.QtWidgets import QCompleter
from services.producto_service import ProductoService
from services.cliente_service import ClienteService
from services.venta_service import VentaService
from database.conexion import get_session
from database.models.cliente import Cliente
from database.models.producto import Producto
from sqlalchemy import select

class VentasTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.carrito = []

        self.splitter = QSplitter(Qt.Orientation.Vertical)

        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout(self.top_widget)
        self.top_layout.setContentsMargins(0,0,0,0)

        # --- ZONA CLIENTE Y OPCIONES ---
        self.box_opciones = QHBoxLayout()

        self.form_cliente = QFormLayout()
        self.combo_clientes = QComboBox()
        self.combo_clientes.setEditable(True)
        self.combo_clientes.setPlaceholderText("Buscar o seleccionar cliente...")
        self.combo_tipo_cliente = QComboBox()
        self.combo_tipo_cliente.addItems(["Cliente Común", "Cliente Especial (-10%)"])

        self.btn_nuevo_cliente = QPushButton("+")
        self.btn_nuevo_cliente.setToolTip("Agregar Nuevo Cliente")
        self.btn_nuevo_cliente.setFixedWidth(30)

        box_cli = QHBoxLayout()
        box_cli.addWidget(self.combo_clientes)
        box_cli.addWidget(self.btn_nuevo_cliente)

        self.form_cliente.addRow("Cliente:", box_cli)
        self.form_cliente.addRow("Tipo:", self.combo_tipo_cliente)

        self.form_pago = QFormLayout()
        self.combo_pago = QComboBox()
        self.combo_pago.addItems(["Efectivo", "Transferencia", "Débito", "Tarjeta", "Cuenta Corriente", "Combinada"])

        self.combo_comprobante = QComboBox()
        self.combo_comprobante.addItems(["Remito", "Factura"])

        self.form_pago.addRow("Comprobante:", self.combo_comprobante)
        self.form_pago.addRow("Método Pago:", self.combo_pago)

        self.box_opciones.addLayout(self.form_cliente)
        self.box_opciones.addLayout(self.form_pago)
        self.box_opciones.addStretch()

        self.btn_consulta_rapida = QPushButton("Consultar Precio (F2)")
        self.btn_consulta_rapida.setStyleSheet("padding: 10px; font-weight: bold; background-color: #f39c12; color: white;")

        self.btn_sugerir_pedido = QPushButton("Anotar Pedido Manual")
        self.btn_sugerir_pedido.setStyleSheet("padding: 10px; font-weight: bold; background-color: #8e44ad; color: white;")

        self.box_opciones.addWidget(self.btn_sugerir_pedido)
        self.box_opciones.addWidget(self.btn_consulta_rapida)

        self.top_layout.addLayout(self.box_opciones)

        # --- ZONA DE INGRESO (Escáner) ---
        self.box_ingreso = QHBoxLayout()
        self.txt_codigo = QLineEdit()
        self.txt_codigo.setPlaceholderText("Escanee SKU/Cód. de Barras o ingrese nombre y presione Enter...")
        font_input = QFont()
        font_input.setPointSize(16)
        self.txt_codigo.setFont(font_input)
        self.txt_codigo.setMinimumHeight(45)

        self.txt_cantidad = QLineEdit("1")
        self.txt_cantidad.setPlaceholderText("Cant.")
        self.txt_cantidad.setMaximumWidth(80)
        self.txt_cantidad.setFont(font_input)
        self.txt_cantidad.setMinimumHeight(45)

        self.btn_buscar = QPushButton("Agregar al Carrito")
        self.btn_buscar.setMinimumHeight(45)
        self.btn_buscar.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold;")

        self.box_ingreso.addWidget(self.txt_codigo)
        self.box_ingreso.addWidget(QLabel(" x "))
        self.box_ingreso.addWidget(self.txt_cantidad)
        self.box_ingreso.addWidget(self.btn_buscar)

        self.top_layout.addLayout(self.box_ingreso)

        # --- QCompleter SETUP ---
        self.setup_completers()

        # --- GRILLA DEL CARRITO ---
        self.bottom_widget = QWidget()
        self.bottom_layout = QVBoxLayout(self.bottom_widget)
        self.bottom_layout.setContentsMargins(0,0,0,0)

        self.tabla = QTableWidget(0, 7)
        self.tabla.setHorizontalHeaderLabels([
            "ID", "Código", "Producto", "Precio Unitario", "Cant.", "Desc. Unid ($)", "Subtotal"
        ])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.setAlternatingRowColors(True)

        self.tabla.setColumnWidth(0, 50)
        self.tabla.setColumnWidth(1, 150)
        self.tabla.setColumnWidth(2, 250)
        self.tabla.setColumnWidth(3, 100)
        self.tabla.setColumnWidth(4, 80)
        self.tabla.setColumnWidth(5, 100)

        self.bottom_layout.addWidget(self.tabla)

        # --- PANEL DE TOTALES Y COBRO ---
        self.box_inferior = QHBoxLayout()

        self.btn_descuento = QPushButton("Aplicar Desc. Global")
        self.btn_descuento.setStyleSheet("padding: 10px; font-weight: bold;")
        self.descuento_global = 0.0

        self.lbl_total_texto = QLabel("TOTAL:")
        font_total = QFont()
        font_total.setPointSize(24)
        font_total.setBold(True)
        self.lbl_total_texto.setFont(font_total)

        self.lbl_total_valor = QLabel("$ 0.00")
        self.lbl_total_valor.setFont(font_total)
        self.lbl_total_valor.setStyleSheet("color: #2e7d32;") # Verde

        self.btn_cobrar = QPushButton("COBRAR FACTURA (F12)")
        self.btn_cobrar.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; font-size: 20px; padding: 15px;")
        self.btn_cobrar.setMinimumWidth(250)
        self.btn_cobrar.setEnabled(False)

        self.box_inferior.addWidget(self.btn_descuento)
        self.box_inferior.addStretch()
        self.box_inferior.addWidget(self.lbl_total_texto)
        self.box_inferior.addWidget(self.lbl_total_valor)
        self.box_inferior.addSpacing(20)
        self.box_inferior.addWidget(self.btn_cobrar)

        self.bottom_layout.addLayout(self.box_inferior)

        self.splitter.addWidget(self.top_widget)
        self.splitter.addWidget(self.bottom_widget)
        self.splitter.setSizes([150, 500])
        self.layout.addWidget(self.splitter)

        # --- CONEXIONES ---
        self.txt_codigo.returnPressed.connect(self.agregar_al_carrito)
        self.btn_buscar.clicked.connect(self.agregar_al_carrito)
        self.tabla.itemChanged.connect(self.modificar_cantidad_grid)
        self.btn_cobrar.clicked.connect(self.procesar_cobro)
        self.combo_tipo_cliente.currentIndexChanged.connect(self.actualizar_ui)
        self.btn_descuento.clicked.connect(self.aplicar_descuento_global)
        self.btn_consulta_rapida.clicked.connect(self.consultar_precio_rapido)
        self.btn_sugerir_pedido.clicked.connect(self.sugerir_pedido)
        self.btn_nuevo_cliente.clicked.connect(self.crear_cliente_rapido)

        # --- ATAJOS DE TECLADO ---
        shortcut_f12 = QShortcut(QKeySequence("F12"), self)
        shortcut_f12.activated.connect(self.procesar_cobro)

        shortcut_f2 = QShortcut(QKeySequence("F2"), self)
        shortcut_f2.activated.connect(self.consultar_precio_rapido)

        self.cargar_clientes()

    def setup_completers(self):
        # Completer Clientes
        self.completer_cli = QCompleter()
        self.completer_cli.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer_cli.setFilterMode(Qt.MatchFlag.MatchContains)
        self.combo_clientes.setCompleter(self.completer_cli)

        # Completer Productos
        self.completer_prod = QCompleter()
        self.completer_prod.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer_prod.setFilterMode(Qt.MatchFlag.MatchContains)
        self.txt_codigo.setCompleter(self.completer_prod)
        self.cargar_completer_productos()

    def cargar_completer_productos(self):
        with get_session() as session:
            prods = session.scalars(select(Producto.nombre)).all()
            model = QStringListModel(prods)
            self.completer_prod.setModel(model)

    def crear_cliente_rapido(self):
        nombre, ok = QInputDialog.getText(self, "Nuevo Cliente", "Nombre del cliente:")
        if ok and nombre.strip():
            try:
                nuevo = ClienteService.crear_cliente(nombre.strip())
                self.cargar_clientes()
                # Seleccionarlo
                index = self.combo_clientes.findData(nuevo.id)
                if index >= 0:
                    self.combo_clientes.setCurrentIndex(index)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo crear: {e}")

    def consultar_precio_rapido(self):
        query, ok = QInputDialog.getText(self, "Consultar Precio (F2)", "Ingrese nombre o código de barras:")
        if ok and query.strip():
            with get_session() as session:
                from database.models.producto import Producto
                stmt = select(Producto).where(
                    (Producto.codigo_barras == query.strip()) |
                    (Producto.sku == query.strip()) |
                    (Producto.nombre.icontains(query.strip()))
                )
                prod = session.scalars(stmt).first()
                if prod:
                    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel
                    dialog = QDialog(self)
                    dialog.setWindowTitle("Consulta de Precio")
                    dialog.resize(400, 250)
                    lay = QVBoxLayout(dialog)

                    lbl_nom = QLabel(f"<b>Producto:</b> {prod.nombre}")
                    lbl_nom.setWordWrap(True)
                    lbl_nom.setStyleSheet("font-size: 16px;")

                    pf = prod.precio_minorista
                    if prod.es_granel and prod.divisor_granel > 0:
                        pf = pf / prod.divisor_granel

                    lbl_pf = QLabel(f"$ {pf:.2f}")
                    lbl_pf.setStyleSheet("font-size: 32px; font-weight: bold; color: #2e7d32;")
                    lbl_pf.setAlignment(Qt.AlignmentFlag.AlignCenter)

                    margen_neto = pf - prod.costo

                    lbl_detalles = QLabel(
                        f"<b>Costo:</b> $ {prod.costo:.2f}<br>"
                        f"<b>Margen Neto:</b> $ {margen_neto:.2f}<br>"
                        f"<b>Stock Actual:</b> {prod.stock_actual:.2f}"
                    )
                    lbl_detalles.setStyleSheet("font-size: 14px;")

                    lay.addWidget(lbl_nom)
                    lay.addStretch()
                    lay.addWidget(lbl_pf)
                    lay.addStretch()
                    lay.addWidget(lbl_detalles)

                    dialog.exec()
                else:
                    QMessageBox.warning(self, "No Encontrado", f"No se encontró ningún producto con: {query}")

    def sugerir_pedido(self):
        nota, ok = QInputDialog.getText(self, "Anotar Pedido Manual", "El cliente solicita:")
        if ok and nota.strip():
            try:
                ProductoService.agregar_pedido_manual(nota.strip())
                QMessageBox.information(self, "Éxito", "Pedido manual registrado en la base de datos.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo guardar: {e}")

    def cargar_clientes(self):
        with get_session() as session:
            clientes = session.scalars(select(Cliente)).all()
            self.combo_clientes.clear()
            self.combo_clientes.addItem("Consumidor Final", None)
            nombres = []
            for c in clientes:
                self.combo_clientes.addItem(c.nombre, c.id)
                nombres.append(c.nombre)

            model = QStringListModel(["Consumidor Final"] + nombres)
            self.completer_cli.setModel(model)

    def showEvent(self, event):
        super().showEvent(event)
        self.cargar_completer_productos()
        super().showEvent(event)
        self.txt_codigo.setFocus()

    def aplicar_descuento_global(self):
        val, ok = QInputDialog.getDouble(self, "Descuento Global", "Ingrese monto a descontar del total:", 0, 0, 999999, 2)
        if ok:
            self.descuento_global = val
            self.actualizar_ui()

    def agregar_al_carrito(self):
        query = self.txt_codigo.text().strip()
        if not query: return

        try:
            cant_input = float(self.txt_cantidad.text().replace(',', '.'))
        except ValueError:
            cant_input = 1.0

        # Buscar en BD por SKU o Codigo Barras o Nombre (simplificado para POS)
        with get_session() as session:
            from database.models.producto import Producto
            stmt = select(Producto).where(
                (Producto.codigo_barras == query) |
                (Producto.sku == query) |
                (Producto.nombre.icontains(query))
            )
            prod = session.scalars(stmt).first()
            if prod:
                session.expunge(prod)

        if not prod:
            QMessageBox.warning(self, "No Encontrado", f"No se encontró un producto coincidente con: {query}")
            self.txt_codigo.selectAll()
            self.txt_codigo.setFocus()
            return

        # Advertencia Stock
        if prod.stock_actual <= 0:
            QMessageBox.warning(self, "Stock Agotado", f"El producto '{prod.nombre}' tiene stock <= 0. La venta continuará.")

        # Fraccionamiento de Precio si es granel
        precio_base_calculado = prod.precio_minorista
        if prod.es_granel and prod.divisor_granel > 0:
            precio_base_calculado = prod.precio_minorista / prod.divisor_granel

        # Revisar si ya está en carrito
        encontrado = False
        for item in self.carrito:
            if item['id'] == prod.id:
                item['cantidad'] += cant_input
                encontrado = True
                break

        if not encontrado:
            nombre_mostrar = f"{prod.nombre} (Granel)" if prod.es_granel else prod.nombre
            self.carrito.append({
                'id': prod.id,
                'codigo': prod.codigo_barras or prod.sku or "N/A",
                'nombre': nombre_mostrar,
                'precio_base': precio_base_calculado,
                'cantidad': cant_input,
                'descuento_unit': 0.0
            })

        self.actualizar_ui()
        self.txt_codigo.clear()
        self.txt_cantidad.setText("1")
        self.txt_codigo.setFocus()

    def actualizar_ui(self):
        # Desconectar temporalmente
        self.tabla.itemChanged.disconnect(self.modificar_cantidad_grid)

        self.tabla.setRowCount(len(self.carrito))
        subtotal_general = 0.0

        # Logica Cliente Especial
        es_especial = (self.combo_tipo_cliente.currentIndex() == 1)

        for r, item in enumerate(self.carrito):
            precio_unitario = item['precio_base'] * 0.9 if es_especial else item['precio_base']
            precio_neto = precio_unitario - item['descuento_unit']
            if precio_neto < 0: precio_neto = 0.0

            subtotal = item['cantidad'] * precio_neto
            subtotal_general += subtotal

            i_id = QTableWidgetItem(str(item['id']))
            i_id.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            i_cod = QTableWidgetItem(item['codigo'])
            i_cod.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            i_nom = QTableWidgetItem(item['nombre'])
            i_nom.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            i_pre = QTableWidgetItem(f"$ {precio_unitario:.2f}")
            i_pre.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            if es_especial:
                i_pre.setBackground(QBrush(QColor(241, 196, 15, 60))) # Amarillo para desc

            i_can = QTableWidgetItem(f"{item['cantidad']:.2f}")

            # Descuento unitario (Editable)
            i_desc = QTableWidgetItem(f"{item['descuento_unit']:.2f}")

            i_sub = QTableWidgetItem(f"$ {subtotal:.2f}")
            i_sub.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            self.tabla.setItem(r, 0, i_id)
            self.tabla.setItem(r, 1, i_cod)
            self.tabla.setItem(r, 2, i_nom)
            self.tabla.setItem(r, 3, i_pre)
            self.tabla.setItem(r, 4, i_can)
            self.tabla.setItem(r, 5, i_desc)
            self.tabla.setItem(r, 6, i_sub)

        total_final = subtotal_general - self.descuento_global
        if total_final < 0: total_final = 0.0

        self.lbl_total_valor.setText(f"$ {total_final:.2f}")
        self.btn_cobrar.setEnabled(len(self.carrito) > 0)

        self.tabla.itemChanged.connect(self.modificar_cantidad_grid)

    def modificar_cantidad_grid(self, item):
        col = item.column()
        row = item.row()

        if col == 4: # Cantidad
            try:
                nueva_cant = float(item.text().replace(',', '.'))
                if nueva_cant <= 0:
                    self.carrito.pop(row)
                else:
                    self.carrito[row]['cantidad'] = nueva_cant
                self.actualizar_ui()
            except ValueError:
                self.actualizar_ui()

        elif col == 5: # Descuento Unitario
            try:
                nuevo_desc = float(item.text().replace(',', '.'))
                if nuevo_desc < 0: nuevo_desc = 0.0
                self.carrito[row]['descuento_unit'] = nuevo_desc
                self.actualizar_ui()
            except ValueError:
                self.actualizar_ui()

    def procesar_cobro(self):
        if not self.carrito: return

        # Parse total final
        total_txt = self.lbl_total_valor.text().replace('$ ', '').replace(',', '.')
        total_float = float(total_txt)

        metodo = self.combo_pago.currentText()
        tipo_comprobante = self.combo_comprobante.currentText()
        cliente_id = self.combo_clientes.currentData()

        # Validar si es Cta Cte
        if metodo == "Cuenta Corriente" and not cliente_id:
            QMessageBox.warning(self, "Error", "Debe seleccionar un Cliente válido para pagos en Cuenta Corriente.")
            return

        # Modal rápido de pago efectivo
        monto_abonado = total_float
        if metodo == "Efectivo":
            val, ok = QInputDialog.getDouble(self, "Cobro en Efectivo", f"Total: $ {total_float:.2f}\n\nAbona con:", total_float, 0, 9999999, 2)
            if not ok: return
            monto_abonado = val
            if monto_abonado < total_float:
                QMessageBox.warning(self, "Falta dinero", "El monto ingresado es menor al total.")
                return

        reply = QMessageBox.question(
            self, "Confirmar Cobro",
            f"¿Registrar venta por $ {total_float:.2f} en {metodo}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                es_especial = (self.combo_tipo_cliente.currentIndex() == 1)
                detalles_final = []

                for item in self.carrito:
                    precio_unitario = item['precio_base'] * 0.9 if es_especial else item['precio_base']
                    detalles_final.append({
                        'producto_id': item['id'],
                        'cantidad': item['cantidad'],
                        'precio_unitario': precio_unitario,
                        'descuento_unitario': item['descuento_unit']
                    })

                venta = VentaService.procesar_venta(
                    detalles_final,
                    cliente_id=cliente_id,
                    metodo_pago=metodo,
                    monto_abonado=monto_abonado,
                    descuento_global=self.descuento_global,
                    tipo_comprobante=tipo_comprobante
                )

                vuelto = venta.vuelto
                msg = f"Venta Registrada Exitosamente (ID: {venta.id})"
                if vuelto > 0: msg += f"\n\nVuelto a entregar: $ {vuelto:.2f}"

                QMessageBox.information(self, "Éxito", msg)

                # Reset
                self.carrito = []
                self.descuento_global = 0.0
                self.txt_codigo.clear()
                self.combo_clientes.setCurrentIndex(0)
                self.combo_tipo_cliente.setCurrentIndex(0)
                self.actualizar_ui()
                self.txt_codigo.setFocus()

            except Exception as e:
                QMessageBox.critical(self, "Error de Sistema", f"No se pudo guardar la venta:\n{str(e)}")
