import re

with open('unificador_listas/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Make sure we clean up any remnants of old treeviews and tabs updates.
# For example, `populate_audit_tables` needs to update the new button texts and refresh treeview.
new_populate = """
    def populate_audit_tables(self):
        self.audit_updates_list.clear()
        self.audit_new_list.clear()

        for item in self.extracted_data:
            prov = item['proveedor']
            cod = item['codigo_proveedor']
            desc = item['descripcion']
            marca = item['marca']
            costo = item['costo_neto']

            # Double Lock Check
            match_sku = None
            match_data = None

            candidates = []
            if prov in self.mapa_por_cod_prov and cod in self.mapa_por_cod_prov[prov]:
                candidates.extend(self.mapa_por_cod_prov[prov][cod])

            cod_suffix = str(cod).split('-')[-1].upper()
            if cod_suffix in self.mapa_por_sku_sufijo:
                candidates.extend(self.mapa_por_sku_sufijo[cod_suffix])

            def validate_match(candidate):
                sku_cand = candidate['sku_interno']
                # Prefijos y semantica
                if self._is_prefix_match(prov, marca, sku_cand):
                    return True
                if self._is_semantic_match(desc, candidate['descripcion']):
                    return True
                return False

            for cand in candidates:
                if validate_match(cand):
                    match_sku = cand['sku_interno']
                    match_data = cand
                    break

            if not match_sku and desc in self.mapa_por_descripcion:
                match_sku = self.mapa_por_descripcion[desc]['sku_interno']
                match_data = self.mapa_por_descripcion[desc]

            if match_sku:
                costo_ant = match_data.get('costo_neto', 0.0)
                var = 0.0
                if costo_ant > 0:
                    var = ((costo - costo_ant) / costo_ant) * 100

                self.audit_updates_list.append({
                    'sku_interno': match_sku,
                    'proveedor': prov,
                    'codigo_proveedor': cod,
                    'descripcion': desc,
                    'marca': marca,
                    'costo_ant': costo_ant,
                    'costo_nvo': costo,
                    'variacion': var
                })
            else:
                self.audit_new_list.append(item)

        # Update summary labels
        total_extracted = len(self.extracted_data)
        total_upd = len(self.audit_updates_list)
        total_new = len(self.audit_new_list)

        if hasattr(self, 'lbl_summary'):
            self.lbl_summary.configure(text=f"Total extraído: {total_extracted} productos | {total_upd} para actualizar | {total_new} nuevos")
            self.btn_view_updates.configure(text=f"🔄 Actualizaciones ({total_upd})")
            self.btn_view_new.configure(text=f"✨ Productos Nuevos ({total_new})")

        self.filter_treeview()
"""

# Replace `populate_audit_tables`
start_pop = content.find("def populate_audit_tables")
end_pop = content.find("if __name__ == \"__main__\":", start_pop)

if start_pop != -1 and end_pop != -1:
    content = content[:start_pop] + new_populate + "\n" + content[end_pop:]
    with open('unificador_listas/app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Populate updated.")
else:
    print("Could not find populate.")
