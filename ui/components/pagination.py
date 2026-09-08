from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import pyqtSignal

class PaginationWidget(QWidget):
    page_changed = pyqtSignal(int) # Emite el índice de página al cambiar (0-based)

    def __init__(self, limit=50):
        super().__init__()
        self.limit = limit
        self.current_page = 0
        self.total_items = 0
        self.total_pages = 1

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.btn_prev = QPushButton("< Anterior")
        self.lbl_info = QLabel("Página 1 de 1")
        self.btn_next = QPushButton("Siguiente >")

        self.layout.addStretch()
        self.layout.addWidget(self.btn_prev)
        self.layout.addWidget(self.lbl_info)
        self.layout.addWidget(self.btn_next)
        self.layout.addStretch()

        self.btn_prev.clicked.connect(self.go_prev)
        self.btn_next.clicked.connect(self.go_next)

        self.update_ui()

    def set_total_items(self, total):
        self.total_items = total
        self.total_pages = max(1, (self.total_items + self.limit - 1) // self.limit)
        # Reset to 0 if out of bounds
        if self.current_page >= self.total_pages:
            self.current_page = 0
        self.update_ui()
        self.page_changed.emit(self.current_page)

    def go_prev(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_ui()
            self.page_changed.emit(self.current_page)

    def go_next(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_ui()
            self.page_changed.emit(self.current_page)

    def update_ui(self):
        self.lbl_info.setText(f"Página {self.current_page + 1} de {self.total_pages}")
        self.btn_prev.setEnabled(self.current_page > 0)
        self.btn_next.setEnabled(self.current_page < self.total_pages - 1)

    def get_slice(self):
        start = self.current_page * self.limit
        end = start + self.limit
        return slice(start, end)
