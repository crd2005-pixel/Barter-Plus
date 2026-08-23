# -*- coding: utf-8 -*-
# ventas/filters_enter.py
from PyQt5.QtCore import QObject, QEvent, Qt

_PATTERNS = ("codigo", "código", "barra", "barras", "dni", "cuit", "doc", "documento")

class SwallowEnterFilter(QObject):
    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.KeyPress, QEvent.KeyRelease):
            k = ev.key()
            if k in (Qt.Key_Return, Qt.Key_Enter):
                return True
        return super().eventFilter(obj, ev)

def _match_name(w):
    try:
        name = (w.objectName() or "").lower()
        ph = (getattr(w, "placeholderText", lambda: "")() or "").lower()
        acc = (getattr(w, "accessibleName", lambda: "")() or "").lower()
        txt = name + " " + ph + " " + acc
        return any(p in txt for p in _PATTERNS)
    except Exception:
        return False

def install_enter_filters(root):
    """Instala filtro SwallowEnterFilter en QLineEdit relevantes dentro de root."""
    if root is None:
        return
    filt = SwallowEnterFilter(root)
    try:
        from PyQt5.QtWidgets import QLineEdit
        edits = root.findChildren(QLineEdit)
        for ed in edits:
            if _match_name(ed):
                ed.installEventFilter(filt)
    except Exception:
        pass
