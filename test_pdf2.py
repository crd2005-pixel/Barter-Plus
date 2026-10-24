from test_pdf import extraer_productos_de_pdf
import pdfplumber

class MockPage:
    def extract_tables(self):
        return [
            [
                ["SFF32205", "FILTRO COMB.", "WK6002\n$ 4.434", "CA10697", "C31003/1"]
            ]
        ]
    def extract_text(self, **kwargs):
        return ""

class MockPDF:
    pages = [MockPage()]
    def __enter__(self): return self
    def __exit__(self, *args): pass

pdfplumber.open = lambda f: MockPDF()
print(extraer_productos_de_pdf("dummy.pdf", "PROV"))
