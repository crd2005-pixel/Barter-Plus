import re

with open("lubricentro_2_2/lubricentro/productos/codigos_barra.py", "r", encoding="utf-8") as f:
    content = f.read()

setup_ui_pattern = r'(        self\.chk_solo_sin_codigo\.stateChanged\.connect\(self\._load_data\)\n        bar\.addWidget\(self\.chk_solo_sin_codigo\))'
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

        layout.addLayout(self.lay_filtros)

        self.cmb_marca.currentIndexChanged.connect(self._aplicar_filtros)
        self.cmb_rubro.currentIndexChanged.connect(self._aplicar_filtros)
        self.cmb_subrubro.currentIndexChanged.connect(self._aplicar_filtros)
        self.chk_recientes.stateChanged.connect(self._aplicar_filtros)
'''
content = re.sub(setup_ui_pattern, new_setup_ui, content)


load_data_pattern = r'(                rows\.append\(\(p, m_nombre\)\)\n            \n            self\.tbl\.setRowCount\(len\(rows\)\))'
new_load_data = r'''                rows.append((p, m_nombre))

            self._datos_filtro = []
            for p, m_nombre in rows:
                rubro = str(getattr(p, "rubro", "") or "")
                subrubro = str(getattr(p, "subrubro", "") or "")
                creado_en = getattr(p, "creado_en", None)

                self._datos_filtro.append({
                    "marca": m_nombre or "",
                    "rubro": rubro,
                    "subrubro": subrubro,
                    "creado_en": creado_en
                })

            self.tbl.setRowCount(len(rows))'''
content = re.sub(load_data_pattern, new_load_data, content)


after_load_pattern = r'(                self\.tbl\.item\(r, 1\)\.setData\(Qt\.UserRole, p\.id\))'
new_after_load = r'''\1
            self._actualizar_combos_filtro()
'''
content = re.sub(after_load_pattern, new_after_load, content)


methods_pattern = r'(    def _asignar_codigos_faltantes\(self\):)'
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

        marcas = sorted(list(set([d["marca"] for d in self._datos_filtro if d["marca"]])))
        rubros = sorted(list(set([d["rubro"] for d in self._datos_filtro if d["rubro"]])))
        subrubros = sorted(list(set([d["subrubro"] for d in self._datos_filtro if d["subrubro"]])))

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
        if not hasattr(self, '_datos_filtro'): return

        f_marca = self.cmb_marca.currentText()
        f_rubro = self.cmb_rubro.currentText()
        f_subrubro = self.cmb_subrubro.currentText()
        f_reciente = self.chk_recientes.isChecked()

        import datetime
        hoy = datetime.datetime.now().date()

        for i, d in enumerate(self._datos_filtro):
            mostrar = True
            if f_marca != "Todas" and f_marca != "" and d["marca"] != f_marca: mostrar = False
            if f_rubro != "Todos" and f_rubro != "" and d["rubro"] != f_rubro: mostrar = False
            if f_subrubro != "Todos" and f_subrubro != "" and d["subrubro"] != f_subrubro: mostrar = False
            if f_reciente:
                if d["creado_en"] is None or d["creado_en"].date() != hoy: mostrar = False

            self.tbl.setRowHidden(i, not mostrar)

\1'''
content = re.sub(methods_pattern, new_methods, content)

with open("lubricentro_2_2/lubricentro/productos/codigos_barra.py", "w", encoding="utf-8") as f:
    f.write(content)
