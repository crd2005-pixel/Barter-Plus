import streamlit as st
import pandas as pd
import io
import re
import numpy as np

st.set_page_config(page_title="Gestor de Precios", layout="wide")

def clean_price(value):
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    s = re.sub(r'[^\d.,-]', '', str(value).strip())
    if not s:
        return 0.0

    if '.' in s and ',' in s:
        if s.rfind(',') > s.rfind('.'): # e.g. 1.500,50
            s = s.replace('.', '').replace(',', '.')
        else: # e.g. 1,500.50
            s = s.replace(',', '')
    elif ',' in s: # e.g. 1500,50
        s = s.replace(',', '.')
    elif '.' in s: # e.g. 1.500
        parts = s.split('.')
        if len(parts) > 1 and len(parts[-1]) == 3:
            s = s.replace('.', '')

    try:
        return float(s)
    except ValueError:
        return 0.0

def calculate_final_price(pm, margin):
    try:
        pm = float(pm)
        margin = float(margin)
    except:
        return 0.0
    if pd.isna(pm) or pm == 0:
        return 0.0
    if margin >= 100:
        return 0.0
    return round(pm / (1 - (margin / 100.0)), 2)

def to_excel(df_export):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Precios Actualizados')
    return output.getvalue()

def update_calculations():
    editor_key = f"data_editor_{st.session_state.get('editor_key', 0)}"
    edited_rows = st.session_state[editor_key].get('edited_rows', {})

    # Apply changes to session state df
    for idx_str, row_changes in edited_rows.items():
        idx = int(idx_str)
        if 'Costo Nuevo (PM)' in row_changes:
            st.session_state.df.at[idx, 'Costo Nuevo (PM)'] = float(row_changes['Costo Nuevo (PM)'])
        if 'Margen Aplicado (%)' in row_changes:
            st.session_state.df.at[idx, 'Margen Aplicado (%)'] = float(row_changes['Margen Aplicado (%)'])

    # Recalculate everything
    st.session_state.df['Costo Nuevo (PM)'] = pd.to_numeric(st.session_state.df['Costo Nuevo (PM)'], errors='coerce').fillna(0.0)
    st.session_state.df['Margen Aplicado (%)'] = pd.to_numeric(st.session_state.df['Margen Aplicado (%)'], errors='coerce').fillna(0.0)
    st.session_state.df['Margen Aplicado (%)'] = st.session_state.df['Margen Aplicado (%)'].clip(upper=99.99)

    st.session_state.df['Precio Final Calculado (PF)'] = st.session_state.df.apply(
        lambda row: calculate_final_price(row['Costo Nuevo (PM)'], row['Margen Aplicado (%)']), axis=1
    )

