"""Página 4 · Ficha del modelo (Parte 4). Todas las cifras salen del notebook."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import comun

comun.barra_lateral_api()

comun.encabezado("Ficha del modelo",
                 "Qué hace el modelo, qué tan bien lo hace y en qué no se debe confiar. Una ficha (model card) "
                 "es un documento estándar para que cualquier persona entienda un modelo antes de usarlo.")

m = comun.cargar_metricas()
comun.exigir_datos(m, "metricas_modelo.json")

# --- Para qué sirve ---
with st.container(border=True, key="card-proposito"):
    st.subheader(":material/target: Para qué sirve")
    st.write(
        f'Pronostica cuántos viajes de taxi amarillo empezarán **cada hora** en '
        f'**{m["n_zonas_pronostico"]} zonas** de Nueva York, con un rango de incertidumbre '
        f'(cuantiles del 10% al 90%). Está pensado para **planificar la flota** con un día de anticipación.'
    )
    b1, b2, b3 = st.columns(3)
    for col, txt in zip((b1, b2, b3),
                        (m["modelo"], "Datos: NYC TLC, enero 2024", f'Horizonte: {m["horizonte"]}')):
        with col:
            try:
                st.badge(txt, color="gray")
            except Exception:
                st.info(txt)

# --- Qué tan bien funciona ---
st.subheader(":material/monitoring: Qué tan bien funciona")
st.caption(f'Evaluado en la semana de prueba ({m["prueba"]}, {m["n_horas_prueba"]:,} horas-zona que el '
           "modelo nunca vio).")
k1, k2, k3 = st.columns(3)
k1.metric("Error del modelo", f'{m["mae_modelo"]:.1f} viajes/hora',
          delta=f'-{m["mejora_vs_semanal_pct"]:.0f}% vs. “igual que hace una semana”',
          delta_color="inverse", border=True, height="stretch")
k2.metric("Cobertura del rango 10%–90%", f'{m["cobertura_80"]:.0f}%',
          delta="objetivo: 80%", delta_color="off", border=True, height="stretch")
k3.metric("Zonas agrupadas", f'{m["n_zonas_segmentar"]}',
          delta=f'{m["n_grupos"]} grupos (K-Means)', delta_color="off", border=True, height="stretch")

g1, g2 = st.columns(2, gap="medium")
with g1.container(border=True, key="card-reglas"):
    st.markdown("**Error frente a reglas simples**")
    _s = pd.Series(m["error_vs_reglas"]).sort_values()
    _f = go.Figure(go.Bar(x=_s.values, y=_s.index, orientation="h",
                          marker_color=comun.COLOR["asfalto"], marker_line_width=0,
                          text=[f"{v:.1f}" for v in _s.values], textposition="outside", cliponaxis=False))
    _f.update_layout(height=240, xaxis_title="Viajes por hora", hovermode="closest",
                     margin=dict(l=10, r=40, t=10, b=10),
                     xaxis=dict(showgrid=True, gridcolor=comun.COLOR["rejilla"]))
    st.plotly_chart(comun.fig_taxis(_f), width="stretch", theme=None, config={"displayModeBar": False})
    st.caption("El modelo le gana a “igual que hace una semana” por poco. Su valor principal está en el "
               "**rango**, que las reglas simples no dan.")
with g2.container(border=True, key="card-tipo"):
    st.markdown("**Error según el tipo de zona**")
    _s = pd.Series(m["error_por_tipo_zona"]).sort_values()
    _f = go.Figure(go.Bar(x=_s.values, y=_s.index, orientation="h",
                          marker_color=comun.COLOR["amarillo"], marker_line_width=0,
                          text=[f"{v:.1f}" for v in _s.values], textposition="outside", cliponaxis=False))
    _f.update_layout(height=240, xaxis_title="Viajes por hora", hovermode="closest",
                     margin=dict(l=10, r=40, t=10, b=10),
                     xaxis=dict(showgrid=True, gridcolor=comun.COLOR["rejilla"]))
    st.plotly_chart(comun.fig_taxis(_f), width="stretch", theme=None, config={"displayModeBar": False})
    st.caption("En los **aeropuertos** el error es mayor: dependen de vuelos y retrasos que el modelo no ve.")

# --- Limitaciones ---
with st.container(border=True, key="card-limites"):
    st.subheader(":material/warning: Limitaciones")
    st.markdown(
        f"- Entrenado con **un solo mes de invierno**: no conoce el verano, las vacaciones ni eventos "
        "como el maratón.\n"
        "- Solo usa la historia de la propia demanda y el calendario: **no sabe de clima, conciertos ni "
        "cierres de calles**.\n"
        "- Las zonas con menos de 3,000 viajes al mes **no tienen pronóstico**; casi todas están fuera de "
        "Manhattan.\n"
        f'- El rango del 80% acierta {m["cobertura_80"]:.0f}% en promedio, pero varía por zona: de '
        f'{m["cobertura_zona_min"]:.0f}% a {m["cobertura_zona_max"]:.0f}%.'
    )

with st.container(border=True, key="card-usos"):
    st.subheader(":material/block: Usos no recomendados")
    st.markdown(
        "- Decidir **qué conductores trabajan** o evaluar su desempeño con este pronóstico.\n"
        "- Recortar el servicio en zonas periféricas porque “el modelo predice poca demanda”: en esos "
        "barrios se usan más los taxis verdes y las apps, que no están en estos datos. **Poca demanda de "
        "taxi amarillo no significa poca necesidad de transporte.**\n"
        "- Usarlo más de un día hacia adelante: está entrenado para el día siguiente."
    )
