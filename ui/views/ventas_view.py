from ui.components.dialogs import FastClientDialog, ItemManualDialog, TicketPreviewDialog
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QDateEdit, QLabel, QMessageBox,
    QComboBox, QFormLayout, QGroupBox, QInputDialog, QSplitter, QSpinBox, QDoubleSpinBox, QDialog
)
from PyQt6.QtCore import Qt, QDate, QStringListModel
from PyQt6.QtGui import QFont, QColor, QBrush, QShortcut, QKeySequence
from PyQt6.QtWidgets import QCompleter
from services.producto_service import ProductoService
from services.cliente_service import ClienteService
from services.venta_service import VentaService



class VentasTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.carrito = []
        self.presupuesto_activo_id = None

        self.splitter = QSplitter(Qt.Orientation.Vertical)

        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout(self.top_widget)
        self.top_layout.setContentsMargins(0,0,0,0)

        # --- ZONA CLIENTE Y OPCIONES ---
        self.layout_cabecera = QVBoxLayout()

        # Fila 1 - Exclusiva para el Cliente
        self.fila_cliente_layout = QHBoxLayout()

        from PyQt6.QtWidgets import QSizePolicy
        self.combo_clientes = QComboBox()
        self.combo_clientes.setEditable(True)
        self.combo_clientes.setPlaceholderText("Buscar o seleccionar cliente...")
        self.combo_clientes.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.combo_clientes.setStyleSheet("margin: 0px; padding: 5px;")

        self.btn_nuevo_cliente = QPushButton("+")
        self.btn_nuevo_cliente.setToolTip("Agregar Nuevo Cliente")
        self.btn_nuevo_cliente.setFixedSize(40, 40)
        self.btn_nuevo_cliente.setStyleSheet("margin: 0px; padding: 0px;")

        self.fila_cliente_layout.addWidget(QLabel("Cliente:"))
        self.fila_cliente_layout.addWidget(self.combo_clientes)
        self.fila_cliente_layout.addWidget(self.btn_nuevo_cliente)
        self.fila_cliente_layout.addStretch()

        # Fila 2 - Controles y Acciones
        self.fila_controles_layout = QHBoxLayout()

        self.combo_pago = QComboBox()
        self.combo_pago.addItems(["Efectivo", "Transferencia", "Débito", "Tarjeta", "Cuenta Corriente", "Cheque", "Combinada"])

        self.combo_comprobante = QComboBox()
        self.combo_comprobante.addItems(["Remito", "Factura A", "Factura B", "Presupuesto"])
        self.combo_comprobante.currentTextChanged.connect(self._actualizar_estado_boton_cobrar)

        # Componentes ocultos para Tarjeta
        self.form_tarjeta = QFormLayout()
        self.combo_tarjeta = QComboBox()
        self.combo_plan_tarjeta = QComboBox()
        self.txt_lote = QLineEdit()
        self.txt_lote.setPlaceholderText("Ej: 12345")
        self.txt_cupon = QLineEdit()
        self.txt_cupon.setPlaceholderText("Ej: 67890")
        self.combo_tarjeta.currentIndexChanged.connect(self.cargar_planes_tarjeta)
        self.combo_plan_tarjeta.currentIndexChanged.connect(self.actualizar_ui)
        self.form_tarjeta.addRow("Tarjeta:", self.combo_tarjeta)
        self.form_tarjeta.addRow("Plan:", self.combo_plan_tarjeta)
        self.form_tarjeta.addRow("Nº Lote:", self.txt_lote)
        self.form_tarjeta.addRow("Nº Cupón:", self.txt_cupon)
        self.widget_tarjeta = QWidget()
        self.widget_tarjeta.setLayout(self.form_tarjeta)
        self.widget_tarjeta.setVisible(False)
        self.combo_pago.currentTextChanged.connect(self.toggle_fecha_acreditacion)

        # Contenedor de Comprobante y Pago para la fila 2
        form_pago_simple = QFormLayout()
        form_pago_simple.addRow("Comprobante:", self.combo_comprobante)
        form_pago_simple.addRow("Método Pago:", self.combo_pago)
        form_pago_simple.addRow(self.widget_tarjeta)

        self.fila_controles_layout.addLayout(form_pago_simple)
        self.fila_controles_layout.addStretch()

        self.btn_consulta_rapida = QPushButton("Consultar Precio (F2)")
        self.btn_consulta_rapida.setStyleSheet("padding: 10px; font-weight: bold; background-color: #f39c12; color: white;")

        self.btn_sugerir_pedido = QPushButton("Anotar Pedido Manual")
        self.btn_sugerir_pedido.setStyleSheet("padding: 10px; font-weight: bold; background-color: #8e44ad; color: white;")

        self.btn_cobrar_cc = QPushButton("Cobrar Cta. Cte.")
        self.btn_cobrar_cc.setStyleSheet("padding: 10px; font-weight: bold; background-color: #d35400; color: white;")

        self.fila_controles_layout.addWidget(self.btn_cobrar_cc)
        self.fila_controles_layout.addWidget(self.btn_sugerir_pedido)
        self.fila_controles_layout.addWidget(self.btn_consulta_rapida)

        # Ensamblaje
        self.layout_cabecera.addLayout(self.fila_cliente_layout)
        self.layout_cabecera.addLayout(self.fila_controles_layout)

        self.top_layout.addLayout(self.layout_cabecera)

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

        self.tabla = QTableWidget(0, 8)
        self.tabla.setHorizontalHeaderLabels([
            "ID", "Código", "Marca", "Producto", "Precio Unitario", "Cant.", "Desc. Unid ($)", "Subtotal"
        ])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.setAlternatingRowColors(True)

        self.tabla.setColumnWidth(0, 50)
        self.tabla.setColumnWidth(1, 120)
        self.tabla.setColumnWidth(2, 100)
        self.tabla.setColumnWidth(3, 250)
        self.tabla.setColumnWidth(4, 100)
        self.tabla.setColumnWidth(5, 80)
        self.tabla.setColumnWidth(6, 100)

        self.bottom_layout.addWidget(self.tabla)

        # --- PANEL DE TOTALES Y COBRO ---
        self.box_inferior = QHBoxLayout()

        self.btn_descuento = QPushButton("Aplicar Desc. Global")
        self.btn_descuento.setStyleSheet("padding: 10px; font-weight: bold;")

        self.btn_buscar_presupuesto = QPushButton("Buscar Presupuesto")
        self.btn_buscar_presupuesto.setStyleSheet("padding: 10px; font-weight: bold; background-color: #3498db; color: white;")

        self.descuento_global = 0.0
        self.cliente_vip = False

        self.lbl_total_texto = QLabel("TOTAL:")
        font_total = QFont()
        font_total.setPointSize(24)
        font_total.setBold(True)
        self.lbl_total_texto.setFont(font_total)

        self.lbl_total_valor = QLabel("$ 0.00")
        self.lbl_total_valor.setFont(font_total)
        self.lbl_total_valor.setStyleSheet("font-size: 45px; font-weight: bold; color: #00ff00; background-color: #1e1e1e; padding: 10px; border-radius: 5px;")

        self.btn_cobrar = QPushButton("COBRAR FACTURA (F12)")
        self.btn_cobrar.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; font-size: 20px; padding: 15px;")
        self.btn_cobrar.setMinimumWidth(250)
        self.btn_cobrar.setEnabled(False)

        self.box_inferior.addWidget(self.btn_descuento)
        self.box_inferior.addWidget(self.btn_buscar_presupuesto)
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
        # --- CONEXIONES ---
        # # self.txt_codigo.returnPressed.connect(self.agregar_al_carrito) # Disabled
        self.btn_buscar.clicked.connect(self.agregar_al_carrito)

        # Shortcut para el boton agregar carrito con el enter
        self.shortcut_enter = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        self.shortcut_enter.activated.connect(self.on_enter_pressed)
        self.shortcut_enter2 = QShortcut(QKeySequence(Qt.Key.Key_Enter), self)
        self.shortcut_enter2.activated.connect(self.on_enter_pressed)


        # Shortcut para el boton agregar carrito con el enter
        self.tabla.itemChanged.connect(self.modificar_cantidad_grid)
        self.btn_cobrar.clicked.connect(self.procesar_cobro)
        self.combo_clientes.currentIndexChanged.connect(self.evaluar_cliente)
        self.btn_descuento.clicked.connect(self.aplicar_descuento_global)
        self.btn_consulta_rapida.clicked.connect(self.consultar_precio_rapido)
        self.btn_sugerir_pedido.clicked.connect(self.sugerir_pedido)
        self.btn_nuevo_cliente.clicked.connect(self.crear_cliente_rapido)
        self.btn_cobrar_cc.clicked.connect(self.abrir_cobro_cc)
        self.btn_buscar_presupuesto.clicked.connect(self._abrir_recuperar_dialog)

        # --- ATAJOS DE TECLADO ---
        shortcut_f12 = QShortcut(QKeySequence("F12"), self)
        shortcut_f12.activated.connect(self.procesar_cobro)

        shortcut_f2 = QShortcut(QKeySequence("F2"), self)
        shortcut_f2.activated.connect(self.consultar_precio_rapido)

        self.cargar_clientes()






    def on_enter_pressed(self):
        # Si el foco esta en el textbox del codigo, IGNORAR (para que el escaner no dispare auto)
        if self.txt_codigo.hasFocus():
            # Mover el foco a la cantidad en su lugar
            self.txt_cantidad.setFocus()
            self.txt_cantidad.selectAll()
        else:
            # En cualquier otro lado, ejecutar agregar_al_carrito
            self.btn_buscar.click()

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
        prods = ProductoService.listar_nombres()
        model = QStringListModel(prods)
        self.completer_prod.setModel(model)

    def crear_cliente_rapido(self):
        dialog = FastClientDialog(self)
        if dialog.exec():
            self.cargar_clientes()
            if dialog.nuevo_cliente_id:
                index = self.combo_clientes.findData(dialog.nuevo_cliente_id)
                if index >= 0:
                    self.combo_clientes.setCurrentIndex(index)

    def consultar_precio_rapido(self):
        query, ok = QInputDialog.getText(self, "Consultar Precio (F2)", "Ingrese nombre o código de barras:")
        if ok and query.strip():
            prod = ProductoService.buscar_por_query_flexible(query.strip())
            if prod:
                from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel
                dialog = QDialog(self)
                dialog.setWindowTitle("Consulta de Precio Público")
                dialog.resize(500, 300)
                lay = QVBoxLayout(dialog)

                lbl_nom = QLabel(prod.nombre)
                lbl_nom.setWordWrap(True)
                lbl_nom.setStyleSheet("font-size: 24px; font-weight: bold;")
                lbl_nom.setAlignment(Qt.AlignmentFlag.AlignCenter)

                pf = prod.precio_minorista
                if prod.es_granel and prod.divisor_granel > 0:
                    pf = pf / prod.divisor_granel

                lbl_pf = QLabel(f"$ {pf:.2f}")
                lbl_pf.setStyleSheet("font-size: 60px; font-weight: bold; color: #2ecc71;")
                lbl_pf.setAlignment(Qt.AlignmentFlag.AlignCenter)

                # Cálculo de margen neto (Camuflado)
                margen_neto = pf - prod.costo

                lbl_detalles = QLabel(f"<b>Stock Actual:</b> {prod.stock_actual:.2f} &nbsp;&nbsp;|&nbsp;&nbsp; {margen_neto:.2f}")
                lbl_detalles.setStyleSheet("font-size: 18px;")
                lbl_detalles.setAlignment(Qt.AlignmentFlag.AlignCenter)

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

    def abrir_cobro_cc(self):
        cliente_id = self.combo_clientes.currentData()
        if not cliente_id:
            QMessageBox.warning(self, "Atención", "Debe seleccionar un cliente primero.")
            return

        saldo_deuda = ClienteService.obtener_deuda(cliente_id)
        if saldo_deuda <= 0:
            QMessageBox.information(self, "Cuenta Corriente", "El cliente no registra deuda actual.")
            return

        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QPushButton, QHBoxLayout
        dialog = QDialog(self)
        dialog.setWindowTitle("Cobro Cuenta Corriente")
        dialog.resize(350, 200)

        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        lbl_deuda = QLabel(f"$ {saldo_deuda:.2f}")
        lbl_deuda.setStyleSheet("font-weight: bold; color: red; font-size: 16px;")

        txt_monto = QLineEdit()
        txt_monto.setText(f"{saldo_deuda:.2f}")

        combo_metodo = QComboBox()
        combo_metodo.addItems(["Efectivo", "Transferencia", "Tarjeta"])

        form.addRow("Deuda Total Actual:", lbl_deuda)
        form.addRow("Monto a Pagar ($):", txt_monto)
        form.addRow("Método de Pago:", combo_metodo)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Registrar Cobro")
        btn_cancel = QPushButton("Cancelar")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        btn_ok.clicked.connect(dialog.accept)
        btn_cancel.clicked.connect(dialog.reject)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                monto = float(txt_monto.text().replace(',', '.'))
                if monto <= 0 or monto > saldo_deuda:
                    QMessageBox.warning(self, "Error", "Monto inválido.")
                    return

                ClienteService.registrar_pago_cc(cliente_id, monto, combo_metodo.currentText()) # El servicio ya lo inyecta en Caja si está abierta
                QMessageBox.information(self, "Éxito", f"Se registró el pago por $ {monto:.2f}.")
            except ValueError:
                QMessageBox.warning(self, "Error", "Debe ingresar un número válido.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo registrar el pago: {e}")

    def toggle_fecha_acreditacion(self, text):
        is_tarjeta = text in ['Tarjeta', 'Débito']
        if hasattr(self, 'widget_tarjeta'):
            self.widget_tarjeta.setVisible(is_tarjeta)

        # Trigger UI update to recalculate surcharge
        self.actualizar_ui()

    def cargar_clientes(self):
        clientes = ClienteService.listar_todos()
        self.combo_clientes.clear()
        self.combo_clientes.addItem("Consumidor Final", None)
        # Guardar dict interno para acceso rápido a es_especial
        self._cache_clientes = {}
        nombres = []
        for c in clientes:
            self._cache_clientes[c.id] = c.es_especial
            self.combo_clientes.addItem(f"{c.nombre} {'(VIP)' if c.es_especial else ''}", c.id)
            nombres.append(c.nombre)

        model = QStringListModel(["Consumidor Final"] + nombres)
        self.completer_cli.setModel(model)


    def evaluar_cliente(self):
        cliente_id = self.combo_clientes.currentData()
        self.cliente_vip = self._cache_clientes.get(cliente_id, False) if cliente_id else False
        self.actualizar_ui()


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

        prod = ProductoService.buscar_por_query_flexible(query)

        if not prod:
            QMessageBox.warning(self, "No Encontrado", f"No se encontró un producto coincidente con: {query}")
            self.txt_codigo.selectAll()
            self.txt_codigo.setFocus()
            return

        # Advertencia Stock y Disparador Automático de Pedido
        if prod.stock_actual <= 0:
            QMessageBox.warning(self, "Stock Agotado", f"El producto '{prod.nombre}' tiene stock <= 0. La venta continuará en negativo.")
            try:
                ProductoService.agregar_pedido_manual(f"Vendido sin stock - Reposición Urgente: {prod.nombre} (Cod: {prod.codigo_barras or prod.sku})")
            except Exception as e:
                print(f"Error generando pedido automático: {e}")

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
            marca_mostrar = prod.marca.nombre if prod.marca else ""
            self.carrito.append({
                'id': prod.id,
                'codigo': prod.codigo_barras or prod.sku or "N/A",
                'marca': marca_mostrar,
                'nombre': nombre_mostrar,
                'precio_base': precio_base_calculado,
                'cantidad': cant_input,
                'descuento_unit': 0.0
            })

        self.actualizar_ui()
        self.txt_codigo.clear()
        self.txt_cantidad.setText("1")
        self.txt_codigo.setFocus()

    def agregar_item_manual(self):
        dialog = ItemManualDialog(self)
        if dialog.exec() and dialog.data_item:
            self.carrito.append(dialog.data_item)
            self.actualizar_ui()


    def cargar_tarjetas(self):
        from database.conexion import get_session
        from database.models import ConfiguracionTarjeta

        self.combo_tarjeta.clear()
        self.combo_tarjeta.blockSignals(True)
        try:
            with get_session() as session:
                bancos = session.query(ConfiguracionTarjeta.banco_tarjeta).distinct().all()
                if not bancos:
                    self.combo_tarjeta.addItem("Sin Configurar", None)
                else:
                    for b in bancos:
                        self.combo_tarjeta.addItem(b[0], b[0])
        except Exception:
            pass
        finally:
            self.combo_tarjeta.blockSignals(False)
            self.cargar_tarjetas()

    def cargar_planes_tarjeta(self):
        from database.conexion import get_session
        from database.models import ConfiguracionTarjeta

        self.combo_plan_tarjeta.clear()
        self.combo_plan_tarjeta.blockSignals(True)
        self.planes_data = {}

        tarjeta_sel = self.combo_tarjeta.currentData()
        if not tarjeta_sel:
            self.combo_plan_tarjeta.addItem("Sin Configurar", None)
            self.combo_plan_tarjeta.blockSignals(False)
            self.actualizar_ui()
            return

        try:
            with get_session() as session:
                planes = session.query(ConfiguracionTarjeta).where(ConfiguracionTarjeta.banco_tarjeta == tarjeta_sel).all()
                if not planes:
                    self.combo_plan_tarjeta.addItem("Sin Configurar", None)
                else:
                    for p in planes:
                        # We just store the ID for now, the actual text will be formatted in actualizar_ui
                        self.combo_plan_tarjeta.addItem(f"{p.cuotas} Cuotas", p.id)
                        self.planes_data[p.id] = {
                            'banco': p.banco_tarjeta,
                            'cuotas': p.cuotas,
                            'interes': p.porcentaje_interes,
                            'dias': p.dias_acreditacion
                        }
        except Exception:
            pass
        finally:
            self.combo_plan_tarjeta.blockSignals(False)
            self.actualizar_ui()

    def actualizar_ui(self):
        # Desconectar temporalmente
        self.tabla.itemChanged.disconnect(self.modificar_cantidad_grid)

        self.tabla.setRowCount(len(self.carrito))
        subtotal_general = 0.0

        # Logica Cliente Especial desde Base de Datos
        cliente_id = self.combo_clientes.currentData()
        for r, item in enumerate(self.carrito):
            precio_unitario = item['precio_base'] * 0.9 if self.cliente_vip else item['precio_base']
            precio_neto = precio_unitario - item['descuento_unit']
            if precio_neto < 0: precio_neto = 0.0

            subtotal = item['cantidad'] * precio_neto
            subtotal_general += subtotal

            i_id = QTableWidgetItem(str(item['id']) if item['id'] else "-")
            i_id.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            i_cod = QTableWidgetItem(item['codigo'])
            i_cod.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            i_marca = QTableWidgetItem(item['marca'])
            i_marca.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            i_nom = QTableWidgetItem(item['nombre'])
            i_nom.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            i_pre = QTableWidgetItem(f"$ {precio_unitario:.2f}")
            i_pre.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            if self.cliente_vip:
                i_pre.setBackground(QBrush(QColor(241, 196, 15, 60))) # Amarillo para desc

            i_can = QTableWidgetItem(f"{item['cantidad']:.2f}")

            # Descuento unitario (Editable)
            i_desc = QTableWidgetItem(f"{item['descuento_unit']:.2f}")

            i_sub = QTableWidgetItem(f"$ {subtotal:.2f}")
            i_sub.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            self.tabla.setItem(r, 0, i_id)
            self.tabla.setItem(r, 1, i_cod)
            self.tabla.setItem(r, 2, i_marca)
            self.tabla.setItem(r, 3, i_nom)
            self.tabla.setItem(r, 4, i_pre)
            self.tabla.setItem(r, 5, i_can)
            self.tabla.setItem(r, 6, i_desc)
            self.tabla.setItem(r, 7, i_sub)

        total_final = subtotal_general - self.descuento_global
        if total_final < 0: total_final = 0.0

        # Apply Credit Card Interest
        if hasattr(self, 'spin_interes') and self.widget_tarjeta.isVisible():
            tasa = self.spin_interes.value()
            if tasa > 0:
                total_final = total_final * (1 + (tasa / 100))

        self.lbl_total_valor.setText(f"$ {total_final:.2f}")
        self.btn_cobrar.setEnabled(len(self.carrito) > 0)

        self.tabla.itemChanged.connect(self.modificar_cantidad_grid)

    def modificar_cantidad_grid(self, item):
        col = item.column()
        row = item.row()

        if col == 5: # Cantidad
            try:
                nueva_cant = float(item.text().replace(',', '.'))
                if nueva_cant <= 0:
                    self.carrito.pop(row)
                else:
                    self.carrito[row]['cantidad'] = nueva_cant
                self.actualizar_ui()
            except ValueError:
                self.actualizar_ui()

        elif col == 6: # Descuento Unitario
            try:
                nuevo_desc = float(item.text().replace(',', '.'))
                if nuevo_desc < 0: nuevo_desc = 0.0
                self.carrito[row]['descuento_unit'] = nuevo_desc
                self.actualizar_ui()
            except ValueError:
                self.actualizar_ui()





    def _actualizar_estado_boton_cobrar(self, text):
        if text == "Presupuesto":
            self.btn_cobrar.setText("CERRAR PRESUPUESTO")
            self.btn_cobrar.setStyleSheet("background-color: #f39c12; color: white; font-size: 20px; font-weight: bold; padding: 15px;")
        else:
            self.btn_cobrar.setText(f"COBRAR {text.upper()}")
            self.btn_cobrar.setStyleSheet("background-color: #27ae60; color: white; font-size: 20px; font-weight: bold; padding: 15px;")

    def _abrir_recuperar_dialog(self):
        from ui.components.recuperar_dialog import RecuperarComprobanteDialog
        dlg = RecuperarComprobanteDialog(self)
        if dlg.exec():
            if dlg.detalles_recuperados:
                self.carrito = [] # Vaciar el carrito
                for item in dlg.detalles_recuperados:
                    self.carrito.append({
                        'id': item.get('id', item.get('producto_id')),
                        'codigo': item.get('codigo', ''),
                        'marca': item.get('marca', ''), # <-- FIX KEYERROR
                        'nombre': item.get('nombre', ''),
                        'precio_base': item.get('precio_base', 0.0),
                        'cantidad': item.get('cantidad', 1.0),
                        'descuento_unit': item.get('descuento_unit', 0.0)
                    })

                self.presupuesto_activo_id = getattr(dlg, 'presupuesto_origen_id', None)
                # Retrieve client ID if possible
                cliente_id = dlg.cliente_id_seleccionado
                if cliente_id:
                    idx = self.combo_clientes.findData(cliente_id)
                    if idx >= 0:
                        self.combo_clientes.setCurrentIndex(idx)

                self.actualizar_ui()

    def procesar_cobro(self):

        if not self.carrito: return

        # Parse total final
        total_txt = self.lbl_total_valor.text().replace('$ ', '').replace(',', '.')
        total_float = float(total_txt)

        metodo_pago_texto = self.combo_pago.currentText().strip()
        metodo = metodo_pago_texto
        tipo_comprobante = self.combo_comprobante.currentText()
        cliente_id = self.combo_clientes.currentData()

        # Validar si es Cta Cte
        if metodo == "Cuenta Corriente" and not cliente_id:
            QMessageBox.warning(self, "Error", "Debe seleccionar un Cliente válido para pagos en Cuenta Corriente.")
            return

        datos_cheque_extra = None
        if metodo_pago_texto.lower() == "cheque":
            from ui.components.dialogs import CargarChequeDialog
            from PyQt6.QtWidgets import QDialog
            dialog_cheque = CargarChequeDialog(total_float, self)
            if dialog_cheque.exec() == QDialog.DialogCode.Accepted:
                datos_cheque_extra = dialog_cheque.get_data()
            else:
                return # Aborta la venta si el cajero cancela la carga del cheque

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
                detalles_final = []
                for item in self.carrito:
                    precio_unitario = item['precio_base'] * 0.9 if self.cliente_vip else item['precio_base']
                    subtotal = (precio_unitario - item['descuento_unit']) * item['cantidad']
                    detalles_final.append({
                        'producto_id': item['id'],
                        'nombre': item.get('nombre', 'Item'),
                        'cantidad': item['cantidad'],
                        'precio_unitario': precio_unitario,
                        'descuento_unitario': item['descuento_unit'],
                        'subtotal': subtotal
                    })

                # Pass extra data for deferred income
                datos_tarjeta = None
                if metodo in ['Tarjeta', 'Débito']:
                    lote = self.txt_lote.text().strip()
                    cupon = self.txt_cupon.text().strip()

                    if not lote or not cupon:
                        QMessageBox.warning(self, "Error", "El número de Lote y Cupón son obligatorios para pagos con Tarjeta.")
                        return

                    plan_id = self.combo_plan_tarjeta.currentData()
                    if plan_id and hasattr(self, 'planes_data') and plan_id in self.planes_data:
                        p = self.planes_data[plan_id]
                        datos_tarjeta = {
                            'banco': p['banco'],
                            'cuotas': p['cuotas'],
                            'interes': p['interes'],
                            'plazo_dias': p['dias'],
                            'lote': lote,
                            'cupon': cupon
                        }
                    else:
                        QMessageBox.warning(self, "Error", "Seleccione un plan de tarjeta válido.")
                        return

                if tipo_comprobante == "Presupuesto":
                    from services.presupuesto_service import PresupuestoService
                    venta = PresupuestoService.guardar_presupuesto(
                        detalles_final,
                        cliente_id=cliente_id,
                        descuento_global=self.descuento_global
                    )
                    venta.tipo_comprobante = "Presupuesto" # For ticket dialog compat
                    venta.metodo_pago = "N/A"
                    venta.vuelto = 0.0
                else:
                    venta = VentaService.procesar_venta(
                        detalles_final,
                        cliente_id=cliente_id,
                        metodo_pago=metodo,
                        monto_abonado=monto_abonado,
                        descuento_global=self.descuento_global,
                        tipo_comprobante=tipo_comprobante,
                        datos_tarjeta=datos_tarjeta,
                        presupuesto_id=getattr(self, 'presupuesto_activo_id', None),
                        datos_cheque=datos_cheque_extra
                    )

                vuelto = venta.vuelto
                msg = f"Venta Registrada Exitosamente (ID: {venta.id})"
                if vuelto > 0: msg += f"\n\nVuelto a entregar: $ {vuelto:.2f}"


                QMessageBox.information(self, "Éxito", msg)

                # Check for ticket print
                reply_print = QMessageBox.question(
                    self, "Imprimir Ticket",
                    "¿Desea imprimir el ticket de esta venta?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply_print == QMessageBox.StandardButton.Yes:
                    cliente_seleccionado = self.combo_clientes.currentText()
                    if not cliente_seleccionado or "Consumidor Final" in cliente_seleccionado:
                        cliente_seleccionado = "Consumidor Final"
                    dlg = TicketPreviewDialog(venta, detalles_final, cliente_seleccionado, self)
                    dlg.exec()


                # Reset
                self.carrito = []
                self.descuento_global = 0.0
                self.cliente_vip = False
                self.presupuesto_activo_id = None
                self.txt_codigo.clear()
                if hasattr(self, 'txt_lote'): self.txt_lote.clear()
                if hasattr(self, 'txt_cupon'): self.txt_cupon.clear()
                self.combo_clientes.setCurrentIndex(0)
                self.actualizar_ui()
                self.txt_codigo.setFocus()

            except Exception as e:
                QMessageBox.critical(self, "Error de Sistema", f"No se pudo guardar la venta:\n{str(e)}")
