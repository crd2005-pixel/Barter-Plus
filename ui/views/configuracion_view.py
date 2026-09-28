from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QGroupBox, QFormLayout, QMessageBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QComboBox, QCheckBox, QAbstractItemView, QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtCore import QTimer, QThreadPool, pyqtSlot, Qt
from core.backup_manager import BackupWorker, GoogleDriveUploader
from database.conexion import get_session
from database.models.usuario import Usuario
import hashlib
import json

class ConfiguracionView(QWidget):
    def __init__(self):
        super().__init__()
        self.threadpool = QThreadPool()
        self.setup_ui()
        self._check_auth_status()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._run_backup)
        self._update_timer()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        # Pestaña 1: Respaldos
        self.tab_respaldos = QWidget()
        self._setup_tab_respaldos()

        # Pestaña 2: Accesos
        self.tab_accesos = QWidget()
        self._setup_tab_accesos()

        self.tabs.addTab(self.tab_respaldos, "Respaldos (Drive)")
        self.tabs.addTab(self.tab_accesos, "Gestión de Accesos")

        layout.addWidget(self.tabs)

    def _setup_tab_respaldos(self):
        layout = QVBoxLayout(self.tab_respaldos)

        group_backup = QGroupBox("Google Drive Backup")
        form_backup = QFormLayout()

        self.btn_auth = QPushButton("Autenticar Google Drive")
        self.btn_auth.clicked.connect(self._authenticate)
        self.btn_auth.setStyleSheet("background-color: #3498db; color: white; font-weight: bold; padding: 5px;")

        self.spin_freq = QSpinBox()
        self.spin_freq.setRange(1, 1440)
        self.spin_freq.setValue(10)
        self.spin_freq.setSuffix(" minutos")
        self.spin_freq.valueChanged.connect(self._update_timer)

        self.btn_force = QPushButton("Forzar Backup Ahora")
        self.btn_force.clicked.connect(self._run_backup)
        self.btn_force.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 5px;")

        self.lbl_status = QLabel("Estado: Esperando...")
        self.lbl_status.setStyleSheet("color: #7f8c8d; font-style: italic;")

        form_backup.addRow("Autenticación:", self.btn_auth)
        form_backup.addRow("Frecuencia:", self.spin_freq)
        form_backup.addRow("Acción:", self.btn_force)
        form_backup.addRow("", self.lbl_status)

        group_backup.setLayout(form_backup)
        layout.addWidget(group_backup)
        layout.addStretch()

    def _setup_tab_accesos(self):
        layout = QHBoxLayout(self.tab_accesos)

        # Izquierda: Grilla
        left_panel = QVBoxLayout()
        self.tabla_usuarios = QTableWidget(0, 3)
        self.tabla_usuarios.setHorizontalHeaderLabels(["ID", "Usuario", "Rol"])
        self.tabla_usuarios.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla_usuarios.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla_usuarios.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabla_usuarios.itemSelectionChanged.connect(self._cargar_usuario_seleccionado)
        left_panel.addWidget(self.tabla_usuarios)

        btn_nuevo = QPushButton("Nuevo Usuario")
        btn_nuevo.clicked.connect(self._limpiar_form_usuario)
        left_panel.addWidget(btn_nuevo)

        # Derecha: Formulario
        right_panel = QVBoxLayout()
        group_form = QGroupBox("Datos del Usuario")
        form = QFormLayout()

        self.txt_usr_id = QLineEdit()
        self.txt_usr_id.setReadOnly(True)
        self.txt_usr_id.setPlaceholderText("ID (Auto)")

        self.txt_usr_name = QLineEdit()
        self.txt_usr_pass = QLineEdit()
        self.txt_usr_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_usr_pass.setPlaceholderText("Dejar vacío para no cambiar")

        self.cmb_usr_rol = QComboBox()
        self.cmb_usr_rol.addItems(["Administrador", "Mostrador"])
        self.cmb_usr_rol.currentTextChanged.connect(self._on_rol_changed)

        form.addRow("ID:", self.txt_usr_id)
        form.addRow("Usuario:", self.txt_usr_name)
        form.addRow("Contraseña:", self.txt_usr_pass)
        form.addRow("Rol:", self.cmb_usr_rol)

        group_form.setLayout(form)
        right_panel.addWidget(group_form)

        # Permisos Granulares
        self.group_permisos = QGroupBox("Permisos de Pestañas (Solo Mostrador)")
        permisos_lay = QVBoxLayout()

        self.tree_permisos = QTreeWidget()
        self.tree_permisos.setHeaderHidden(True)

        estructura = {
            "POS": [],
            "Caja": ["Caja Actual", "Historial / Auditoría", "Configuración de Tarjetas"],
            "Egresos": [],
            "Taller": ["Garantías de Baterías", "Cambios de Aceite"],
            "Finanzas": [],
            "Clientes": [],
            "Productos": [],
            "Precios": ["Gestor de Precios", "Códigos de Barra y Etiquetas"],
            "Proveedores": [],
            "Métricas": [],
            "Configuración": []
        }

        self.nodos_dict = {}

        for padre, hijos in estructura.items():
            item_padre = QTreeWidgetItem([padre])
            item_padre.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            item_padre.setCheckState(0, Qt.CheckState.Unchecked)
            self.tree_permisos.addTopLevelItem(item_padre)
            self.nodos_dict[padre] = item_padre

            for hijo in hijos:
                item_hijo = QTreeWidgetItem([hijo])
                item_hijo.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                item_hijo.setCheckState(0, Qt.CheckState.Unchecked)
                item_padre.addChild(item_hijo)
                self.nodos_dict[f"{padre}:{hijo}"] = item_hijo

        self.tree_permisos.expandAll()
        permisos_lay.addWidget(self.tree_permisos)

        self.group_permisos.setLayout(permisos_lay)
        right_panel.addWidget(self.group_permisos)

        # Botones
        hb_botones = QHBoxLayout()
        self.btn_guardar_usr = QPushButton("Guardar Cambios")
        self.btn_guardar_usr.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.btn_guardar_usr.clicked.connect(self._guardar_usuario)

        self.btn_eliminar_usr = QPushButton("Eliminar Usuario")
        self.btn_eliminar_usr.setStyleSheet("background-color: #c0392b; color: white;")
        self.btn_eliminar_usr.clicked.connect(self._eliminar_usuario)

        hb_botones.addWidget(self.btn_guardar_usr)
        hb_botones.addWidget(self.btn_eliminar_usr)
        right_panel.addLayout(hb_botones)
        right_panel.addStretch()

        layout.addLayout(left_panel, 1)
        layout.addLayout(right_panel, 1)

        self._cargar_grilla_usuarios()

    def _cargar_grilla_usuarios(self):
        with get_session() as s:
            usuarios = s.query(Usuario).all()
            self.tabla_usuarios.setRowCount(len(usuarios))
            for r, u in enumerate(usuarios):
                self.tabla_usuarios.setItem(r, 0, QTableWidgetItem(str(u.id)))
                self.tabla_usuarios.setItem(r, 1, QTableWidgetItem(u.usuario))
                self.tabla_usuarios.setItem(r, 2, QTableWidgetItem(u.rol))

    def _limpiar_form_usuario(self):
        self.tabla_usuarios.clearSelection()
        self.txt_usr_id.clear()
        self.txt_usr_name.clear()
        self.txt_usr_pass.clear()
        self.cmb_usr_rol.setCurrentIndex(1) # Mostrador
        for nodo in self.nodos_dict.values():
            nodo.setCheckState(0, Qt.CheckState.Unchecked)

    def _cargar_usuario_seleccionado(self):
        items = self.tabla_usuarios.selectedItems()
        if not items: return
        uid = int(items[0].text())
        with get_session() as s:
            u = s.get(Usuario, uid)
            if not u: return

            self.txt_usr_id.setText(str(u.id))
            self.txt_usr_name.setText(u.usuario)
            self.txt_usr_pass.clear()
            self.cmb_usr_rol.setCurrentText(u.rol)

            for nodo in self.nodos_dict.values():
                nodo.setCheckState(0, Qt.CheckState.Unchecked)

            if u.rol == "Administrador":
                self._on_rol_changed("Administrador")
            else:
                self._on_rol_changed("Mostrador")
                try:
                    permisos = json.loads(u.permisos) if u.permisos else []
                except:
                    # Fallback for old comma-separated
                    permisos = u.permisos.split(',') if u.permisos else []

                for p in permisos:
                    if p in self.nodos_dict:
                        self.nodos_dict[p].setCheckState(0, Qt.CheckState.Checked)

    def _on_rol_changed(self, rol):
        if rol == "Administrador":
            self.group_permisos.setEnabled(False)
            for nodo in self.nodos_dict.values():
                nodo.setCheckState(0, Qt.CheckState.Checked)
        else:
            self.group_permisos.setEnabled(True)

    def _guardar_usuario(self):
        usr = self.txt_usr_name.text().strip()
        pwd = self.txt_usr_pass.text()
        rol = self.cmb_usr_rol.currentText()

        if not usr:
            QMessageBox.warning(self, "Error", "El nombre de usuario no puede estar vacío.")
            return

        if rol == "Administrador":
            permisos = "TODOS"
        else:
            perm_list = [k for k, v in self.nodos_dict.items() if v.checkState(0) == Qt.CheckState.Checked]
            permisos = json.dumps(perm_list)

        with get_session() as s:
            if self.txt_usr_id.text():
                # Edit
                u = s.get(Usuario, int(self.txt_usr_id.text()))
                u.usuario = usr
                u.rol = rol
                u.permisos = permisos
                if pwd:
                    u.password = hashlib.sha256(pwd.encode()).hexdigest()
            else:
                # New
                if not pwd:
                    QMessageBox.warning(self, "Error", "Debe ingresar una contraseña para el nuevo usuario.")
                    return
                # Check exist
                if s.query(Usuario).filter(Usuario.usuario == usr).count() > 0:
                    QMessageBox.warning(self, "Error", "El nombre de usuario ya existe.")
                    return

                u = Usuario(
                    usuario=usr,
                    password=hashlib.sha256(pwd.encode()).hexdigest(),
                    rol=rol,
                    permisos=permisos
                )
                s.add(u)
            s.commit()

        QMessageBox.information(self, "Éxito", "Usuario guardado.")
        self._cargar_grilla_usuarios()
        self._limpiar_form_usuario()

    def _eliminar_usuario(self):
        if not self.txt_usr_id.text(): return
        uid = int(self.txt_usr_id.text())

        # Prevent self deletion or last admin deletion
        with get_session() as s:
            u = s.get(Usuario, uid)
            if u.rol == "Administrador":
                admins = s.query(Usuario).filter(Usuario.rol == "Administrador").count()
                if admins <= 1:
                    QMessageBox.warning(self, "Error", "No puede eliminar al último administrador.")
                    return

            s.delete(u)
            s.commit()

        QMessageBox.information(self, "Éxito", "Usuario eliminado.")
        self._cargar_grilla_usuarios()
        self._limpiar_form_usuario()

    # --- RESPALDOS ---
    def _update_timer(self):
        mins = self.spin_freq.value()
        self.timer.start(mins * 60 * 1000)

    def _check_auth_status(self):
        import os
        if os.path.exists("token.json"):
            self.btn_auth.setText("Autenticado ✓")
            self.btn_auth.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 5px;")
            self.btn_auth.setEnabled(False)

    def _authenticate(self):
        try:
            self.lbl_status.setText("Estado: Autenticando...")
            uploader = GoogleDriveUploader()
            uploader.authenticate()
            self._check_auth_status()
            self.lbl_status.setText("Estado: Autenticación Exitosa.")
        except FileNotFoundError as e:
            QMessageBox.critical(self, "Error de Credenciales", str(e))
            self.lbl_status.setText("Estado: Faltan credenciales.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al autenticar: {e}")
            self.lbl_status.setText("Estado: Error de Autenticación.")

    @pyqtSlot()
    def _run_backup(self):
        self.lbl_status.setText("Estado: Respaldando base de datos...")
        self.btn_force.setEnabled(False)

        worker = BackupWorker()
        worker.signals.finished.connect(self._on_backup_finished)
        self.threadpool.start(worker)

    def _on_backup_finished(self, success, msg):
        self.btn_force.setEnabled(True)
        if success:
            self.lbl_status.setText(f"Estado: {msg}")
            self.lbl_status.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self.lbl_status.setText(f"Estado: Error en backup - {msg}")
            self.lbl_status.setStyleSheet("color: #c0392b; font-weight: bold;")
