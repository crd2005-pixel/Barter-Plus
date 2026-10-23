import sys
# Override GUI components for headless testing
from unificador_listas.app import App
import tkinter as tk

def mock_populate(self):
    print("Populate called")

App.populate_audit_tables = mock_populate

app = App()
app.current_file = "dummy.pdf"
app.current_file_type = "pdf"
app.entry_proveedor = type('obj', (object,), {'get': lambda self: 'PROV'})()
app.api_key = "dummy"

import pdfplumber
class MockPage:
    def extract_tables(self):
        return [[ ["SFF32205", "FILTRO COMB.", "WK6002\n$ 4.434", "CA10697", "C31003/1"] ]]
    def extract_text(self, **kwargs):
        return ""
class MockPDF:
    pages = [MockPage()]
    def __enter__(self): return self
    def __exit__(self, *args): pass
pdfplumber.open = lambda f: MockPDF()

from tkinter import messagebox
messagebox.showinfo = lambda *args, **kwargs: None

app.process_file()
for x in app.extracted_data:
    print(x)
