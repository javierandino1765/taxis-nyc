"""Punto de entrada de la app Taxis NYC.

Una app de varias páginas con st.navigation + st.Page (función avanzada). Cada página
vive en su propio archivo dentro de `paginas/`. La app nunca carga el modelo: le pregunta
a la API y lee los CSV precalculados.
"""
import streamlit as st

st.set_page_config(page_title="Taxis NYC", page_icon="🚕", layout="wide")

# Secciones y páginas (iconos de Material)
paginas = {
    "Resumen": [
        st.Page("paginas/0_inicio.py", title="Plan del día", icon=":material/dashboard:", default=True),
    ],
    "Planificar": [
        st.Page("paginas/1_pronostico.py", title="Pronóstico", icon=":material/insights:"),
        st.Page("paginas/2_decision.py", title="Decisión", icon=":material/balance:"),
    ],
    "Entender": [
        st.Page("paginas/3_segmentacion.py", title="Segmentación de zonas", icon=":material/scatter_plot:"),
        st.Page("paginas/4_ficha.py", title="Ficha del modelo", icon=":material/description:"),
        st.Page("paginas/5_monitoreo.py", title="Monitoreo", icon=":material/monitoring:"),
    ],
}

st.navigation(paginas, position="sidebar").run()
