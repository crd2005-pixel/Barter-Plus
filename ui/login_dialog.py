from PyQt6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QLabel, QMessageBox
from PyQt6.QtCore import Qt
import hashlib
from database.conexion import get_session
from database.models.usuario import Usuario

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Acceso Restringido - Barter Plus")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        self.resize(300, 150)
        self.permisos = ""
        self.rol = ""
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        lbl = QLabel("Ingrese sus credenciales")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(lbl)

        form = QFormLayout()
        self.txt_user = QLineEdit()
        self.txt_pass = QLineEdit()
        self.txt_pass.setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow("Usuario:", self.txt_user)
        form.addRow("Contraseña:", self.txt_pass)
        layout.addLayout(form)

        btn_login = QPushButton("Ingresar")
        btn_login.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; padding: 8px;")
        btn_login.clicked.connect(self._intentar_login)
        layout.addWidget(btn_login)

    def _intentar_login(self):
        usr = self.txt_user.text().strip()
        pwd = self.txt_pass.text()
        if not usr or not pwd:
            QMessageBox.warning(self, "Error", "Debe ingresar usuario y contraseña.")
            return

        pwd_hash = hashlib.sha256(pwd.encode()).hexdigest()

        with get_session() as s:
            u = s.query(Usuario).filter(Usuario.usuario == usr, Usuario.password == pwd_hash).first()
            if u:
                self.permisos = u.permisos
                self.rol = u.rol
                self.accept()
            else:
                QMessageBox.critical(self, "Error", "Credenciales inválidas.")

    def get_permisos(self):
        return self.permisos

    def get_rol(self):
        return self.rol
