from .bootstrap import bootstrap
class ModelNamespace:
    def __init__(self, d):
        self.Proveedor = d["Proveedor"]
        self.ListaPrecioProveedor = d["ListaPrecioProveedor"]
        self.ItemListaProveedor = d["ItemListaProveedor"]
        self.FacturaProveedor = d["FacturaProveedor"]
        self.MovimientoProveedor = d["MovimientoProveedor"]
        self.sessionmaker = d["SessionLocal"]
        self.ok = True
def ensure_models():
    return ModelNamespace(bootstrap())
