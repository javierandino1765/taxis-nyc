"""Página 5 · Monitoreo (extra, +10). Mide el error día a día y avisa cuando pasa un límite."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

import comun

info = comun.barra_lateral_api()

comun.encabezado("Monitoreo del modelo",
                 "Vigila el error del pronóstico día a día en la semana de prueba y enciende una alarma cuando "
                 "el modelo se desvía demasiado. Es la señal para que una persona tome el control.")

comun.exigir_api(info)

c1, c2, c3 = st.columns(3)
with c1:
    zona = comun.selector_zona(info)
umbral = c2.slider("Umbral de alarma (error relativo)", 10, 100, 30, step=5,
                   help="Si el error supera este % del pronóstico…") / 100
horas_seg = c3.slider("…durante cuántas horas seguidas", 1, 6, 3)

fechas_reales = [f for f in info["fechas"] if f != "2024-02-01"]

# Traer la semana de prueba (hasta 7 llamadas, cacheadas)
filas = []
with st.status("Consultando la semana de prueba…", expanded=False) as s:
    try:
        for f in fechas_reales:
            d = comun.get_pronostico(zona["id"], f)
            for hr in d["horas"]:
                filas.append({"fecha": f, "hora": hr["hora"],
                              "real": hr["real"], "p50": hr["cuantiles"]["p50"]})
        s.update(label="Semana consultada", state="complete")
    except requests.RequestException:
        s.update(label="La API no respondió", state="error")
        st.stop()

sem = pd.DataFrame(filas).dropna(subset=["real"])
sem["abs_err"] = (sem["real"] - sem["p50"]).abs()

# Error día a día
diario = sem.groupby("fecha")["abs_err"].mean().reset_index()
diario["etiqueta"] = diario["fecha"].map(comun._fmt_fecha)
limite = st.slider("Límite de error diario (viajes/hora)", 1, 60,
                   int(np.ceil(diario["abs_err"].mean() * 1.5)))
diario["supera"] = diario["abs_err"] > limite

fig = px.bar(diario, x="etiqueta", y="abs_err", color="supera",
             color_discrete_map={True: comun.COLOR["real"], False: comun.COLOR["asfalto"]},
             labels={"etiqueta": "Día", "abs_err": "Error medio (viajes/hora)", "supera": "Supera límite"})
fig.add_hline(y=limite, line_dash="dash", line_color=comun.COLOR["amarillo"], line_width=2,
              annotation_text="límite", annotation_font_color=comun.COLOR["texto_suave"])
fig.update_layout(height=340, showlegend=False, hovermode="closest")
st.plotly_chart(comun.fig_taxis(fig), width="stretch", theme=None, config={"displayModeBar": False})

dias_alarma = diario.loc[diario["supera"], "etiqueta"].tolist()
if dias_alarma:
    st.warning(f"Días que superan el límite de {limite} viajes/hora: **{', '.join(dias_alarma)}**.", icon=":material/warning:")
    st.toast("Alarma: el modelo se desvió en al menos un día.", icon="⚠️")
else:
    st.success(f"Ningún día superó el límite de {limite} viajes/hora en esta zona.")

# Alarma por horas seguidas de error relativo alto
st.subheader("Alarma por horas seguidas")
sem = sem.sort_values(["fecha", "hora"]).reset_index(drop=True)
sem["error_rel"] = sem["abs_err"] / sem["p50"].clip(lower=1)
sem["pasa"] = sem["error_rel"] > umbral
sem["alarma"] = sem["pasa"].rolling(horas_seg).sum() == horas_seg
sem["momento"] = sem["fecha"].map(comun._fmt_fecha) + " " + sem["hora"].astype(str) + "h"

n_alarmas = int(sem["alarma"].sum())
st.caption(f"Se enciende cuando el error relativo supera {umbral*100:.0f}% durante {horas_seg} horas "
           f"seguidas. Veces encendida esta semana: **{n_alarmas}**.")
# Línea de alarma. Animación: se dibuja de izquierda a derecha como un monitor en vivo y cada
# tramo con alarma destella cuando la línea llega a él (CSS en comun.py, clave "graf_alarma").
alarma = sem["alarma"].astype(int).to_numpy()
n_pts = len(sem)
fig2 = go.Figure(go.Scatter(x=list(range(n_pts)), y=alarma, mode="lines", line_shape="hv",
                            line=dict(color=comun.COLOR["real"], width=2), customdata=sem["momento"],
                            hovertemplate="%{customdata}: %{y}<extra></extra>", name="Alarma"))
tramos = []           # (inicio, fin) de cada tramo con alarma encendida
ini = None
for i, v in enumerate(alarma):
    if v and ini is None:
        ini = i
    if (not v or i == n_pts - 1) and ini is not None:
        tramos.append((ini, i if v else i - 1))
        ini = None
for t0, t1 in tramos:
    fig2.add_vrect(x0=t0 - 0.15, x1=t1 + 1.15, fillcolor=comun.COLOR["amarillo"], opacity=0.35,
                   line_width=0, layer="below")
fig2.update_layout(height=260, showlegend=False, hovermode="closest", xaxis_title="Momento",
                   yaxis=dict(tickvals=[0, 1], ticktext=["ok", "alarma"], range=[-0.1, 1.15]),
                   xaxis=dict(range=[-0.5, n_pts - 0.5]))
fig2.update_xaxes(showticklabels=False)
DUR_ALARMA = 2.8   # segundos que tarda la línea en recorrer la semana
# Plotly pone cada franja en su propio grupo: se elige el grupo número k de la capa de figuras.
reglas = [f".st-key-graf_alarma .layer-below .shapelayer > :nth-child({k + 1}) path, "
          f".st-key-graf_alarma .layer-below .shapelayer > path:nth-child({k + 1}) "
          f"{{ animation: tx-destello 1.2s ease {DUR_ALARMA * (t0 / max(n_pts - 1, 1)):.2f}s both; }}"
          for k, (t0, _) in enumerate(tramos)]
if reglas:
    st.markdown("<style>" + "\n".join(reglas) + "</style>", unsafe_allow_html=True)
st.plotly_chart(comun.fig_taxis(fig2), width="stretch", theme=None, config={"displayModeBar": False},
                key="graf_alarma")

st.caption("El umbral (porcentaje y horas) es una decisión: muy sensible y la alarma “grita” tanto que "
           "nadie le hace caso; muy laxa y llega tarde.")