def main():
    st.title("Gestor Maestro de Precios")

    st.sidebar.header("1. Cargar Archivo")
    uploaded_file = st.sidebar.file_uploader("Sube Lista de Precios (.xlsx, .xls, .csv)", type=["xlsx", "xls", "csv"])

    if uploaded_file is not None:
        if 'uploaded_filename' not in st.session_state or st.session_state.uploaded_filename != uploaded_file.name:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)

                st.session_state.raw_df = df
                st.session_state.uploaded_filename = uploaded_file.name

                st.session_state.df = df.copy()
                st.session_state.initialized = False
            except Exception as e:
                st.error(f"Error al leer el archivo: {e}")
                return

        df = st.session_state.raw_df
        columns = list(df.columns)

        st.sidebar.header("2. Mapeo de Columnas")
        col_prov = st.sidebar.selectbox("Columna Proveedor", ["-- Ninguna --"] + columns)
        col_marca = st.sidebar.selectbox("Columna Marca", ["-- Ninguna --"] + columns)
        col_rubro = st.sidebar.selectbox("Columna Rubro", ["-- Ninguna --"] + columns)
        col_costo = st.sidebar.selectbox("Columna Costo (PM)", ["-- Ninguna --"] + columns)

        if col_costo != "-- Ninguna --":
            if st.session_state.get('last_cost_col') != col_costo:
                working_df = st.session_state.raw_df.copy()
                working_df['Costo Anterior'] = working_df[col_costo].apply(clean_price)
                working_df['Costo Nuevo (PM)'] = working_df['Costo Anterior']
                working_df['Margen Aplicado (%)'] = 0.0
                working_df['Precio Final Calculado (PF)'] = working_df['Costo Nuevo (PM)']
                st.session_state.df = working_df
                st.session_state.last_cost_col = col_costo
                st.session_state.editor_key = st.session_state.get('editor_key', 0) + 1

            st.header("3. Filtros y Aumentos")
            col1, col2, col3 = st.columns(3)

            with col1:
                filter_type = st.radio("Tipo de Aumento", ["Masivo", "Por Proveedor", "Por Marca", "Por Rubro"])

            with col2:
                filter_value = None
                if filter_type == "Por Proveedor" and col_prov != "-- Ninguna --":
                    proveedores = df[col_prov].dropna().astype(str).unique().tolist()
                    filter_value = st.selectbox("Selecciona Proveedor", proveedores)
                elif filter_type == "Por Marca" and col_marca != "-- Ninguna --":
                    marcas = df[col_marca].dropna().astype(str).unique().tolist()
                    filter_value = st.selectbox("Selecciona Marca", marcas)
                elif filter_type == "Por Rubro" and col_rubro != "-- Ninguna --":
                    rubros = df[col_rubro].dropna().astype(str).unique().tolist()
                    filter_value = st.selectbox("Selecciona Rubro", rubros)
                elif filter_type != "Masivo":
                    st.warning("Selecciona la columna correspondiente en la barra lateral para filtrar.")

            with col3:
                margen_input = st.number_input("Margen (%)", min_value=0.0, max_value=99.99, value=0.0, step=1.0)
                if st.button("Aplicar Aumento"):
                    working_df = st.session_state.df

                    mask = pd.Series(True, index=working_df.index)
                    if filter_type == "Por Proveedor":
                        if col_prov != "-- Ninguna --" and filter_value:
                            mask = working_df[col_prov].astype(str) == filter_value
                        else:
                            mask = pd.Series(False, index=working_df.index)
                    elif filter_type == "Por Marca":
                        if col_marca != "-- Ninguna --" and filter_value:
                            mask = working_df[col_marca].astype(str) == filter_value
                        else:
                            mask = pd.Series(False, index=working_df.index)
                    elif filter_type == "Por Rubro":
                        if col_rubro != "-- Ninguna --" and filter_value:
                            mask = working_df[col_rubro].astype(str) == filter_value
                        else:
                            mask = pd.Series(False, index=working_df.index)

                    working_df.loc[mask, 'Margen Aplicado (%)'] = margen_input
                    working_df.loc[mask, 'Precio Final Calculado (PF)'] = working_df.loc[mask].apply(
                        lambda row: calculate_final_price(row['Costo Nuevo (PM)'], row['Margen Aplicado (%)']), axis=1
                    )
                    st.session_state.df = working_df
                    st.session_state.editor_key = st.session_state.get('editor_key', 0) + 1
                    st.success("¡Aumento aplicado correctamente!")

            st.header("4. Previsualización y Edición Individual")
            st.write("Puedes editar el Costo Nuevo o el Margen directamente en la tabla. El Precio Final se recalculará automáticamente.")

            working_df = st.session_state.df

            display_cols = columns + ['Costo Anterior', 'Costo Nuevo (PM)', 'Margen Aplicado (%)', 'Precio Final Calculado (PF)']

            st.data_editor(
                working_df[display_cols],
                use_container_width=True,
                num_rows="fixed",
                key=f"data_editor_{st.session_state.get('editor_key', 0)}",
                on_change=update_calculations,
                disabled=columns + ['Costo Anterior', 'Precio Final Calculado (PF)'] # Only allow editing new cost and margin
            )

            st.header("5. Exportar Datos")

            excel_data = to_excel(st.session_state.df)
            st.download_button(
                label="📥 Descargar Lista de Precios Actualizada (Excel)",
                data=excel_data,
                file_name="Lista_Precios_Actualizada.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

if __name__ == '__main__':
    main()
