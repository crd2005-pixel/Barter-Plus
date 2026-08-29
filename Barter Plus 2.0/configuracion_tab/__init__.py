# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton, QGroupBox, QSpacerItem, QSizePolicy
)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import QApplication

class ConfiguracionTab(QWidget):
    def __init__(self, apply_theme_callback=None):
        super().__init__()
        self.apply_theme_callback = apply_theme_callback
        self.settings = QSettings("BarterPlus", "App")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Grupo de Temas
        gb_temas = QGroupBox("Tema de la Aplicación")
        lay_temas = QVBoxLayout(gb_temas)

        self.rb_oscuro = QRadioButton("Tema Oscuro")
        self.rb_claro = QRadioButton("Tema Claro")

        lay_temas.addWidget(self.rb_oscuro)
        lay_temas.addWidget(self.rb_claro)

        # Cargar estado actual
        current_theme = self.settings.value("theme", "oscuro")
        if current_theme == "oscuro":
            self.rb_oscuro.setChecked(True)
        else:
            self.rb_claro.setChecked(True)

        # Conectar señales
        self.rb_oscuro.toggled.connect(self._on_theme_changed)
        self.rb_claro.toggled.connect(self._on_theme_changed)

        layout.addWidget(gb_temas)
        layout.addStretch()

    def _on_theme_changed(self):
        if self.rb_oscuro.isChecked():
            theme = "oscuro"
        else:
            theme = "claro"

        # Guardar en settings
        self.settings.setValue("theme", theme)

        # Aplicar
        if self.apply_theme_callback:
            self.apply_theme_callback(theme)
