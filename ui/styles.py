LIGHT_THEME = """
QWidget {
    background-color: #f5f6fa;
    color: #2f3640;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 14px;
}

QMainWindow {
    background-color: #dcdde1;
}

QTabWidget::pane {
    border: 1px solid #dcdde1;
    background: #ffffff;
    border-radius: 4px;
}

QTabBar::tab {
    background: #e1e2e6;
    color: #353b48;
    padding: 10px 20px;
    border: 1px solid #dcdde1;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #ffffff;
    font-weight: bold;
    border-top: 3px solid #0097e6;
}

QTabBar::tab:hover:!selected {
    background: #f5f6fa;
}

/* Tables */
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f8f9fa;
    color: #2f3640;
    gridline-color: #dcdde1;
    border: 1px solid #dcdde1;
    border-radius: 4px;
    selection-background-color: #0097e6;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #f1f2f6;
    color: #2f3640;
    padding: 5px;
    border: 1px solid #dcdde1;
    font-weight: bold;
}

/* Inputs */
QLineEdit, QComboBox, QDoubleSpinBox {
    background-color: #ffffff;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    padding: 5px;
    color: #2f3640;
    min-height: 25px;
}

QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {
    border: 2px solid #0097e6;
}

/* Buttons */
QPushButton {
    background-color: #0097e6;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #00a8ff;
}

QPushButton:pressed {
    background-color: #0081c6;
}

QPushButton:disabled {
    background-color: #bdc3c7;
    color: #7f8fa6;
}

/* GroupBox */
QGroupBox {
    border: 1px solid #dcdde1;
    border-radius: 4px;
    margin-top: 15px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    color: #353b48;
}
"""

DARK_THEME = """
QWidget {
    background-color: #2f3640;
    color: #f5f6fa;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 14px;
}

QMainWindow {
    background-color: #222f3e;
}

QTabWidget::pane {
    border: 1px solid #353b48;
    background: #353b48;
    border-radius: 4px;
}

QTabBar::tab {
    background: #2f3640;
    color: #dcdde1;
    padding: 10px 20px;
    border: 1px solid #222f3e;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #353b48;
    color: #ffffff;
    font-weight: bold;
    border-top: 3px solid #00a8ff;
}

QTabBar::tab:hover:!selected {
    background: #353b48;
}

/* Tables */
QTableWidget {
    background-color: #353b48;
    alternate-background-color: #2f3640;
    color: #f5f6fa;
    gridline-color: #222f3e;
    border: 1px solid #222f3e;
    border-radius: 4px;
    selection-background-color: #00a8ff;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #222f3e;
    color: #f5f6fa;
    padding: 5px;
    border: 1px solid #2f3640;
    font-weight: bold;
}

/* Inputs */
QLineEdit, QComboBox, QDoubleSpinBox {
    background-color: #222f3e;
    border: 1px solid #7f8fa6;
    border-radius: 4px;
    padding: 5px;
    color: #f5f6fa;
    min-height: 25px;
}

QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {
    border: 2px solid #00a8ff;
}

QComboBox QAbstractItemView {
    background-color: #222f3e;
    color: #f5f6fa;
    selection-background-color: #00a8ff;
}

/* Buttons */
QPushButton {
    background-color: #0097e6;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #00a8ff;
}

QPushButton:pressed {
    background-color: #0081c6;
}

QPushButton:disabled {
    background-color: #7f8fa6;
    color: #dcdde1;
}

/* GroupBox */
QGroupBox {
    border: 1px solid #7f8fa6;
    border-radius: 4px;
    margin-top: 15px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    color: #00a8ff;
}
"""
