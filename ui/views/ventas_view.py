from ui.components.dialogs import FastClientDialog, ItemManualDialog
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QDateEdit, QLabel, QMessageBox,
    QComboBox, QFormLayout, QGroupBox, QInputDialog, QSplitter, QSpinBox, QDoubleSpinBox
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

        self.btn_nuevo_cliente = QPushButton("+")
        self.btn_nuevo_cliente.setToolTip("Agregar Nuevo Cliente")
        self.btn_nuevo_cliente.setFixedWidth(30)

        box_cli = QHBoxLayout()
        box_cli.addWidget(self.combo_clientes)
        box_cli.addWidget(self.btn_nuevo_cliente)

        self.form_cliente.addRow("Cliente:", box_cli)

        # Eliminar QComboBox de "Tipo", la lectura será directamente del modelo Cliente

        self.form_pago = QFormLayout()
        self.combo_pago = QComboBox()
        self.combo_pago.addItems(["Efectivo", "Transferencia", "Débito", "Tarjeta", "Cuenta Corriente", "Combinada"])

        self.combo_comprobante = QComboBox()
        self.combo_comprobante.addItems(["Remito", "Factura A", "Factura B"])

        self.form_pago.addRow("Comprobante:", self.combo_comprobante)
        self.form_pago.addRow("Método Pago:", self.combo_pago)


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
        self.form_tarjeta.addRow("Plan de Tarjeta:", self.combo_plan_tarjeta)
        self.form_tarjeta.addRow("Nº Lote:", self.txt_lote)
        self.form_tarjeta.addRow("Nº Cupón:", self.txt_cupon)

        # Ocultar por defecto
        self.widget_tarjeta = QWidget()
        self.widget_tarjeta.setLayout(self.form_tarjeta)
        self.widget_tarjeta.setVisible(False)
        self.form_pago.addRow(self.widget_tarjeta)

        self.combo_pago.currentTextChanged.connect(self.toggle_fecha_acreditacion)

        self.box_opciones.addLayout(self.form_cliente)
        self.box_opciones.addLayout(self.form_pago)
        self.box_opciones.addStretch()

        self.btn_consulta_rapida = QPushButton("Consultar Precio (F2)")
        self.btn_consulta_rapida.setStyleSheet("padding: 10px; font-weight: bold; background-color: #f39c12; color: white;")

        self.btn_sugerir_pedido = QPushButton("Anotar Pedido Manual")
        self.btn_sugerir_pedido.setStyleSheet("padding: 10px; font-weight: bold; background-color: #8e44ad; color: white;")

        self.btn_cobrar_cc = QPushButton("Cobrar Cuenta Corriente")
        self.btn_cobrar_cc.setStyleSheet("padding: 10px; font-weight: bold; background-color: #d35400; color: white;")

        self.box_opciones.addWidget(self.btn_cobrar_cc)
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
        # self.txt_codigo.returnPressed.connect(self.agregar_al_carrito) # Desactivado: Evita auto-inserción de scanners
        self.btn_buscar.clicked.connect(self.agregar_al_carrito)
        self.tabla.itemChanged.connect(self.modificar_cantidad_grid)
        self.btn_cobrar.clicked.connect(self.procesar_cobro)
        self.combo_clientes.currentIndexChanged.connect(self.evaluar_cliente)
        self.btn_descuento.clicked.connect(self.aplicar_descuento_global)
        self.btn_consulta_rapida.clicked.connect(self.consultar_precio_rapido)
        self.btn_sugerir_pedido.clicked.connect(self.sugerir_pedido)
        self.btn_nuevo_cliente.clicked.connect(self.crear_cliente_rapido)
        self.btn_cobrar_cc.clicked.connect(self.abrir_cobro_cc)

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
                detalles_final = []
                for item in self.carrito:
                    precio_unitario = item['precio_base'] * 0.9 if self.cliente_vip else item['precio_base']
                    detalles_final.append({
                        'producto_id': item['id'],
                        'nombre': item.get('nombre', 'Item'),
                        'cantidad': item['cantidad'],
                        'precio_unitario': precio_unitario,
                        'descuento_unitario': item['descuento_unit']
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

                venta = VentaService.procesar_venta(
                    detalles_final,
                    cliente_id=cliente_id,
                    metodo_pago=metodo,
                    monto_abonado=monto_abonado,
                    descuento_global=self.descuento_global,
                    tipo_comprobante=tipo_comprobante,
                    datos_tarjeta=datos_tarjeta
                )

                vuelto = venta.vuelto
                msg = f"Venta Registrada Exitosamente (ID: {venta.id})"
                if vuelto > 0: msg += f"\n\nVuelto a entregar: $ {vuelto:.2f}"

                QMessageBox.information(self, "Éxito", msg)

                # Reset
                self.carrito = []
                self.descuento_global = 0.0
                self.cliente_vip = False
                self.txt_codigo.clear()
                if hasattr(self, 'txt_lote'): self.txt_lote.clear()
                if hasattr(self, 'txt_cupon'): self.txt_cupon.clear()
                self.combo_clientes.setCurrentIndex(0)
                self.actualizar_ui()
                self.txt_codigo.setFocus()

            except Exception as e:
                QMessageBox.critical(self, "Error de Sistema", f"No se pudo guardar la venta:\n{str(e)}")
