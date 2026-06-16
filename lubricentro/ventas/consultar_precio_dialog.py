# -*- coding: utf-8 -*-
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QLabel,
    QPushButton, QCompleter
)

from db import SessionLocal, Producto

def _fmt(n):
    try:
        return f"${float(n):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "$0,00"

# -----------------------------
# ConsultarPrecioDialog
# -----------------------------
class ConsultarPrecioDialog(QDialog):
    def __init__(self, parent=None, token_inicial: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Consultar Precio")
        self.resize(480, 260)

        self.selected_data = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.inp_buscar = QLineEdit(token_inicial or "")
        self.inp_buscar.setPlaceholderText("ID / código / código de barras / nombre")
        # Agregar autocompletado para hacerlo "intuitivo"
        self._helper = ProductoSearchHelper(self.inp_buscar)

        # Al presionar Enter, buscar
        self.inp_buscar.returnPressed.connect(self._buscar)

        form.addRow("Producto:", self.inp_buscar)
        layout.addLayout(form)

        self.lbl_nombre = QLabel("")
        self.lbl_nombre.setStyleSheet("font-size:14px; color:#cfd4da;")
        layout.addWidget(self.lbl_nombre)

        self.lbl_final = QLabel("$0,00")
        self.lbl_final.setStyleSheet("font-size:42px; font-weight:800; color:#e8eaed;")
        layout.addWidget(self.lbl_final)

        self.lbl_promo = QLabel("")
        self.lbl_promo.setStyleSheet("font-size:18px; color:#aab0b6;")
        layout.addWidget(self.lbl_promo)

        row = QHBoxLayout()
        btn_buscar = QPushButton("Buscar"); btn_buscar.clicked.connect(self._buscar)
        btn_cerrar = QPushButton("Cerrar"); btn_cerrar.clicked.connect(self.accept)
        row.addStretch(1); row.addWidget(btn_buscar); row.addWidget(btn_cerrar)
        layout.addLayout(row)

        if (token_inicial or "").strip():
            self._buscar()


    def keyPressEvent(self, event):
        from PyQt5.QtCore import Qt
        if event.key() == Qt.Key_Delete:
            if hasattr(self, "inp_buscar"):
                self.inp_buscar.clear()
                self.inp_buscar.setFocus()
        else:
            super().keyPressEvent(event)

    def _buscar(self):
        # Búsquedas y precios (importación tardía para romper ciclo)
        from ventas.precio_busquedas import (
            find_producto_robusto, precio_vigente, precio_final_lista, calcular_parametros
        )

        token = (self.inp_buscar.text() or "").strip()
        # Si se seleccionó del autocompletar, usar el ID
        pid = None
        if hasattr(self, "_helper") and self._helper.current_id:
            pid = self._helper.current_id

        if not token and not pid:
            self.lbl_nombre.setText("Ingresá un producto para buscar")
            self.lbl_final.setText("$0,00"); self.lbl_promo.setText(""); return

        with SessionLocal() as s:
            p = None
            if pid:
                p = s.query(Producto).get(int(pid))

            if not p:
                p = find_producto_robusto(s, token)

            if not p:
                self.lbl_nombre.setText("No encontrado")
                self.lbl_final.setText("$0,00"); self.lbl_promo.setText(""); return

            self.lbl_nombre.setText(getattr(p, "nombre", "") or "")
            params = calcular_parametros(s)
            final_lista = float(precio_final_lista(s, p, params) or 0.0)
            vigente = float(precio_vigente(s, p, params) or 0.0)

            self.selected_data = {
                "id": p.id,
                "nombre": getattr(p, "nombre", "") or "",
                "precio": vigente
            }

            self.lbl_final.setText(_fmt(final_lista))
            if abs(vigente - final_lista) > 1e-9:
                self.lbl_promo.setText(f"Con descuento: {_fmt(vigente)}")
            else:
                self.lbl_promo.setText("")

# -----------------------------
# Autocompletado de productos (para la pestaña de venta)
# -----------------------------
class ProductoSearchHelper:
    def __init__(self, line_edit: QLineEdit):
        self.le = line_edit
        self.completer = QCompleter([], self.le)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        try:
            self.completer.setFilterMode(Qt.MatchContains)
        except Exception:
            pass
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.le.setCompleter(self.completer)

        self._items = []
        self.map_by_display = {}
        self.current_id = None

        self.le.textEdited.connect(self._refresh)
        try:
            self.completer.activated[str].connect(self._on_pick)
        except Exception:
            self.completer.activated.connect(lambda _: self._on_pick(self.le.text()))

    def _on_pick(self, display):
        it = self.map_by_display.get(display)
        if it:
            pid, _disp, nombre = it
            self.current_id = pid
            self.le.setText(nombre)

    def _refresh(self, txt):
        pat = (txt or "").strip()
        self.current_id = None
        if not pat:
            self._apply([])
            return

        code_fields = ("codigo_barras","codigo_barra","barcode","cb","ean",
                       "codigo","codigo_interno","cod","sku","codigo_proveedor")

        with SessionLocal() as s:
            q = s.query(Producto)
            conds = []
            try:
                conds.append(Producto.nombre.ilike(f"%{pat}%"))
            except Exception:
                conds.append(Producto.nombre.contains(pat))
            for fn in code_fields:
                col = getattr(Producto, fn, None)
                if col is not None:
                    try:
                        conds.append(col.ilike(f"%{pat}%"))
                    except Exception:
                        conds.append(col.contains(pat))
            # OR dinámico
            try:
                q = q.filter(conds[0] | conds[1] | conds[2] | conds[3] | conds[4] | conds[5] | conds[6] | conds[7] | conds[8] | conds[9])
            except Exception:
                from sqlalchemy import or_
                q = q.filter(or_(*conds))
            rows = q.order_by(Producto.nombre.asc()).limit(25).all()

        # Importar hook de stock para obtener cantidad
        try:
            from ventas.stock_hooks import _get_stock_ref
        except ImportError:
            def _get_stock_ref(p, session=None): return None, 0.0

        items = []
        for r in rows:
            pid = getattr(r, "id", None)
            nombre = getattr(r, "nombre", "") or ""
            cod = ""
            for fn in ("codigo","codigo_interno","sku","codigo_proveedor","codigo_barras","ean","cb"):
                if hasattr(r, fn):
                    v = getattr(r, fn) or ""
                    if v:
                        cod = str(v); break

            # Obtener stock actual para mostrar
            _, stock_val = _get_stock_ref(r, session=s)
            s_val = float(stock_val or 0.0)
            stock_str = f"Stock: {s_val:g}" # :g quita ceros extra

            disp = f"{nombre} — {cod}  [{stock_str}]" if cod else f"{nombre}  [{stock_str}]"
            items.append((pid, disp, nombre))
        self._apply(items)

    def _apply(self, items):
        self._items = list(items)
        self.map_by_display = {d: (pid, d, nombre) for (pid, d, nombre) in self._items}
        try:
            from PyQt5.QtCore import QStringListModel
            self.completer.setModel(QStringListModel([it[1] for it in self._items], self.completer))
        except Exception:
            pass
