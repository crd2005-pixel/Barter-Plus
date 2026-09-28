from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QGroupBox, QFormLayout, QMessageBox, QProgressBar
)
from PyQt6.QtCore import QTimer, QThreadPool, pyqtSlot
from core.backup_manager import BackupWorker, GoogleDriveUploader

class ConfiguracionView(QWidget):
    def __init__(self):
        super().__init__()
        self.threadpool = QThreadPool()
        self.setup_ui()
        self._check_auth_status()

        # Iniciar Timer de Backup
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._run_backup)
        self._update_timer()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Grupo Backup
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
