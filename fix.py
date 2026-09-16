with open("ui/views/ventas_view.py", "r") as f:
    text = f.read()

import re

# extract TicketPreviewDialog
match = re.search(r"class TicketPreviewDialog\(QDialog\):.*?def procesar_cobro\(self\):", text, re.DOTALL)
if match:
    dialog_code = match.group(0).replace("def procesar_cobro(self):", "")
    text = text.replace(match.group(0), "    def procesar_cobro(self):")
    with open("ui/views/ventas_view.py", "w") as f:
        f.write(text)

    # Append to dialogs.py
    with open("ui/components/dialogs.py", "a") as f:
        f.write("\nfrom PyQt6.QtWidgets import QWidget, QSplitter, QComboBox, QDoubleSpinBox, QSpinBox, QFileDialog\n")
        f.write("from PyQt6.QtPrintSupport import QPrinter, QPrintPreviewWidget, QPrintDialog\n")
        f.write("from PyQt6.QtGui import QPainter, QFont, QPageSize, QPixmap, QFontMetrics\n")
        f.write("from PyQt6.QtCore import QSizeF, QSettings, Qt, QRectF, QTimer, QMarginsF\n")
        f.write("import os\n")
        f.write(dialog_code)

with open("ui/views/ventas_view.py", "r") as f:
    text = f.read()
text = text.replace("from ui.components.dialogs import FastClientDialog, ItemManualDialog", "from ui.components.dialogs import FastClientDialog, ItemManualDialog, TicketPreviewDialog")
with open("ui/views/ventas_view.py", "w") as f:
    f.write(text)
