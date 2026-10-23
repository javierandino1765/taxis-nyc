"""Página 1 · Pronóstico de demanda (Parte 1)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

import comun

info = comun.barra_lateral_api()


@st.dialog("¿Cómo leer este pronóstico?")   # función avanzada: @st.dialog
def ayuda():
    st.markdown(
        "- La **línea** es el pronóstico central (mediana): la mitad de las veces la demanda "
        "real queda arriba y la mitad abajo.\n"
        "- La **banda** va del cuantil 10% al 90%: en 8 de cada 10 horas la demanda real cae dentro.\n"
        "- Los **puntos** son los viajes que de verdad ocurrieron (no existen para mañana).\n"
        "- Una banda ancha no es un error del modelo: es una hora **difícil de predecir**, y conviene saberlo."
    )


col_t, col_b = st.columns([0.78, 0.22], vertical_alignment="top")
with col_t:
    comun.encabezado("Pronóstico de demanda",
                     "Viajes por hora que se esperan en una zona, con su rango de incertidumbre. "
                     "El modelo vive en la API.")
col_b.write("")
if col_b.button("Cómo leerlo", icon=":material/help:", width="content"):
    ayuda()

comun.exigir_api(info)

with st.container(border=True, key="card-toolbar"):
    c1, _ = st.columns([0.5, 0.5])
    with c1:
        zona = comun.selector_zona(info)
    fecha = comun.selector_fecha(info)

# --- Pedir el pronóstico a la API ---
try:
    datos = comun.get_pronostico(zona["id"], fecha)
except requests.RequestException as e:
    st.error("La API no respondió a tiempo. Intenta de nuevo en un minuto.")
    st.stop()

h = pd.DataFrame(datos["horas"])
cu = pd.json_normalize(h["cuantiles"])     # columnas p10..p90
h = pd.concat([h.drop(columns="cuantiles"), cu], axis=1)
hay_real = h["real"].notna().any()

# --- Indicadores del día (mismas cifras de siempre, en una sola banda) ---
viajes_dia = float(h["p50"].sum())
sem_dia = float(h["hace_una_semana"].sum()) if h["hace_una_semana"].notna().any() else None
hora_pico = int(h.loc[h["p50"].idxmax(), "hora"])
viajes_pico = float(h.loc[h["p50"].idxmax(), "p50"])
rango_bajo, rango_alto = float(h["p10"].sum()), float(h["p90"].sum())
if hay_real:
    err = float((h["real"] - h["p50"]).abs().mean())
    n_real = int(h["real"].sum())

if sem_dia:
    var = (viajes_dia - sem_dia) / sem_dia * 100
    tono = "up" if var >= 0.5 else ("down" if var <= -0.5 else "flat")
    nota_sem = comun.pill(f"{var:+.0f}% vs. hace una semana", tono)
else:
    nota_sem = ""

tipo = comun.tipo_de_zona(zona["id"])

comun.banda_kpis([
    {"lab": "Viajes esperados en el día", "val": comun._fmt(viajes_dia), "nota": nota_sem,
     "spark": comun.sparkline(h["p50"].tolist())},
    {"lab": "Hora pico", "val": f"{hora_pico:02d}:00",
     "nota": f"{viajes_pico:,.0f} viajes en esa hora"},
    {"lab": "Rango del día (80%)", "val": f"{rango_bajo:,.0f}–{rango_alto:,.0f}",
     "nota": "suma de los cuantiles 10% y 90% por hora"},
    {"lab": "Error promedio por hora",
     "val": f"{err:.1f}" if hay_real else "Pendiente", "unidad": " viajes" if hay_real else "",
     "nota": f"frente a {n_real:,} viajes reales" if hay_real else "pronóstico a futuro"},
])

# --- Gráfico con banda de incertidumbre (función avanzada: Plotly go.Scatter con fill) ---
# Interacción: un clic sobre una hora muestra su detalle al lado (st.plotly_chart con on_select).
panel = st.container(border=True, key="card-grafico")
t1, t2 = panel.columns([0.7, 0.3], vertical_alignment="center")
t1.subheader(f'{zona["nombre"]}, {comun._fmt_fecha(fecha)}')
if tipo:
    col_g = comun.color_grupos(comun.cargar_segmentacion()["nombre_grupo"].unique()).get(tipo, "#5A6470")
    t2.markdown(f'<p style="text-align:right;margin:0">{comun.chip(tipo, col_g)}</p>',
                unsafe_allow_html=True)

g_izq, g_der = panel.columns([0.68, 0.32], gap="medium")

fig = go.Figure()
fig.add_vrect(x0=hora_pico - 0.5, x1=hora_pico + 0.5, fillcolor="#1C2128", opacity=0.05, line_width=0)
fig.add_trace(go.Scatter(x=h["hora"], y=h["p90"], line=dict(width=0),
                         name="p90", showlegend=False, hoverinfo="skip"))
fig.add_trace(go.Scatter(x=h["hora"], y=h["p10"], line=dict(width=0), fill="tonexty",
                         fillcolor=comun.COLOR["banda"], name="Rango 10%–90%", hoverinfo="skip"))
fig.add_trace(go.Scatter(x=h["hora"], y=h["hace_una_semana"], mode="lines",
                         line=dict(dash="dot", color=comun.COLOR["semana"], width=2),
                         name="Hace una semana", hovertemplate="%{y:.0f}"))
fig.add_trace(go.Scatter(x=h["hora"], y=h["p50"], mode="lines+markers",
                         line=dict(color=comun.COLOR["asfalto"], width=3),
                         marker=dict(size=7, color=comun.COLOR["asfalto"], line=dict(color="#FFFFFF", width=1)),
                         name="Pronóstico (mediana)", hovertemplate="%{y:.0f}",
                         unselected=dict(marker=dict(opacity=0.35))))
if hay_real:
    fig.add_trace(go.Scatter(x=h["hora"], y=h["real"], mode="markers",
                             marker=dict(color=comun.COLOR["real"], size=8, line=dict(color="#FFFFFF", width=1)),
                             name="Real", hovertemplate="%{y:.0f}",
                             unselected=dict(marker=dict(opacity=0.35))))
fig.add_annotation(x=hora_pico, y=float(h["p90"].max()), yshift=16, showarrow=False,
                   text=f"Pico {hora_pico:02d}:00", bgcolor="#FFFFFF",
                   font=dict(size=12, color=comun.COLOR["asfalto"]))
fig.update_layout(height=430, xaxis_title="Hora del día", yaxis_title="Viajes",
                  xaxis=dict(dtick=2, range=[-0.6, 23.6]),
                  yaxis=dict(range=[0, float(max(h["p90"].max(), h["real"].max() if hay_real else 0)) * 1.15]),
                  legend=dict(orientation="h", y=-0.22, x=0), clickmode="event+select",
                  margin=dict(l=10, r=10, t=10, b=10))
with g_izq:
    evento = st.plotly_chart(comun.fig_taxis(fig), width="stretch", theme=None, config={"displayModeBar": False},
                             on_select="rerun", selection_mode="points", key="graf_pronostico")

hora_sel = comun.hora_elegida(evento, hora_pico)
fila = h.loc[h["hora"] == hora_sel].iloc[0]
real_h = None if pd.isna(fila["real"]) else float(fila["real"])
sem_h = None if pd.isna(fila["hace_una_semana"]) else float(fila["hace_una_semana"])
with g_der:
    st.markdown(
        f'<div class="tx-hour"><h5>{hora_sel:02d}:00 a {hora_sel:02d}:59</h5>'
        f'<p class="hint">{"Hora pico del día. " if hora_sel == hora_pico else ""}'
        f'Haz clic en otra hora del gráfico para verla aquí.</p>'
        f'<div class="big">{fila["p50"]:,.0f}<small>viajes esperados</small></div>'
        f'{comun.regla_rango(float(fila["p10"]), float(fila["p50"]), float(fila["p90"]), real_h, float(h["p90"].max()))}'
        f'<dl><dt>Rango 10%–90%</dt><dd>{fila["p10"]:,.0f}–{fila["p90"]:,.0f}</dd>'
        f'<dt>Real</dt><dd>{f"{real_h:,.0f}" if real_h is not None else "Pendiente"}</dd>'
        f'<dt>Hace una semana</dt><dd>{f"{sem_h:,.0f}" if sem_h is not None else "—"}</dd></dl></div>',
        unsafe_allow_html=True,
    )

# --- Tabla por hora con barras animadas (HTML propio: Streamlit dibuja st.dataframe como imagen
#     y sus barras no se pueden animar). Mismas columnas y mismas cifras que antes. ---
# Un interruptor (en vez de un desplegable): la tabla se crea al activarlo, así su animación
# arranca siempre, sin depender de cómo cada versión de Streamlit arma el desplegable.
if st.toggle("Ver la tabla por hora", key="ver_tabla"):
    tope = float(np.nanmax([h["p90"].max(), h["real"].max() if hay_real else 0])) or 1.0
    fmt = lambda v: "—" if pd.isna(v) else f"{v:,.0f}"
    filas = []
    for i, r in h.reset_index(drop=True).iterrows():
        ancho = max(0.0, min(100.0, float(r["p50"]) / tope * 100))
        filas.append(
            f'<tr style="--i:{i}"><td>{int(r["hora"])}:00</td><td>{fmt(r["p10"])}</td>'
            f'<td><div class="tx-barcell"><span class="tx-track"><span class="tx-fill" style="width:{ancho:.1f}%">'
            f'</span></span><span class="tx-num">{fmt(r["p50"])}</span></div></td>'
            f'<td>{fmt(r["p90"])}</td><td>{fmt(r["hace_una_semana"])}</td>'
            f'<td>{fmt(r["real"]) if hay_real else "Pendiente"}</td></tr>')
    st.markdown(
        '<div class="tx-tbl"><table><thead><tr><th>Hora</th><th>p10</th><th>Pronóstico (p50)</th>'
        '<th>p90</th><th>Hace 1 sem.</th><th>Real</th></tr></thead><tbody>'
        + "".join(filas) + '</tbody></table></div>',
        unsafe_allow_html=True,
    )
