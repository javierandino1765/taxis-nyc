"""Página 3 · Segmentación de zonas (Parte 2, K-Means + PCA)."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import comun

comun.barra_lateral_api()   # la segmentación no usa la API, pero mantenemos la barra

comun.encabezado("Segmentación de zonas",
                 "K-Means agrupa las zonas por cómo se usan los taxis: a qué hora, qué tan lejos, cuánto se "
                 "paga. PCA las resume en dos ejes para poder dibujarlas.")

seg = comun.cargar_segmentacion()
comun.exigir_datos(seg, "zonas_segmentadas.csv")
metricas = comun.cargar_metricas()

horas_cols = [f"h{i:02d}" for i in range(24)]
grupos = sorted(seg["nombre_grupo"].unique())
colores = comun.color_grupos(grupos)

# Filtro por grupo (función avanzada: st.pills, selección múltiple)
elegidos = st.pills("Grupos", grupos, selection_mode="multi", default=grupos)
if not elegidos:
    elegidos = grupos
vista = seg[seg["nombre_grupo"].isin(elegidos)].copy()

# Fichas por grupo (mismas cifras, ordenadas en cuadrícula)
fichas = []
for g in elegidos:
    sub = seg[seg["nombre_grupo"] == g]
    fichas.append(
        f'<div class="tx-group" style="--c:{colores[g]}"><p class="gname">{g}</p>'
        f'<div class="gcount">{len(sub)}<small>zonas</small></div>'
        f'<dl><div><dt>Viajes/día</dt><dd>{sub["viajes_dia"].sum():,.0f}</dd></div>'
        f'<div><dt>Distancia</dt><dd>{sub["dist_mediana"].median():.1f} mi</dd></div>'
        f'<div><dt>De noche</dt><dd>{sub["pct_22a5"].median():.0f}%</dd></div></dl></div>')
st.markdown(f'<div class="tx-groups" style="--n:{len(elegidos)}">{"".join(fichas)}</div>',
            unsafe_allow_html=True)

# PCA scatter con selección (función avanzada: st.plotly_chart(on_select="rerun"))
# Animación: los círculos aparecen grupo por grupo (CSS en comun.py, clave "pca").
with st.container(border=True, key="card-pca"):
    st.subheader("Mapa de zonas (PCA)")
    if metricas and metricas.get("pca_var_pct"):
        st.caption(f'Los dos componentes conservan el **{metricas["pca_var_pct"]:.0f}%** de la variación.')
    fig = px.scatter(vista, x="pca1", y="pca2", color="nombre_grupo",
                     size="viajes_dia", size_max=28, color_discrete_map=colores,
                     custom_data=["zona_id"], hover_name="nombre",
                     labels={"pca1": "Componente 1", "pca2": "Componente 2",
                             "nombre_grupo": "Grupo"})
    fig.update_traces(marker=dict(line=dict(color="#FFFFFF", width=1), opacity=0.85))
    fig.update_layout(height=460, hovermode="closest", legend_title_text="")
    ev = st.plotly_chart(comun.fig_taxis(fig), width="stretch", on_select="rerun", key="pca", theme=None)
    st.caption("Selecciona zonas en el gráfico (clic, caja o lazo) para verlas en la tabla.")

seleccion = []
if ev and ev.get("selection") and ev["selection"].get("points"):
    seleccion = [int(p["customdata"][0]) for p in ev["selection"]["points"]]

# Perfil horario, debajo del mapa. Animación: las líneas se dibujan una por una (clave "graf_perfil").
with st.container(border=True, key="card-perfil"):
    st.subheader("Perfil horario de los grupos")
    perfil_grupo = (seg.groupby("nombre_grupo")[horas_cols].mean().T)
    perfil_grupo.index = range(24)
    fig_p = go.Figure()
    for g in elegidos:
        fig_p.add_trace(go.Scatter(x=perfil_grupo.index, y=perfil_grupo[g], mode="lines", name=g,
                                   line=dict(color=colores[g], width=2.5),
                                   hovertemplate="%{y:.3f}"))
    fig_p.update_layout(height=380, xaxis_title="Hora del día", yaxis_title="Proporción de viajes",
                        xaxis=dict(dtick=2), legend=dict(orientation="h", y=-0.25, x=0),
                        hovermode="x unified")
    st.plotly_chart(comun.fig_taxis(fig_p), width="stretch", theme=None,
                    config={"displayModeBar": False}, key="graf_perfil")

# Detalle por zona: tabla propia (HTML) para poder animar barras y mini líneas.
# Mismas columnas y cifras que la tabla anterior; se filtra con la selección del mapa.
st.subheader("Detalle por zona")
detalle = vista[vista["zona_id"].isin(seleccion)] if seleccion else vista
detalle = detalle.sort_values("viajes_dia", ascending=False).reset_index(drop=True)
tope_v = float(seg["viajes_dia"].max()) or 1.0


def _mini_linea(vals):
    vals = [float(v) for v in vals]
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    pts = " ".join(f"{i * 100 / 23:.2f},{22 - (v - lo) / rng * 18:.2f}" for i, v in enumerate(vals))
    return (f'<svg class="tx-spk" viewBox="0 0 100 24" preserveAspectRatio="none" aria-hidden="true">'
            f'<polyline points="{pts}" fill="none" stroke="#1C2128" stroke-width="1.5" '
            f'vector-effect="non-scaling-stroke" stroke-linejoin="round"/></svg>')


filas = []
for i, r in detalle.iterrows():
    ancho = max(0.0, min(100.0, float(r["viajes_dia"]) / tope_v * 100))
    filas.append(
        f'<tr style="--i:{min(i, 18)}"><td>{r["nombre"]}</td><td>{r["distrito"]}</td>'
        f'<td><span class="tx-dot" style="background:{colores.get(r["nombre_grupo"], "#5A6470")}"></span> '
        f'{r["nombre_grupo"]}</td>'
        f'<td><div class="tx-barcell"><span class="tx-track"><span class="tx-fill" style="width:{ancho:.1f}%">'
        f'</span></span><span class="tx-num">{r["viajes_dia"]:,.0f}</span></div></td>'
        f'<td>{r["dist_mediana"]:.1f} mi</td><td>{r["pct_22a5"]:.0f}%</td>'
        f'<td>${r["propina_mediana"]:.2f}</td><td>{_mini_linea(r[horas_cols].tolist())}</td></tr>')
st.markdown(
    '<div class="tx-tbl tx-tbl-scroll tx-tbl-zonas"><table><thead><tr><th>Zona</th><th>Distrito</th>'
    '<th>Grupo</th><th>Viajes al día</th><th>Distancia mediana</th><th>Viajes de noche</th>'
    '<th>Propina mediana</th><th>Perfil de 0 a 23 h</th></tr></thead><tbody>'
    + "".join(filas) + '</tbody></table></div>',
    unsafe_allow_html=True,
)
st.caption(f"{len(detalle)} zonas" + (" seleccionadas en el mapa." if seleccion else ", ordenadas por viajes al día."))

# Justificar k (función avanzada: st.expander). Línea de tendencia con k = 4 resaltado.
if metricas and metricas.get("silueta_por_k"):
    with st.expander("¿Por qué 4 grupos? (coeficiente de silueta para k = 2 a 7)",
                     icon=":material/science:"):
        sil = pd.DataFrame({"k": [int(k) for k in metricas["silueta_por_k"]],
                            "silueta": list(metricas["silueta_por_k"].values())}).set_index("k")
        fig_s = go.Figure()
        fig_s.add_trace(go.Scatter(x=sil.index, y=sil["silueta"], mode="lines+markers",
                                   line=dict(color=comun.COLOR["asfalto"], width=3),
                                   marker=dict(size=9, color=comun.COLOR["asfalto"],
                                               line=dict(color="#FFFFFF", width=1.5)),
                                   name="Silueta", hovertemplate="k = %{x}: %{y:.3f}<extra></extra>"))
        if 4 in sil.index:
            fig_s.add_trace(go.Scatter(x=[4], y=[sil.loc[4, "silueta"]], mode="markers+text",
                                       marker=dict(size=17, color=comun.COLOR["amarillo"],
                                                   line=dict(color=comun.COLOR["asfalto"], width=2)),
                                       text=[f"k = 4 (elegido): {sil.loc[4, 'silueta']:.2f}"],
                                       textposition="top center", textfont=dict(size=13),
                                       name="Elegido", hoverinfo="skip"))
        lo, hi = float(sil["silueta"].min()), float(sil["silueta"].max())
        fig_s.update_layout(height=300, xaxis_title="k (número de grupos)", yaxis_title="Silueta",
                            hovermode="closest", showlegend=False, xaxis=dict(dtick=1),
                            yaxis=dict(range=[lo - (hi - lo) * 0.6, hi + (hi - lo) * 0.9]))
        st.plotly_chart(comun.fig_taxis(fig_s), width="stretch", theme=None,
                        config={"displayModeBar": False}, key="graf_silueta")
        st.caption("En nuestros datos la silueta es más alta justo en k = 4 (0.41): la métrica y el "
                   "negocio coinciden. Cuatro grupos dan la mejor separación y, a la vez, una "
                   "estrategia comercial accionable.")
