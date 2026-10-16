from unificador_listas.app import App

app = App()
print("Sufijo keys:", list(app.mapa_por_sku_sufijo.keys()))
print("Desc keys:", list(app.mapa_por_descripcion.keys()))
print("Cod keys:", list(app.mapa_por_cod_prov.keys()))
