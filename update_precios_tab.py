import re

with open("lubricentro_2_2/lubricentro/productos/precios_tab.py", "r", encoding="utf-8") as f:
    content = f.read()

import_pattern = r'from PyQt5\.QtWidgets import \((.*?)\)'
new_imports = '    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox,\n    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,\n    QDialog, QDialogButtonBox, QMessageBox, QMenu, QInputDialog,\n    QComboBox, QCheckBox\n'
content = re.sub(import_pattern, f'from PyQt5.QtWidgets import (\n{new_imports})', content, flags=re.DOTALL)


setup_ui_pattern = r'(        top\.addStretch\(1\)\n        lay\.addLayout\(top\))'
new_setup_ui = r'''\1

        # Filtros
        self.lay_filtros = QHBoxLayout()
        self.cmb_marca = QComboBox()
        self.cmb_rubro = QComboBox()
        self.cmb_subrubro = QComboBox()
        self.chk_recientes = QCheckBox("Agregados hoy")

        self.lay_filtros.addWidget(QLabel("Marca:"))
        self.lay_filtros.addWidget(self.cmb_marca)
        self.lay_filtros.addWidget(QLabel("Rubro:"))
        self.lay_filtros.addWidget(self.cmb_rubro)
        self.lay_filtros.addWidget(QLabel("Subrubro:"))
        self.lay_filtros.addWidget(self.cmb_subrubro)
        self.lay_filtros.addWidget(self.chk_recientes)
        self.lay_filtros.addStretch()

        lay.addLayout(self.lay_filtros)

        self.cmb_marca.currentIndexChanged.connect(self._aplicar_filtros)
        self.cmb_rubro.currentIndexChanged.connect(self._aplicar_filtros)
        self.cmb_subrubro.currentIndexChanged.connect(self._aplicar_filtros)
        self.chk_recientes.stateChanged.connect(self._aplicar_filtros)
'''
content = re.sub(setup_ui_pattern, new_setup_ui, content)


load_products_pattern = r'(                "presentacion_cantidad": float\(getattr\(p, "presentacion_cantidad", 1\.0\) or 1\.0\),)'
new_load_products = r'''\1
                "rubro": str(getattr(p, "rubro", "") or ""),
                "subrubro": str(getattr(p, "subrubro", "") or ""),
                "creado_en": getattr(p, "creado_en", None),
'''
content = re.sub(load_products_pattern, new_load_products, content)


render_table_pattern = r'(        self\.tbl\.itemChanged\.connect\(self\._on_item_changed\))'
new_render_table = r'''\1
        self._actualizar_combos_filtro()
'''
content = re.sub(render_table_pattern, new_render_table, content)

import datetime
methods_pattern = r'(    def _on_item_changed\(self, item\):)'
new_methods = r'''
    def _actualizar_combos_filtro(self):
        m_marca = self.cmb_marca.currentText()
        m_rubro = self.cmb_rubro.currentText()
        m_subrubro = self.cmb_subrubro.currentText()

        self.cmb_marca.blockSignals(True)
        self.cmb_rubro.blockSignals(True)
        self.cmb_subrubro.blockSignals(True)

        self.cmb_marca.clear()
        self.cmb_rubro.clear()
        self.cmb_subrubro.clear()

        marcas = sorted(list(set([r["marca"] for r in self._rows if r.get("marca")])))
        rubros = sorted(list(set([r.get("rubro", "") for r in self._rows if r.get("rubro")])))
        subrubros = sorted(list(set([r.get("subrubro", "") for r in self._rows if r.get("subrubro")])))

        self.cmb_marca.addItem("Todas")
        self.cmb_marca.addItems(marcas)
        self.cmb_rubro.addItem("Todos")
        self.cmb_rubro.addItems(rubros)
        self.cmb_subrubro.addItem("Todos")
        self.cmb_subrubro.addItems(subrubros)

        idx = self.cmb_marca.findText(m_marca)
        if idx >= 0: self.cmb_marca.setCurrentIndex(idx)
        idx = self.cmb_rubro.findText(m_rubro)
        if idx >= 0: self.cmb_rubro.setCurrentIndex(idx)
        idx = self.cmb_subrubro.findText(m_subrubro)
        if idx >= 0: self.cmb_subrubro.setCurrentIndex(idx)

        self.cmb_marca.blockSignals(False)
        self.cmb_rubro.blockSignals(False)
        self.cmb_subrubro.blockSignals(False)

        self._aplicar_filtros()

    def _aplicar_filtros(self):
        if not hasattr(self, '_rows'): return

        f_marca = self.cmb_marca.currentText()
        f_rubro = self.cmb_rubro.currentText()
        f_subrubro = self.cmb_subrubro.currentText()
        f_reciente = self.chk_recientes.isChecked()

        import datetime
        hoy = datetime.datetime.now().date()

        for i, r in enumerate(self._rows):
            mostrar = True
            if f_marca != "Todas" and f_marca != "" and r.get("marca", "") != f_marca: mostrar = False
            if f_rubro != "Todos" and f_rubro != "" and r.get("rubro", "") != f_rubro: mostrar = False
            if f_subrubro != "Todos" and f_subrubro != "" and r.get("subrubro", "") != f_subrubro: mostrar = False
            if f_reciente:
                if r.get("creado_en") is None or r.get("creado_en").date() != hoy: mostrar = False

            self.tbl.setRowHidden(i, not mostrar)

\1'''
content = re.sub(methods_pattern, new_methods, content)

with open("lubricentro_2_2/lubricentro/productos/precios_tab.py", "w", encoding="utf-8") as f:
    f.write(content)
