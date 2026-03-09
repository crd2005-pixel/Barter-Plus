# -*- coding: utf-8 -*-
"""
ventas/nueva_venta_tab.py
UI de la pestaña, delega TODO en NuevaVentaService.
"""

import os, datetime as dt
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QComboBox, QMessageBox, QTableWidget, QTableWidgetItem, QLabel, QWidget as QW,
    QApplication, QInputDialog
)

from ventas.nueva_venta_service import NuevaVentaService, fmt_money, log_err
from services.solicitud_service import SolicitudService
from db import SessionLocal

try:
    from ventas.nueva_venta_complemento import (
        ClienteDialog, PagosMixtosDialog, SlidePanel, ClienteSearchHelper, ProductoSearchHelper
    )
except Exception:
    ClienteDialog = PagosMixtosDialog = SlidePanel = None
    ClienteSearchHelper = ProductoSearchHelper = None

try:
    from utils.pdf import generar_remito_pdf
except Exception:
    generar_remito_pdf = None


class NuevaVentaTab(QWidget):
    venta_guardada = pyqtSignal(object)
    venta_anulada = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.svc = NuevaVentaService()

        root = QVBoxLayout(self)
        form = QFormLayout()
        self.ed_cliente = QLineEdit()
        self._cli_helper = ClienteSearchHelper(self.ed_cliente) if ClienteSearchHelper else None

        self._temp_selected_price = None
        self._temp_selected_pid = None

        self.cb_tipo_cliente = QComboBox(); self.cb_tipo_cliente.addItems(["Cliente común","Cliente especial (-10%)"])
        self.ed_prod = QLineEdit(); self._prod_helper = ProductoSearchHelper(self.ed_prod) if ProductoSearchHelper else None
        self.ed_cant = QLineEdit("1")

        self.cb_pago = QComboBox()
        self.cb_pago.addItems(["Efectivo","Transferencia","Débito","Tarjeta","Cheque","Cuenta Corriente","Combinada"])

        self.row_tarjeta = QW(); rt = QHBoxLayout(self.row_tarjeta); rt.setContentsMargins(0,0,0,0); rt.setSpacing(8)
        self.cb_tarjeta = QComboBox(); self.cb_tarjeta.addItems(sorted(self.svc.tarj_cfg.keys()))
        self.lbl_cuotas = QLabel("Cuotas:"); self.cb_cuotas = QComboBox(); self.cb_cuotas.addItems([str(x) for x in sorted(self.svc.tarj_cfg.get(self.cb_tarjeta.currentText(),{1:0}).keys())])
        self.lbl_cuota = QLabel("Cuota: $0,00"); self.lbl_total_tarj = QLabel("Total c/recargo: $0,00")
        self.ed_lote = QLineEdit(); self.ed_lote.setPlaceholderText("Lote")
        self.ed_cupon = QLineEdit(); self.ed_cupon.setPlaceholderText("Cupón")
        for w in (QLabel("Tarjeta:"), self.cb_tarjeta, self.lbl_cuotas, self.cb_cuotas,
                  self.lbl_cuota, self.lbl_total_tarj, QLabel("Lote:"), self.ed_lote, QLabel("Cupón:"), self.ed_cupon):
            rt.addWidget(w)
        self.row_tarjeta.hide()

        form.addRow("Cliente:", self.ed_cliente)
        form.addRow("Tipo cliente:", self.cb_tipo_cliente)

        # Row Producto con boton sugerir
        hb_prod = QHBoxLayout()
        hb_prod.addWidget(self.ed_prod)
        btn_sugerir = QPushButton("Sugerir/Pedir"); btn_sugerir.setStyleSheet("background-color:#ffeb3b; color:black; font-weight:bold; padding:2px 8px;")
        btn_sugerir.setToolTip("Sugerir producto faltante o nuevo pedido cliente")
        btn_sugerir.clicked.connect(self._sugerir_pedido)
        hb_prod.addWidget(btn_sugerir)

        form.addRow("Producto:", hb_prod)
        form.addRow("Cantidad:", self.ed_cant)
        form.addRow("Forma de pago:", self.cb_pago)
        form.addRow(self.row_tarjeta)
        root.addLayout(form)

        self.tbl = QTableWidget(0, 5); self.tbl.setHorizontalHeaderLabels(["ID","Descripción","Cantidad","P. Unit","Subtotal"])
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows) # Permitir selección completa de fila
        root.addWidget(self.tbl)

        self.slide = SlidePanel(self) if SlidePanel else QW(self)
        total_line = QHBoxLayout()
        self.lbl_total_txt = QLabel("TOTAL:"); self.lbl_total_val = QLabel("$0,00")
        self.lbl_total_val.setStyleSheet("font-size:26px;color:#0a58ca;background:#e7f1ff;padding:6px 12px;border-radius:6px;")

        self.btn_desc_global = QPushButton("Desc / Redondeo")
        self.btn_desc_global.clicked.connect(self._aplicar_descuento_global)

        total_line.addStretch()
        total_line.addWidget(self.btn_desc_global)
        total_line.addSpacing(10)
        total_line.addWidget(self.lbl_total_txt); total_line.addWidget(self.lbl_total_val)
        root.addLayout(total_line); root.addWidget(self.slide)

        self.lbl_pagos_hdr = QLabel("Pagos combinados (vista previa)")
        self.lbl_pagos_hdr.setStyleSheet("font-size:14px;color:#8ab4f8;")
        self.tbl_pagos = QTableWidget(0, 3); self.tbl_pagos.setHorizontalHeaderLabels(["Medio","Detalle","Monto"])
        self.tbl_pagos.setEditTriggers(QTableWidget.NoEditTriggers); self.tbl_pagos.setSelectionBehavior(QTableWidget.SelectRows)
        self.lbl_pagos_hdr.setVisible(False); self.tbl_pagos.setVisible(False)
        root.addWidget(self.lbl_pagos_hdr); root.addWidget(self.tbl_pagos)

        bar = QHBoxLayout()
        self.btn_consulta = QPushButton("Consultar precio"); self.btn_consulta.clicked.connect(self._consultar_precio)
        self.btn_consulta.setMinimumHeight(52); self.btn_consulta.setStyleSheet("font-size:20px;padding:12px 18px;")
        self.btn_add2 = QPushButton("Agregar producto"); self.btn_add2.clicked.connect(self._add_producto)
        self.btn_newcli2 = QPushButton("Nuevo cliente…"); self.btn_newcli2.clicked.connect(self._nuevo_cliente)
        self.btn_pagos = QPushButton("Pagos…"); self.btn_pagos.clicked.connect(self._pagos); self.btn_pagos.setVisible(False)
        self.btn_finalizar = QPushButton("Finalizar venta"); self.btn_finalizar.clicked.connect(self._finalizar)
        self.btn_anular = QPushButton("Anular venta…"); self.btn_anular.clicked.connect(self._anular_venta_dialogo)
        bar.addWidget(self.btn_consulta, stretch=1); bar.addStretch()
        for b in (self.btn_add2, self.btn_newcli2, self.btn_pagos, self.btn_finalizar, self.btn_anular):
            b.setStyleSheet("font-size:14px;padding:6px 10px;"); bar.addWidget(b)
        root.addLayout(bar)

        # señales
        self.cb_pago.currentTextChanged.connect(self._on_pago_changed)
        self.cb_tarjeta.currentTextChanged.connect(self._on_tarjeta_changed)
        self.cb_cuotas.currentTextChanged.connect(self._sync_total)
        self.cb_tipo_cliente.currentTextChanged.connect(self._sync_total)
        self.ed_prod.returnPressed.connect(self._add_producto)
        self.ed_cant.returnPressed.connect(self._add_producto)

        # Permitir edición de celdas en la tabla (Subtotal)
        self.tbl.itemChanged.connect(self._on_table_item_changed)

        # NUEVO: detectar cliente especial al instante
        try:
            self.ed_cliente.textChanged.connect(self._on_cliente_text_changed)
        except Exception:
            pass

        self._sync_total()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            if self.tbl.hasFocus():
                self._borrar_seleccion()
            else:
                self.ed_prod.clear()
                self.ed_cant.setText("1")
                self.ed_prod.setFocus()
        else:
            super().keyPressEvent(event)

    def _borrar_seleccion(self):
        rows = sorted(set(index.row() for index in self.tbl.selectedIndexes()), reverse=True)
        if not rows:
            return

        resp = QMessageBox.question(self, "Borrar ítem", "¿Quitar los ítems seleccionados?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if resp != QMessageBox.Yes:
            return

        for r in rows:
            self.svc.remove_item(r)
            self.tbl.removeRow(r)

        self._sync_total()

    # ===== helpers =====
    def _cliente_actual_es_especial(self) -> bool:
        # Primero, si el helper tiene ID, usamos ese (más confiable)
        cid = None
        try:
            if self._cli_helper and hasattr(self._cli_helper, "current_id"):
                cid = getattr(self._cli_helper, "current_id", None)
        except Exception:
            cid = None
        cli = self.svc.find_cliente_by_id(cid) if cid else self.svc.find_cliente(self.ed_cliente.text())
        return self.svc.cliente_especial(cli) or self.cb_tipo_cliente.currentText().startswith("Cliente especial")

    def _on_cliente_text_changed(self, _txt):
        # Relee estado de "cliente especial" y ajusta combo sin intervención del usuario
        try:
            es_esp = self._cliente_actual_es_especial()
            self.cb_tipo_cliente.setCurrentIndex(1 if es_esp else 0)
            self._sync_total()
        except Exception:
            pass

    def _push_table(self, pid, nombre, cant, subtotal):
        r = self.tbl.rowCount(); self.tbl.insertRow(r)

        # ID (no editable)
        it_id = QTableWidgetItem(str(pid or ""))
        it_id.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.tbl.setItem(r, 0, it_id)

        # Nombre (no editable)
        it_nom = QTableWidgetItem(nombre)
        it_nom.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.tbl.setItem(r, 1, it_nom)

        # Cantidad (no editable por ahora, simplificado)
        it_cant = QTableWidgetItem(f"{float(cant):.3f}")
        it_cant.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.tbl.setItem(r, 2, it_cant)

        # P. Unit (EDITABLE)
        p_unit = float(subtotal) / float(cant) if float(cant) != 0 else 0.0
        it_unit = QTableWidgetItem(f"{p_unit:.2f}")
        it_unit.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
        self.tbl.setItem(r, 3, it_unit)

        # Subtotal (EDITABLE)
        it_sub = QTableWidgetItem(f"{float(subtotal):.2f}")
        it_sub.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
        self.tbl.setItem(r, 4, it_sub)

        for c in range(5):
            it = self.tbl.item(r, c)
            it.setTextAlignment(Qt.AlignCenter if c != 1 else Qt.AlignLeft | Qt.AlignVCenter)

    def _on_table_item_changed(self, item):
        # Evitar recursión si nosotros mismos cambiamos el texto
        if getattr(self, "_updating_table", False): return

        col = item.column()
        row = item.row()

        # Si cambia P. Unit (col 3) o Subtotal (col 4)
        if col in (3, 4):
            try:
                val_txt = item.text().replace("$","").replace(" ","").replace(",", ".")
                val_float = float(val_txt)

                # Obtener cantidad actual (col 2)
                cant_txt = self.tbl.item(row, 2).text().replace(",", ".")
                cant = float(cant_txt)

                self._updating_table = True

                if col == 3: # Cambio P. Unit -> Actualizar Subtotal
                    new_sub = val_float * cant
                    # Actualizar UI Subtotal
                    self.tbl.item(row, 4).setText(f"{new_sub:.2f}")
                    # Actualizar modelo
                    self.svc.update_item_subtotal(row, new_sub)

                elif col == 4: # Cambio Subtotal -> Actualizar P. Unit
                    new_sub = val_float
                    new_unit = new_sub / cant if cant != 0 else 0.0
                    # Actualizar UI P. Unit
                    self.tbl.item(row, 3).setText(f"{new_unit:.2f}")
                    # Actualizar modelo
                    self.svc.update_item_subtotal(row, new_sub)

                self._sync_total()

            except ValueError:
                pass
            except Exception as e:
                log_err(f"Error editando tabla: {e}")
            finally:
                self._updating_table = False

    def _sync_total(self):
        es_esp = self._cliente_actual_es_especial()
        base = self.svc.total_con_desc(es_esp)
        if self.cb_pago.currentText() == "Tarjeta" and self.row_tarjeta.isVisible():
            marca = self.cb_tarjeta.currentText() or "Visa"
            try: cuotas = int(self.cb_cuotas.currentText() or "1")
            except Exception: cuotas = 1
            total, cuota = self.svc.total_tarjeta(base, marca, cuotas)
            self.lbl_total_tarj.setText(f"Total c/recargo: {fmt_money(total)}")
            self.lbl_cuota.setText(f"Cuota: {fmt_money(cuota)}")
            self.lbl_total_val.setText(fmt_money(total))
        else:
            self.lbl_total_val.setText(fmt_money(base))

    # ===== eventos =====
    def _on_pago_changed(self, text):
        if text == "Tarjeta":
            self.row_tarjeta.show()
            self.cb_tarjeta.clear(); self.cb_tarjeta.addItems(sorted(self.svc.tarj_cfg.keys()))
            self._on_tarjeta_changed()
        elif text == "Débito":
            self.row_tarjeta.show()
            self.cb_tarjeta.clear(); self.cb_tarjeta.addItems(sorted(self.svc.tarj_cfg.keys()))
            self.lbl_cuotas.hide(); self.cb_cuotas.hide()
        elif text == "Combinada":
            self.row_tarjeta.hide(); self._pagos()
        else:
            self.row_tarjeta.hide()
        self._sync_total()

    def _on_tarjeta_changed(self):
        marca = self.cb_tarjeta.currentText()
        self.cb_cuotas.show(); self.lbl_cuotas.show()
        self.cb_cuotas.clear(); self.cb_cuotas.addItems([str(x) for x in sorted(self.svc.tarj_cfg.get(marca, {1:0}).keys())])
        self._sync_total()

    def _consultar_precio(self):
        # Intuitivo: si hay selección en el autocompletar, usar ese nombre; si no, usar lo escrito.
        token = (self.ed_prod.text() or "").strip()
        if self._prod_helper and hasattr(self._prod_helper, "current_id") and getattr(self._prod_helper, "current_id", None):
            try:
                pid = int(self._prod_helper.current_id)
                nombre, _ = self.svc.resolver_producto_por_id(pid)
                if nombre:
                    token = nombre
            except Exception:
                pass
        # Abrir y disparar búsqueda automática (el service intenta múltiples nombres de método)
        res = self.svc.consultar_precio(self, token_inicial=token)
        if res and isinstance(res, dict):
             # res = { "id": int, "nombre": str, "precio": float }
             pid = res.get("id")
             nombre = res.get("nombre")
             if pid and nombre:
                 self.ed_prod.setText(nombre)
                 if self._prod_helper:
                     self._prod_helper.current_id = pid

                 # Guardar precio para usarlo en _add_producto sin re-consultar
                 self._temp_selected_pid = pid
                 self._temp_selected_price = res.get("precio", 0.0)

                 self.ed_prod.selectAll()
                 self.ed_prod.setFocus()

    def _nuevo_cliente(self):
        if not ClienteDialog:
            QMessageBox.information(self, "Cliente", "Diálogo no disponible."); return
        dlg = ClienteDialog(self)
        if dlg.exec_() == dlg.Accepted:
            d = dlg.datos()
            if d: self.ed_cliente.setText(d.get("nombre",""))
        self._sync_total()

    def _add_producto(self):
        try:
            # Prioridad al ID del autocompletar para evitar subtotales $0,00
            pid_sel = None
            if self._prod_helper and hasattr(self._prod_helper, "current_id") and getattr(self._prod_helper, "current_id", None):
                try:
                    pid_sel = int(self._prod_helper.current_id)
                except Exception:
                    pid_sel = None

            if pid_sel:
                nombre, precio_unit = self.svc.resolver_producto_por_id(pid_sel)
                pid = pid_sel
            else:
                token = (self.ed_prod.text() or "").strip()
                if not token:
                    QMessageBox.warning(self, "Producto", "Indique un producto."); return
                pid, nombre, precio_unit = self.svc.resolver_producto_y_precio(token)

            if not nombre:
                QMessageBox.warning(self, "Producto", "No se encontró el producto."); return

            # Usar precio del diálogo si coincide el producto
            if self._temp_selected_pid and pid and int(self._temp_selected_pid) == int(pid):
                if self._temp_selected_price is not None:
                    precio_unit = float(self._temp_selected_price)
            # Limpiar temp
            self._temp_selected_pid = None
            self._temp_selected_price = None

            # --- Detección de Venta a Granel y Foco en Cantidad ---
            # Si el foco está en el campo de producto (Scanner / Enter), y el producto es a granel,
            # no agregamos inmediatamente; pasamos el foco a cantidad para que el usuario ingrese fraccion.
            # Además, necesitamos saber si el producto es granel. Consultamos al service.
            # Corrección: recuperamos también la unidad para decidir si dividir precio o no.
            es_granel, pres_cant, pres_unidad = self.svc.es_producto_granel(pid) if pid else (False, 1.0, "Unidad")

            # Chequeamos si la llamada viene desde el scanner/enter en ed_prod (focus)
            # y si todavía no se editó la cantidad (está en 1 por defecto).
            is_scanner_input = self.ed_prod.hasFocus()

            cant_input = 1.0

            if is_scanner_input:
                if es_granel:
                    # Si es granel, NO agregar todavía. Mover foco a cantidad y seleccionar texto.
                    self.ed_cant.setFocus()
                    self.ed_cant.selectAll()
                    return
                else:
                    # Si NO es granel, pero el usuario pidió confirmar cantidad (Scanner mode).
                    # Abrimos dialog para confirmar cantidad.
                    current_qty = self.ed_cant.text().strip() or "1"
                    qty, ok = QInputDialog.getDouble(self, "Cantidad", f"Ingresar cantidad para:\n{nombre}",
                                                   value=float(current_qty), decimals=2, min=0.01, max=9999)
                    if not ok:
                        return # Cancelado por usuario
                    cant_input = qty
                    self.ed_cant.setText(str(qty))
            else:
                # Flujo normal (botón agregar o Enter en cantidad)
                try:
                    cant_input = float((self.ed_cant.text() or "1").replace(",", "."))
                except Exception:
                    cant_input = 1.0

            # --- Cálculo de Cantidad ---
            if pid:
                # Permitimos float para granel siempre.
                # normalizar_cantidad puede ser restrictivo si no es granel, pero el usuario pidió soporte decimal.
                # Asumimos que normalizar_cantidad soporta floats.
                # Si es granel, la cantidad ingresada (ej 0.5) es la cantidad a vender.
                # Usamos la cantidad ya resuelta arriba
                cant_norm, _u = self.svc.normalizar_cantidad(pid, str(cant_input))
            else:
                cant_norm = cant_input

            if cant_norm <= 0:
                QMessageBox.warning(self, "Producto", "La cantidad debe ser mayor a 0."); return

            # --- Ajuste de Precio para Granel ---
            # El precio_unit que viene es por la unidad de presentación (ej. tambor 200L).
            # Solo dividimos si la unidad NO es "Unidad" (ej: "Litros", "L", etc)
            # Y si es granel.

            precio_final_unitario = precio_unit

            # Si es granel, el precio ya viene normalizado por unidad desde el service/bridge.
            # No dividimos de nuevo.
            precio_final_unitario = precio_unit

            self.svc.add_item(pid, nombre, cant_norm, precio_final_unitario)
            self._push_table(pid, nombre, cant_norm, cant_norm * precio_final_unitario)

            # Limpiar entrada y también el ID del helper para la próxima
            self.ed_prod.clear(); self.ed_cant.setText("1")
            try:
                if self._prod_helper and hasattr(self._prod_helper, "current_id"):
                    self._prod_helper.current_id = None
            except Exception:
                pass

            # Volver foco a producto para seguir escaneando
            self.ed_prod.setFocus()

            self._sync_total()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar producto:\n{e}")
            log_err("Error cargando producto: " + str(e))

    def _pagos(self):
        if not self.svc.items:
            QMessageBox.information(self, "Pagos", "Cargá ítems primero."); return
        base = self.svc.total_con_desc(self._cliente_actual_es_especial())
        from ventas.nueva_venta_complemento import PagosMixtosDialog
        dlg = PagosMixtosDialog(self, total_actual=base)
        if dlg.exec_() == dlg.Accepted:
            out = getattr(dlg, "out_data", None)
            if out is None and hasattr(dlg, "result_data"):
                out = dlg.result_data()
            pagos = []
            for p in (out or []):
                try:
                    if isinstance(p, (list, tuple)):
                        medio, monto = str(p[0]), float(p[1] or 0.0); det = p[2] if len(p) > 2 else ""
                    else:
                        medio, monto = str(p.get("medio","")), float(p.get("monto",0) or 0.0); det = p.get("detalle","")
                    pagos.append((medio, monto, det))
                except Exception:
                    continue
            self.svc.set_pagos(pagos)
            self.tbl_pagos.setRowCount(0)
            for medio, monto, det in pagos:
                r = self.tbl_pagos.rowCount(); self.tbl_pagos.insertRow(r)
                self.tbl_pagos.setItem(r,0,QTableWidgetItem(medio))
                self.tbl_pagos.setItem(r,1,QTableWidgetItem(det))
                self.tbl_pagos.setItem(r,2,QTableWidgetItem(f"{float(monto):.2f}"))
            self.lbl_pagos_hdr.setVisible(bool(pagos)); self.tbl_pagos.setVisible(bool(pagos))

    def _finalizar(self):
        try:
            es_esp = self._cliente_actual_es_especial()
            forma = self.cb_pago.currentText()
            tinfo = {"marca": self.cb_tarjeta.currentText(), "cuotas": int(self.cb_cuotas.currentText() or "1"),
                     "lote": self.ed_lote.text(), "cupon": self.ed_cupon.text()}

            # Pasar descuento si existe
            payload = self.svc.guardar_venta(self.ed_cliente.text(), es_esp, forma, tinfo if forma in ("Tarjeta","Débito") else {})
        except Exception as e:
            QMessageBox.critical(self, "Venta", f"No se pudo guardar la venta.\n{e}")
            log_err("Guardar venta error: " + str(e)); return

        # Remito
        try:
            out = None
            if generar_remito_pdf is not None:
                datos = {
                    "venta_id": payload["venta_id"],
                    "fecha": payload["fecha"],
                    "cliente_nombre": payload["cliente"],
                    "comprobante": payload["comprobante"],
                    "items": payload["items_planos"],
                    "pagos": payload["pagos_doc"],
                    "total": payload["total"]
                }
                ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
                os.makedirs("Exports/Remitos", exist_ok=True)
                dest = os.path.join("Exports/Remitos", f"remito_{payload['venta_id']}_{ts}.pdf")
                generar_remito_pdf(datos, dest)
                out = dest
        except Exception:
            out = None

        if out:
            QMessageBox.information(self, "Venta", f"Venta registrada.\nSe generó: {out}\nTotal {fmt_money(payload['total'])}")
        else:
            QMessageBox.information(self, "Venta", f"Venta registrada.\nTotal {fmt_money(payload['total'])}")

        try: self.venta_guardada.emit(payload)
        except Exception: pass

        self.tbl.setRowCount(0); self.svc.clear_items()
        self.lbl_pagos_hdr.setVisible(False); self.tbl_pagos.setVisible(False); self.tbl_pagos.setRowCount(0)
        self.ed_prod.clear(); self.ed_cant.setText("1"); self._sync_total()

    def _anular_venta_dialogo(self):
        txt, ok = QInputDialog.getText(self, "Anular venta", "Ingrese ID o Número de Comprobante:")
        if not ok or not str(txt).strip():
            return

        # Buscar venta
        data = self.svc.buscar_venta_flexible(str(txt))
        if not data:
            QMessageBox.warning(self, "Anulación", "No se encontró la venta.")
            return

        # Confirmar
        msg = (f"¿Anular esta venta?\n\n"
               f"Comprobante: {data['comprobante']}\n"
               f"Fecha: {data['fecha']}\n"
               f"Cliente: {data['cliente']}\n"
               f"Total: {fmt_money(data['total'])}\n"
               f"Estado actual: {data['estado']}")

        resp = QMessageBox.question(self, "Confirmar anulación", msg, QMessageBox.Yes | QMessageBox.No)
        if resp != QMessageBox.Yes:
            return

        if data['estado'] == "ANULADA":
            QMessageBox.information(self, "Anulación", "Esta venta ya está anulada.")
            return

        # Proceder
        try:
            self.svc.anular_venta(data['id'])
            try: self.venta_anulada.emit({"venta_id": data['id']})
            except Exception: pass
            QMessageBox.information(self, "Anulación", f"Venta {data['comprobante']} anulada y stock repuesto.")
        except Exception as e:
            QMessageBox.critical(self, "Anulación", f"No se pudo anular.\n{e}")
            log_err("Anular venta error: " + str(e))

    def _sugerir_pedido(self):
        # 1. Obtener texto (si hay algo escrito en producto, usalo como default)
        default_txt = self.ed_prod.text()
        text, ok = QInputDialog.getText(self, "Sugerir Pedido", "Producto solicitado (puede ser nuevo):", text=default_txt)
        if not ok or not text.strip():
            return

        # 2. Cliente actual (si hay)
        cid = None
        try:
            if self._cli_helper and hasattr(self._cli_helper, "current_id") and getattr(self._cli_helper, "current_id", None):
                cid = int(self._cli_helper.current_id)
        except: pass

        # 3. Guardar
        try:
            with SessionLocal() as session:
                SolicitudService.crear_solicitud(session, text, cid)
            QMessageBox.information(self, "Sugerencia", "Pedido sugerido registrado correctamente.")
            self.ed_prod.clear()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo registrar: {e}")

    def _aplicar_descuento_global(self):
        # Dialogo para pedir monto o nuevo total
        # Opcion A: Pedir Descuento. Opcion B: Pedir Nuevo Total.
        # Mejor: Pedir Descuento directo.

        current_total = self.svc.total_con_desc(self._cliente_actual_es_especial())
        if current_total <= 0:
            QMessageBox.warning(self, "Descuento", "No hay monto para aplicar descuento.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Aplicar Descuento / Redondeo")
        lay = QFormLayout(dlg)

        lbl_info = QLabel(f"Total actual: {fmt_money(current_total)}")
        lay.addRow(lbl_info)

        inp_desc = QLineEdit()
        inp_desc.setPlaceholderText("Monto a descontar (ej: 50.50)")
        lay.addRow("Descuento ($):", inp_desc)

        inp_obs = QLineEdit()
        inp_obs.setPlaceholderText("Motivo (ej: Redondeo, Atención)")
        lay.addRow("Motivo:", inp_obs)

        btn_ok = QPushButton("Aplicar")
        btn_ok.clicked.connect(dlg.accept)
        lay.addRow(btn_ok)

        if dlg.exec_() == QDialog.Accepted:
            try:
                monto = float(inp_desc.text().replace(",", "."))
                obs = inp_obs.text().strip() or "Descuento manual"

                if monto < 0:
                    QMessageBox.warning(self, "Error", "El descuento no puede ser negativo.")
                    return
                if monto > current_total:
                    QMessageBox.warning(self, "Error", "El descuento no puede superar el total.")
                    return

                self.svc.set_descuento_global(monto, obs)
                self._sync_total()

            except Exception:
                QMessageBox.warning(self, "Error", "Monto inválido")
