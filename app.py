import streamlit as st
import requests

def main():
    st.set_page_config(page_title="Auditoría de API Gemini", layout="centered")

    st.title("Diagnóstico Estricto de Modelos Gemini")
    st.info("Ingresa tu API Key para auditar los modelos exactos a los que tienes acceso.")

    api_key = st.text_input("Gemini API Key", type="password")

    if st.button("Auditar Modelos Disponibles"):
        if not api_key:
            st.error("Por favor, ingresa una API Key.")
            return

        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

        with st.spinner("Consultando API de Google..."):
            try:
                resp = requests.get(url)

                if resp.status_code != 200:
                    st.error(f"Error de conexión (HTTP {resp.status_code})")
                    st.code(resp.text)
                    return

                data = resp.json()
                models = data.get('models', [])

                valid_models = []
                for m in models:
                    methods = m.get('supportedGenerationMethods', [])
                    name = m.get('name', '')

                    if 'generateContent' in methods and 'gemini' in name.lower():
                        valid_models.append(name)

                if valid_models:
                    st.success("✅ Auditoría completada. Modelos autorizados:")
                    for m_name in valid_models:
                        st.write(f"- `{m_name}`")
                else:
                    st.warning("No se encontraron modelos 'gemini' que soporten 'generateContent' con esta API Key.")

            except Exception as e:
                st.error(f"Excepción durante la auditoría: {e}")

if __name__ == '__main__':
    main()
