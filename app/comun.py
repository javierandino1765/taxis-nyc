"""Funciones compartidas por todas las páginas de la app.

Aquí viven: la dirección de la API (desde st.secrets, sin tocar el código),
las llamadas cacheadas a la API, el manejo de errores cuando la API no responde,
la carga de los CSV precalculados y el selector de zona que se recuerda entre páginas.
"""
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import requests
import streamlit as st

DATA = Path(__file__).parent / "data"
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
ZONA_INICIAL = 161   # Midtown Center: la app abre en una zona con movimiento


# ------------------------- Identidad visual -------------------------
# Paleta "Taxis NYC": asfalto, amarillo taxi y colores de señal para los datos.
COLOR = {
    "asfalto": "#1C2128",
    "amarillo": "#F2B705",
    "banda": "rgba(242, 183, 5, 0.28)",
    "real": "#D2333F",
    "semana": "#8A929C",
    "rejilla": "#E3E6EA",
    "texto_suave": "#5A6470",
    "bien": "#1A8F7A",
}
COLORES_GRUPO = ["#2B59C3", "#7B4FBF", "#C98A00", "#1A8F7A", "#D2333F", "#5A6470"]

pio.templates["taxis"] = go.layout.Template(
    layout=go.Layout(
        font=dict(family="Barlow, sans-serif", size=13, color=COLOR["asfalto"]),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=COLORES_GRUPO,
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor=COLOR["rejilla"],
                        font=dict(family="Barlow, sans-serif", color=COLOR["asfalto"])),
        xaxis=dict(showgrid=False, linecolor="#C9CED4", ticks="outside", tickcolor="#C9CED4",
                   title=dict(font=dict(color=COLOR["texto_suave"]))),
        yaxis=dict(gridcolor=COLOR["rejilla"], zeroline=False,
                   title=dict(font=dict(color=COLOR["texto_suave"]))),
        legend=dict(orientation="h", y=-0.22, x=0, font=dict(color=COLOR["texto_suave"])),
        margin=dict(l=10, r=10, t=10, b=10),
    )
)
pio.templates.default = "plotly_white+taxis"


def fig_taxis(fig):
    """Aplica la identidad de la app a una figura de Plotly.
    Los valores se fijan en el layout para que el tema de Streamlit no los reemplace."""
    fig.update_layout(template="plotly_white+taxis")
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Barlow, sans-serif", size=13, color=COLOR["asfalto"]),
    )
    fig.update_yaxes(gridcolor=COLOR["rejilla"], zeroline=False)
    fig.update_xaxes(linecolor="#C9CED4")
    return fig

_CSS = """
<style>
/* Encabezado de página con la franja de cuadros del checker cab */
.tx-head { margin: 0 0 0.35rem 0; }
.tx-checker {
  width: 9.5rem; height: 0.9rem; margin-bottom: 0.2rem; border-radius: 2px;
  background:
    conic-gradient(#1C2128 25%, #F2B705 0 50%, #1C2128 0 75%, #F2B705 0)
    0 0 / 0.9rem 0.9rem;
}
.tx-head h1.tx-title, .tx-title {
  font-family: "Barlow Condensed", sans-serif; font-weight: 700;
  font-size: clamp(2.2rem, 4vw, 3.1rem); line-height: 1; letter-spacing: -0.01em;
  color: #1C2128; margin: 0 0 0.55rem 0; padding: 0;
}
.tx-lede { color: #5A6470; font-size: 1.02rem; line-height: 1.5; max-width: 46rem; margin: 0; }

/* Métricas y paneles sobre blanco para separarlos del fondo */
[data-testid="stMain"] [data-testid="stMetric"] { background: #FFFFFF; }
[data-testid="stMain"] [class*="st-key-card-"] { background: #FFFFFF; padding: 1.1rem 1.25rem; }
[data-testid="stMetricLabel"] p { color: #5A6470; font-weight: 500; }

/* Respuesta principal de la página de decisión */
.tx-answer {
  background: #1C2128; color: #FFFFFF; border-radius: 0.45rem;
  padding: 1.25rem 1.5rem; border-left: 0.55rem solid #F2B705; margin: 0.4rem 0 0.6rem 0;
}
.tx-answer .tx-kicker { color: #C9CED4; font-size: 0.95rem; margin: 0 0 0.25rem 0; }
.tx-answer .tx-big {
  font-family: "Barlow Condensed", sans-serif; font-weight: 700;
  font-size: clamp(2rem, 3.6vw, 2.8rem); line-height: 1.05; margin: 0;
}
.tx-answer .tx-sub { color: #E6E8EB; margin: 0.45rem 0 0 0; font-size: 1rem; }

/* Etiqueta del tipo de zona y chips de grupo */
.tx-chip {
  display: inline-flex; align-items: center; gap: 0.45rem; font-size: 0.9rem;
  color: #1C2128; background: #FFFFFF; border: 1px solid #D9DDE2;
  border-radius: 999px; padding: 0.2rem 0.75rem 0.2rem 0.55rem;
}
.tx-dot { width: 0.6rem; height: 0.6rem; border-radius: 50%; display: inline-block; }

/* Marca en la barra lateral */
.tx-brand { display: flex; align-items: center; gap: 0.6rem; margin: 0.2rem 0 0.15rem 0; }
.tx-brand .tx-mark {
  width: 1.7rem; height: 1.7rem; border-radius: 3px; flex: none;
  background: conic-gradient(#1C2128 25%, #F2B705 0 50%, #1C2128 0 75%, #F2B705 0) 0 0 / 0.85rem 0.85rem;
  outline: 2px solid #F2B705; outline-offset: -2px;
}
.tx-brand .tx-name {
  font-family: "Barlow Condensed", sans-serif; font-weight: 700; font-size: 1.45rem;
  color: #FFFFFF; line-height: 1;
}
.tx-brand-sub { color: #9AA3AD; font-size: 0.88rem; margin: 0 0 0.6rem 0; }

/* ---------- v3: composición editorial ---------- */
[data-testid="stMainBlockContainer"] { max-width: 1320px; padding-top: 2.4rem; }
.tx-head { padding-bottom: 0.6rem; }

/* Banda de indicadores */
.tx-kpis {
  display: grid; grid-template-columns: repeat(var(--n, 4), minmax(0, 1fr));
  background: #FFFFFF; border: 1px solid #D9DDE2; border-radius: 0.45rem; margin: 0.6rem 0 1rem 0;
}
.tx-kpi { padding: 1.05rem 1.35rem 1rem 1.35rem; border-left: 1px solid #E3E6EA; min-width: 0; }
.tx-kpi:first-child { border-left: 0; }
.tx-kpi .lab { color: #5A6470; font-size: 0.9rem; margin: 0 0 0.35rem 0; }
.tx-kpi .val {
  font-family: "Barlow Condensed", sans-serif; font-weight: 600; font-size: 2.15rem;
  line-height: 1.05; color: #1C2128; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.tx-kpi .val small { font-size: 1.15rem; font-weight: 500; color: #5A6470; margin-left: 0.2rem; }
.tx-kpi .note { color: #5A6470; font-size: 0.86rem; margin-top: 0.4rem; }
.tx-kpi .spark { display: block; margin-top: 0.55rem; width: 100%; height: 34px; }
.tx-pill { display: inline-block; border-radius: 999px; padding: 0.05rem 0.55rem; font-size: 0.82rem; }
.tx-pill.up { background: #E7F4F1; color: #136B5B; }
.tx-pill.down { background: #FBE9EA; color: #A3202B; }
.tx-pill.flat { background: #EEF0F2; color: #5A6470; }
@media (max-width: 900px) {
  .tx-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .tx-kpi:nth-child(3) { border-left: 0; }
  .tx-kpi:nth-child(n+3) { border-top: 1px solid #E3E6EA; }
}

/* Respuesta de la página de decisión, con datos clave */
.tx-answer { display: grid; grid-template-columns: minmax(0, 2.3fr) repeat(3, minmax(0, 1fr)); gap: 0;
  padding: 0; overflow: hidden; }
.tx-answer > div { padding: 1.35rem 1.5rem; }
.tx-answer .tx-stat { border-left: 1px solid #343C46; }
.tx-answer .tx-stat .lab { color: #9AA3AD; font-size: 0.88rem; margin: 0 0 0.3rem 0; }
.tx-answer .tx-stat .val { font-family: "Barlow Condensed", sans-serif; font-weight: 600;
  font-size: 1.9rem; line-height: 1.05; color: #FFFFFF; }
.tx-answer .tx-stat .val.hi { color: #F2B705; }
@media (max-width: 900px) { .tx-answer { grid-template-columns: 1fr 1fr; }
  .tx-answer > div:first-child { grid-column: 1 / -1; } .tx-answer .tx-stat:nth-child(2) { border-left: 0; } }

/* Comparación de costos en barras */
.tx-cmp { background: #FFFFFF; border: 1px solid #D9DDE2; border-radius: 0.45rem; padding: 1.15rem 1.35rem; }
.tx-cmp h4 { font-family: "Barlow Condensed", sans-serif; font-weight: 600; font-size: 1.35rem; margin: 0 0 0.9rem 0; }
.tx-row { display: grid; grid-template-columns: minmax(10rem, 15rem) minmax(0, 1fr) 6.5rem 12rem;
  align-items: center; gap: 1rem; padding: 0.55rem 0; border-top: 1px solid #EEF0F2; }
.tx-row:first-of-type { border-top: 0; }
.tx-row .name { font-weight: 500; }
.tx-row .name span { display: block; color: #5A6470; font-size: 0.84rem; font-weight: 400; }
.tx-row .track { height: 0.8rem; background: #EEF0F2; border-radius: 999px; overflow: hidden; }
.tx-row .bar { height: 100%; background: #9AA3AD; border-radius: 999px; }
.tx-row.best .bar { background: #F2B705; }
.tx-row .amt { font-family: "Barlow Condensed", sans-serif; font-weight: 600; font-size: 1.45rem; text-align: right; }
.tx-row .dif { text-align: right; white-space: nowrap; }
@media (max-width: 760px) { .tx-row { grid-template-columns: 1fr auto; } .tx-row .track { grid-column: 1 / -1; order: 3; } }

/* Fichas de grupo (segmentación) */
.tx-groups { display: grid; grid-template-columns: repeat(var(--n, 4), minmax(0, 1fr)); gap: 0.9rem; margin: 0.4rem 0 1rem 0; }
.tx-group { background: #FFFFFF; border: 1px solid #D9DDE2; border-radius: 0.45rem; padding: 1rem 1.15rem;
  border-top: 0.3rem solid var(--c); }
.tx-group .gname { font-weight: 600; font-size: 1.02rem; margin: 0; }
.tx-group .gcount { font-family: "Barlow Condensed", sans-serif; font-weight: 600; font-size: 2.3rem; line-height: 1;
  margin: 0.55rem 0 0.15rem 0; }
.tx-group .gcount small { font-size: 1rem; font-weight: 500; color: #5A6470; margin-left: 0.25rem; }
.tx-group dl { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.5rem; margin: 0.8rem 0 0 0;
  padding-top: 0.7rem; border-top: 1px solid #EEF0F2; }
.tx-group dt { color: #5A6470; font-size: 0.78rem; }
.tx-group dd { margin: 0.1rem 0 0 0; font-weight: 600; font-size: 0.98rem; }
@media (max-width: 900px) { .tx-groups { grid-template-columns: repeat(2, minmax(0, 1fr)); } }

/* Barra de herramientas */
[data-testid="stMain"] .st-key-card-toolbar { padding: 0.85rem 1.25rem 0.95rem 1.25rem; }

/* ---------- v4: sin choques entre elementos (se adaptan al ancho real) ---------- */
[data-testid="stMarkdownContainer"]:has(> .tx-kpis),
[data-testid="stMarkdownContainer"]:has(> .tx-answer),
[data-testid="stMarkdownContainer"]:has(> .tx-groups),
[data-testid="stMarkdownContainer"]:has(> .tx-cmp) { container-type: inline-size; }
.tx-kpi .val { font-size: clamp(1.55rem, 3.2cqi, 2.15rem); }
.tx-kpi .lab, .tx-kpi .note { overflow-wrap: anywhere; }
.tx-pill { white-space: nowrap; }
@container (max-width: 860px) {
  .tx-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .tx-kpi { border-left: 0; border-top: 1px solid #E3E6EA; }
  .tx-kpi:nth-child(-n+2) { border-top: 0; }
  .tx-kpi:nth-child(even) { border-left: 1px solid #E3E6EA; }
  .tx-kpi .val { font-size: 1.9rem; }
  .tx-answer { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .tx-answer > div:first-child { grid-column: 1 / -1; border-bottom: 1px solid #343C46; }
  .tx-answer .tx-stat:nth-child(2) { border-left: 0; }
  .tx-groups { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .tx-row { grid-template-columns: minmax(0, 1fr) auto; row-gap: 0.4rem; }
  .tx-row .track { grid-column: 1 / -1; order: 3; }
  .tx-row .dif { grid-column: 1 / -1; order: 4; text-align: left; }
}
@container (max-width: 480px) {
  .tx-kpis, .tx-groups { grid-template-columns: 1fr; }
  .tx-kpi:nth-child(even) { border-left: 0; }
  .tx-kpi:nth-child(2) { border-top: 1px solid #E3E6EA; }
  .tx-answer { grid-template-columns: 1fr; }
  .tx-answer .tx-stat { border-left: 0; border-top: 1px solid #343C46; }
}

/* Detalle de la hora elegida en el gráfico */
.tx-hour h5 { font-family: "Barlow Condensed", sans-serif; font-weight: 600; font-size: 1.35rem; margin: 0 0 0.15rem 0; }
.tx-hour .hint { color: #5A6470; font-size: 0.85rem; margin: 0 0 0.9rem 0; }
.tx-hour .big { font-family: "Barlow Condensed", sans-serif; font-weight: 600; font-size: 2.4rem; line-height: 1; }
.tx-hour .big small { font-size: 1rem; color: #5A6470; font-weight: 500; margin-left: 0.25rem; }
.tx-range { position: relative; height: 2.6rem; margin: 1rem 0 0.4rem 0; }
.tx-range .rail { position: absolute; left: 0; right: 0; top: 1.1rem; height: 0.4rem; background: #EEF0F2; border-radius: 999px; }
.tx-range .band { position: absolute; top: 1.1rem; height: 0.4rem; background: #F2B705; border-radius: 999px; }
.tx-range .mark { position: absolute; top: 0.7rem; width: 2px; height: 1.2rem; background: #1C2128; transform: translateX(-1px); }
.tx-range .dot { position: absolute; top: 1.05rem; width: 0.7rem; height: 0.7rem; border-radius: 50%;
  background: #D2333F; border: 2px solid #FFFFFF; transform: translateX(-50%); }
.tx-range .tick { position: absolute; top: 2rem; font-size: 0.75rem; color: #5A6470; transform: translateX(-50%); white-space: nowrap; }
.tx-hour dl { display: grid; grid-template-columns: auto 1fr; gap: 0.35rem 1rem; margin: 1rem 0 0 0;
  padding-top: 0.8rem; border-top: 1px solid #EEF0F2; }
.tx-hour dt { color: #5A6470; font-size: 0.9rem; }
.tx-hour dd { margin: 0; text-align: right; font-weight: 600; white-space: nowrap; }
.tx-hour dt { min-width: 0; }

/* Tarjetas de las cuatro preguntas (inicio) */
.tx-q p.tx-q-num { display: flex; align-items: center; gap: 0.55rem; color: #5A6470; font-weight: 500; margin: 0 0 0.6rem 0; }
.tx-q-num span { display: inline-grid; place-items: center; width: 1.55rem; height: 1.55rem; border-radius: 50%;
  background: #1C2128; color: #F2B705; font-family: "Barlow Condensed", sans-serif; font-weight: 700; font-size: 0.95rem; }
.tx-q-dot { display: inline-block; width: 0.8rem; height: 0.8rem; border-radius: 50%; margin-right: 0.5rem; vertical-align: 0.25rem; }
.tx-q p.tx-q-big { font-family: "Barlow Condensed", sans-serif; font-weight: 700; font-size: clamp(1.8rem, 3vw, 2.4rem);
  line-height: 1.05; color: #1C2128; margin: 0 0 0.45rem 0; }
.tx-q p.tx-q-txt { color: #3A424D; line-height: 1.5; margin: 0 0 0.3rem 0; max-width: 34rem; }
[class*="st-key-card-q"] [data-testid="stPageLink"] a { padding-left: 0; }
[class*="st-key-card-q"] [data-testid="stPageLink"] p { font-weight: 600; }

/* ---------- Animación de entrada de los gráficos ---------- */
@keyframes tx-crecer-y { from { transform: scaleY(0); } to { transform: scaleY(1); } }
@keyframes tx-crecer-x { from { transform: scaleX(0); } to { transform: scaleX(1); } }
@keyframes tx-aparecer { from { opacity: 0; } to { opacity: 1; } }

/* Líneas y bandas: se revelan de izquierda a derecha, como si se dibujaran */
@keyframes tx-barrido { from { clip-path: inset(-10% 100% -10% 0); } to { clip-path: inset(-10% -2% -10% 0); } }
.js-plotly-plot .scatterlayer .trace { animation: tx-barrido 1.5s cubic-bezier(.4, 0, .2, 1) both; }
/* Puntos: aparecen cuando la línea ya está dibujada */
.js-plotly-plot .scatterlayer .points path { animation: tx-aparecer .45s ease 1.2s backwards; }
/* Barras verticales: crecen desde abajo, una tras otra */
.js-plotly-plot .barlayer .point path {
  transform-box: fill-box; transform-origin: 50% 100%;
  animation: tx-crecer-y .7s cubic-bezier(.2, .7, .2, 1) both;
}
.js-plotly-plot .barlayer .point:nth-child(1) path { animation-delay: 0.00s; }
.js-plotly-plot .barlayer .point:nth-child(2) path { animation-delay: 0.03s; }
.js-plotly-plot .barlayer .point:nth-child(3) path { animation-delay: 0.06s; }
.js-plotly-plot .barlayer .point:nth-child(4) path { animation-delay: 0.09s; }
.js-plotly-plot .barlayer .point:nth-child(5) path { animation-delay: 0.12s; }
.js-plotly-plot .barlayer .point:nth-child(6) path { animation-delay: 0.15s; }
.js-plotly-plot .barlayer .point:nth-child(7) path { animation-delay: 0.18s; }
.js-plotly-plot .barlayer .point:nth-child(8) path { animation-delay: 0.21s; }
.js-plotly-plot .barlayer .point:nth-child(9) path { animation-delay: 0.24s; }
.js-plotly-plot .barlayer .point:nth-child(10) path { animation-delay: 0.27s; }
.js-plotly-plot .barlayer .point:nth-child(11) path { animation-delay: 0.30s; }
.js-plotly-plot .barlayer .point:nth-child(12) path { animation-delay: 0.33s; }
.js-plotly-plot .barlayer .point:nth-child(13) path { animation-delay: 0.36s; }
.js-plotly-plot .barlayer .point:nth-child(14) path { animation-delay: 0.39s; }
.js-plotly-plot .barlayer .point:nth-child(15) path { animation-delay: 0.42s; }
.js-plotly-plot .barlayer .point:nth-child(16) path { animation-delay: 0.45s; }
.js-plotly-plot .barlayer .point:nth-child(17) path { animation-delay: 0.48s; }
.js-plotly-plot .barlayer .point:nth-child(18) path { animation-delay: 0.51s; }
.js-plotly-plot .barlayer .point:nth-child(19) path { animation-delay: 0.54s; }
.js-plotly-plot .barlayer .point:nth-child(20) path { animation-delay: 0.57s; }
.js-plotly-plot .barlayer .point:nth-child(21) path { animation-delay: 0.60s; }
.js-plotly-plot .barlayer .point:nth-child(22) path { animation-delay: 0.63s; }
.js-plotly-plot .barlayer .point:nth-child(23) path { animation-delay: 0.66s; }
.js-plotly-plot .barlayer .point:nth-child(24) path { animation-delay: 0.69s; }
/* Barras horizontales (Ficha del modelo): crecen desde la izquierda */
.st-key-card-reglas .js-plotly-plot .barlayer .point path,
.st-key-card-tipo .js-plotly-plot .barlayer .point path {
  transform-origin: 0% 50%; animation-name: tx-crecer-x;
}
.js-plotly-plot .barlayer .bartext { animation: tx-aparecer .4s ease .8s both; }

/* Quien prefiere menos movimiento lo ve todo de inmediato */
@media (prefers-reduced-motion: reduce) {
  .js-plotly-plot .scatterlayer .trace,
  .js-plotly-plot .scatterlayer .points path, .js-plotly-plot .barlayer .point path,
  .js-plotly-plot .barlayer .bartext { animation: none !important; }
}

/* ---------- Secuencia del gráfico de Pronóstico ----------
   Orden de las series en la figura: 1 p90 (invisible), 2 p10 + banda, 3 hace una semana,
   4 pronóstico (mediana), 5 real. Se revelan en este orden: mediana, punteada, puntos rojos, banda. */
.st-key-graf_pronostico .scatterlayer .trace:nth-child(4) {
  animation: tx-barrido 1.2s cubic-bezier(.4, 0, .2, 1) 0s both; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(4) .points path { animation: none; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(3) {
  animation: tx-barrido 1s cubic-bezier(.4, 0, .2, 1) 1s both; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) { animation: none; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path {
  animation: tx-aparecer .35s ease backwards; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(1) { animation-delay: 1.900s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(2) { animation-delay: 1.925s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(3) { animation-delay: 1.950s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(4) { animation-delay: 1.975s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(5) { animation-delay: 2.000s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(6) { animation-delay: 2.025s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(7) { animation-delay: 2.050s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(8) { animation-delay: 2.075s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(9) { animation-delay: 2.100s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(10) { animation-delay: 2.125s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(11) { animation-delay: 2.150s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(12) { animation-delay: 2.175s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(13) { animation-delay: 2.200s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(14) { animation-delay: 2.225s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(15) { animation-delay: 2.250s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(16) { animation-delay: 2.275s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(17) { animation-delay: 2.300s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(18) { animation-delay: 2.325s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(19) { animation-delay: 2.350s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(20) { animation-delay: 2.375s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(21) { animation-delay: 2.400s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(22) { animation-delay: 2.425s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(23) { animation-delay: 2.450s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(5) .points path:nth-child(24) { animation-delay: 2.475s; }
.st-key-graf_pronostico .scatterlayer .trace:nth-child(1),
.st-key-graf_pronostico .scatterlayer .trace:nth-child(2) { animation: tx-aparecer .8s ease 2.7s both; }

/* Mini gráfico de la banda de indicadores: la línea se dibuja y el área la acompaña */
.tx-kpi .spark { animation: tx-barrido 1.8s cubic-bezier(.4, 0, .2, 1) .3s both; }
.tx-kpi .spark polygon { animation: tx-aparecer 1.2s ease .9s both; }

/* Tabla por hora: se revela de izquierda a derecha al abrirla */
.tx-tbl { animation: tx-barrido 1s cubic-bezier(.4, 0, .2, 1) both; }

@media (prefers-reduced-motion: reduce) {
  .st-key-graf_pronostico .scatterlayer .trace, .st-key-graf_pronostico .scatterlayer .points path,
  .tx-kpi .spark, .tx-kpi .spark polygon, .tx-tbl, .tx-tbl .tx-fill { animation: none !important; }
}

/* Tabla por hora (Pronóstico): barras que crecen al abrir el desplegable */
.tx-tbl { overflow-x: auto; border: 1px solid #D9DDE2; border-radius: 0.45rem; background: #FFFFFF; }
.tx-tbl table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; margin: 0; }
.tx-tbl th { background: #F3F4F6; color: #5A6470; font-weight: 500;
  text-align: right; padding: 0.6rem 0.9rem; border-bottom: 1px solid #D9DDE2; white-space: nowrap; }
.tx-tbl th:nth-child(3), .tx-tbl td:nth-child(3) { text-align: left; min-width: 13rem; }
.tx-tbl td { text-align: right; padding: 0.5rem 0.9rem; border-bottom: 1px solid #EEF0F2; white-space: nowrap; border-left: 0; border-right: 0; }
.tx-tbl tr:last-child td { border-bottom: 0; }
.tx-tbl tbody tr:hover td { background: #FAFAF7; }
.tx-barcell { display: flex; align-items: center; gap: 0.7rem; }
.tx-track { flex: 1; height: 0.45rem; background: #EEF0F2; border-radius: 999px; overflow: hidden; }
.tx-fill { display: block; height: 100%; background: #1C2128; border-radius: 999px; transform-origin: left center; }
.tx-num { min-width: 2.6rem; text-align: right; }
@keyframes tx-barra { from { transform: scaleX(0); } to { transform: scaleX(1); } }
.tx-tbl .tx-fill {
  animation: tx-barra .8s cubic-bezier(.2, .7, .2, 1) both; animation-delay: calc(.25s + var(--i, 0) * .04s); }

/* ================= v7 ================= */
/* Animaciones en pausa hasta que el elemento aparece en pantalla */
html.tx-js :is(.js-plotly-plot, .tx-cmp, .tx-tbl, .tx-kpis, .tx-groups):not(.tx-visto),
html.tx-js :is(.js-plotly-plot, .tx-cmp, .tx-tbl, .tx-kpis, .tx-groups):not(.tx-visto) * {
  animation-play-state: paused !important; }
[data-testid="stSidebar"] [data-testid="stHtml"] { display: none; }

/* Decisión: comparación de costos (barras que crecen y se resaltan) */
.tx-cmp .tx-cmp-t { font-family: "Barlow Condensed", sans-serif; font-weight: 600; font-size: 1.35rem; margin: 0 0 0.9rem 0; }
.tx-row { margin: 0 -0.75rem; padding: 0.6rem 0.75rem; border-radius: 0.35rem;
  transition: background-color .2s ease; }
.tx-row:hover { background: #FAF6EA; }
.tx-row .track { transition: height .2s ease; }
.tx-row:hover .track { height: 1.05rem; }
.tx-row:nth-of-type(1) { --d: .15s; } .tx-row:nth-of-type(2) { --d: .45s; } .tx-row:nth-of-type(3) { --d: .75s; }
.tx-row .bar { transform-origin: left center; animation: tx-barra 1s cubic-bezier(.2, .7, .2, 1) var(--d, 0s) both; }
.tx-row .amt, .tx-row .dif { animation: tx-aparecer .5s ease calc(var(--d, 0s) + .75s) both; }
@keyframes tx-brillo { 0%, 100% { box-shadow: 0 0 0 0 rgba(242, 183, 5, 0); }
  40% { box-shadow: 0 0 0 6px rgba(242, 183, 5, 0.35); } }
.tx-row.best .track { animation: tx-brillo 1.2s ease calc(var(--d, 0s) + 1.1s) 1; }
.tx-row.best .name { font-weight: 600; }
.tx-row.best .amt { color: #1C2128; }

/* Segmentación: perfil horario, una línea tras otra */
.st-key-graf_perfil .scatterlayer .trace:nth-child(1) { animation: tx-barrido 1s cubic-bezier(.4, 0, .2, 1) 0.15s both; }
.st-key-graf_perfil .scatterlayer .trace:nth-child(2) { animation: tx-barrido 1s cubic-bezier(.4, 0, .2, 1) 1.10s both; }
.st-key-graf_perfil .scatterlayer .trace:nth-child(3) { animation: tx-barrido 1s cubic-bezier(.4, 0, .2, 1) 2.05s both; }
.st-key-graf_perfil .scatterlayer .trace:nth-child(4) { animation: tx-barrido 1s cubic-bezier(.4, 0, .2, 1) 3.00s both; }
.st-key-graf_perfil .scatterlayer .trace:nth-child(5) { animation: tx-barrido 1s cubic-bezier(.4, 0, .2, 1) 3.95s both; }
.st-key-graf_perfil .scatterlayer .trace:nth-child(6) { animation: tx-barrido 1s cubic-bezier(.4, 0, .2, 1) 4.90s both; }
/* Segmentación: mapa PCA, los círculos aparecen grupo por grupo */
@keyframes tx-materializar { from { opacity: 0; filter: blur(6px); } to { opacity: 1; filter: blur(0); } }
.st-key-pca .scatterlayer .trace { animation: none; }
.st-key-pca .scatterlayer .points path { animation: none; }
.st-key-pca .scatterlayer .trace:nth-child(1) .points { animation: tx-materializar .8s ease 0.10s backwards; }
.st-key-pca .scatterlayer .trace:nth-child(2) .points { animation: tx-materializar .8s ease 0.60s backwards; }
.st-key-pca .scatterlayer .trace:nth-child(3) .points { animation: tx-materializar .8s ease 1.10s backwards; }
.st-key-pca .scatterlayer .trace:nth-child(4) .points { animation: tx-materializar .8s ease 1.60s backwards; }
.st-key-pca .scatterlayer .trace:nth-child(5) .points { animation: tx-materializar .8s ease 2.10s backwards; }
.st-key-pca .scatterlayer .trace:nth-child(6) .points { animation: tx-materializar .8s ease 2.60s backwards; }
/* Segmentación: silueta, la línea se dibuja y luego aparece el punto elegido (k = 4) */
.st-key-graf_silueta .scatterlayer .trace:nth-child(1) { animation: tx-barrido 1.3s cubic-bezier(.4, 0, .2, 1) .1s both; }
.st-key-graf_silueta .scatterlayer .trace:nth-child(1) .points path { animation: none; }
.st-key-graf_silueta .scatterlayer .trace:nth-child(2) { animation: tx-aparecer .5s ease 1.3s both; }
.st-key-graf_silueta .scatterlayer .trace:nth-child(2) .points path { animation: none; }

/* Tabla de detalle por zona: con desplazamiento, encabezado fijo, mini líneas que se dibujan */
.tx-tbl-scroll { max-height: 30rem; overflow: auto; }
.tx-tbl-scroll th { position: sticky; top: 0; z-index: 1; }
.tx-tbl-zonas table { font-size: 0.92rem; }
.tx-tbl-zonas th, .tx-tbl-zonas td { padding: 0.45rem 0.6rem; }
.tx-tbl-zonas th { white-space: normal; line-height: 1.2; vertical-align: bottom; }
.tx-tbl-zonas td:nth-child(1) { white-space: normal; min-width: 9rem; }
.tx-tbl-zonas th:nth-child(-n+3), .tx-tbl-zonas td:nth-child(-n+3) { text-align: left; }
.tx-tbl-zonas th:nth-child(3), .tx-tbl-zonas td:nth-child(3) { min-width: 0; }
.tx-tbl-zonas th:nth-child(4), .tx-tbl-zonas td:nth-child(4) { text-align: left; min-width: 9rem; }
.tx-tbl-zonas .tx-barcell { gap: 0.5rem; }
.tx-tbl-zonas .tx-dot { margin-right: 0.3rem; vertical-align: 0.05rem; }
.tx-spk { display: block; width: 6.5rem; height: 1.6rem;
  animation: tx-barrido 1s cubic-bezier(.4, 0, .2, 1) calc(.35s + var(--i, 0) * .04s) both; }

/* Monitoreo: la alarma se dibuja como un monitor en vivo y los tramos encendidos destellan */
.st-key-graf_alarma .scatterlayer .trace { animation: tx-barrido 2.8s linear .05s both; }
@keyframes tx-destello { 0% { opacity: 0; } 30% { opacity: .95; } 55% { opacity: .2; } 75% { opacity: .85; } 100% { opacity: .35; } }

@media (prefers-reduced-motion: reduce) {
  .st-key-pca .scatterlayer .points, .st-key-graf_perfil .scatterlayer .trace,
  .st-key-graf_silueta .scatterlayer .trace, .st-key-graf_alarma .scatterlayer .trace,
  .st-key-graf_alarma .shapelayer path, .tx-spk, .tx-row .bar, .tx-row .amt, .tx-row .dif,
  .tx-row .track { animation: none !important; }
}

/* Pantallas angostas: la tabla de zonas oculta Distrito y Propina para caber sin desplazamiento */
[data-testid="stMarkdownContainer"]:has(> .tx-tbl-zonas) { container-type: inline-size; }
@container (max-width: 900px) {
  .tx-tbl-zonas th:nth-child(2), .tx-tbl-zonas td:nth-child(2),
  .tx-tbl-zonas th:nth-child(7), .tx-tbl-zonas td:nth-child(7) { display: none; }
  .tx-tbl-zonas th:nth-child(4), .tx-tbl-zonas td:nth-child(4) { min-width: 6rem; }
  .tx-tbl-zonas td:nth-child(1) { min-width: 7rem; }
  .tx-tbl-zonas table { font-size: 0.86rem; }
  .tx-tbl-zonas th, .tx-tbl-zonas td { padding: 0.4rem 0.45rem; }
  .tx-tbl-zonas .tx-spk { width: 5rem; }
}
</style>
"""


_JS_VISTO = """
<script>
(function () {
  if (window.__txVisto) return;            // una sola vez por pestaña
  window.__txVisto = true;
  var d = document;
  d.documentElement.classList.add('tx-js'); // sin esta clase, las animaciones corren al cargar
  var SEL = '.js-plotly-plot, .tx-cmp, .tx-tbl, .tx-kpis, .tx-groups';
  var io = new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      if (e.isIntersecting) { e.target.classList.add('tx-visto'); io.unobserve(e.target); }
    });
  }, { threshold: 0, rootMargin: '0px 0px -12% 0px' });
  function buscar() {
    d.querySelectorAll(SEL).forEach(function (el) {
      if (!el.__txObs) { el.__txObs = true; io.observe(el); }
    });
  }
  buscar();
  new MutationObserver(buscar).observe(d.body, { childList: true, subtree: true });
})();
</script>
"""


def estilos():
    """Inyecta los estilos propios de la app (una vez por página)."""
    st.markdown(_CSS, unsafe_allow_html=True)


def animar_al_ver():
    """Las animaciones arrancan cuando cada gráfico o tabla aparece en pantalla (al bajar con el scroll).
    Si el navegador no ejecuta el script, todo se anima al cargar, como antes."""
    try:
        st.html(_JS_VISTO, unsafe_allow_javascript=True)
    except TypeError:   # versiones de Streamlit sin unsafe_allow_javascript
        pass


def encabezado(titulo: str, bajada: str):
    """Título de página con la franja de cuadros y una bajada en lenguaje simple."""
    st.markdown(
        f'<div class="tx-head">'
        f'<h1 class="tx-title">{titulo}</h1><p class="tx-lede">{bajada}</p></div>',
        unsafe_allow_html=True,
    )


def chip(texto: str, color: str) -> str:
    return f'<span class="tx-chip"><span class="tx-dot" style="background:{color}"></span>{texto}</span>'


def color_grupos(grupos) -> dict:
    """Color fijo por grupo (por orden alfabético del nombre, no por número de K-Means)."""
    return {g: c for g, c in zip(sorted(grupos), COLORES_GRUPO)}


def tipo_de_zona(zona_id: int) -> str | None:
    """Grupo de K-Means de una zona, leído del CSV precalculado (si existe)."""
    seg = cargar_segmentacion()
    if seg is None:
        return None
    fila = seg.loc[seg["zona_id"] == zona_id, "nombre_grupo"]
    return None if fila.empty else str(fila.iloc[0])


# ------------------------- Piezas de presentación (HTML) -------------------------
def _fmt(v, dec=0):
    return f"{v:,.{dec}f}"


def sparkline(valores, color="#1C2128", relleno="rgba(242,183,5,0.30)") -> str:
    """Mini gráfico SVG (área + línea) a partir de una lista de valores."""
    vals = [float(v) for v in valores]
    if not vals:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    n = len(vals)
    pts = [(i * 100 / max(n - 1, 1), 30 - (v - lo) / rng * 26) for i, v in enumerate(vals)]
    linea = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
    area = f"0,32 {linea} 100,32"
    return (f'<svg class="spark" viewBox="0 0 100 32" preserveAspectRatio="none" aria-hidden="true">'
            f'<polygon points="{area}" fill="{relleno}"/>'
            f'<polyline points="{linea}" fill="none" stroke="{color}" stroke-width="1.6" '
            f'vector-effect="non-scaling-stroke" stroke-linejoin="round"/></svg>')


def pill(texto: str, tono: str = "flat") -> str:
    return f'<span class="tx-pill {tono}">{texto}</span>'


def banda_kpis(items: list[dict]):
    """Banda de indicadores: cada item tiene lab, val, y opcionalmente unidad, nota y spark (HTML)."""
    celdas = []
    for it in items:
        unidad = f'<small>{it["unidad"]}</small>' if it.get("unidad") else ""
        nota = f'<div class="note">{it["nota"]}</div>' if it.get("nota") else ""
        celdas.append(f'<div class="tx-kpi"><p class="lab">{it["lab"]}</p>'
                      f'<div class="val">{it["val"]}{unidad}</div>{nota}{it.get("spark", "")}</div>')
    st.markdown(f'<div class="tx-kpis" style="--n:{len(items)}">{"".join(celdas)}</div>',
                unsafe_allow_html=True)


def hora_elegida(evento, defecto: int) -> int:
    """Hora seleccionada con un clic en un gráfico de Plotly (o la hora por defecto)."""
    try:
        puntos = evento["selection"]["points"]
        if puntos:
            return int(round(float(puntos[0]["x"])))
    except (KeyError, TypeError, IndexError, ValueError):
        pass
    return defecto


def regla_rango(p10, p50, p90, real=None, tope=None) -> str:
    """Barra horizontal que dibuja el rango 10%–90%, la mediana y el valor real."""
    tope = max(tope or 0, p90, real or 0) * 1.08 or 1
    pos = lambda v: max(0.0, min(100.0, v / tope * 100))
    dot = f'<span class="dot" style="left:{pos(real):.1f}%"></span>' if real is not None else ""
    if pos(p90) - pos(p10) < 18:   # rango estrecho: una sola etiqueta para que no se encimen
        ticks = (f'<span class="tick" style="left:{(pos(p10) + pos(p90)) / 2:.1f}%">'
                 f'{p10:,.0f}–{p90:,.0f}</span>')
    else:
        ticks = (f'<span class="tick" style="left:{pos(p10):.1f}%">{p10:,.0f}</span>'
                 f'<span class="tick" style="left:{pos(p90):.1f}%">{p90:,.0f}</span>')
    return (f'<div class="tx-range"><span class="rail"></span>'
            f'<span class="band" style="left:{pos(p10):.1f}%;width:{pos(p90) - pos(p10):.1f}%"></span>'
            f'<span class="mark" style="left:{pos(p50):.1f}%"></span>{dot}{ticks}</div>')


# ------------------------- Dirección de la API -------------------------
def api_url() -> str:
    """La dirección de la API: primero st.secrets, luego lo que el usuario escriba,
    y en último caso localhost (para desarrollo)."""
    if st.session_state.get("API_URL_guardada"):
        return st.session_state["API_URL_guardada"]
    try:
        return st.secrets["API_URL"].rstrip("/")   # función avanzada: st.secrets
    except Exception:
        return "http://127.0.0.1:8000"


# ------------------------- Llamadas cacheadas -------------------------
@st.cache_data(ttl=3600, show_spinner=False)   # función avanzada: @st.cache_data
def _get(url: str, params: tuple = ()) -> dict:
    r = requests.get(url, params=dict(params), timeout=90)   # timeout alto: Render "despierta"
    r.raise_for_status()
    return r.json()


def get_info() -> dict:
    return _get(f"{api_url()}/info")


def get_pronostico(zona_id: int, fecha: str) -> dict:
    return _get(f"{api_url()}/pronostico", (("zona_id", zona_id), ("fecha", fecha)))


# ------------------------- Estado de la API en la barra lateral -------------------------
def barra_lateral_api() -> dict | None:
    """Muestra el estado de la API y permite cambiar su dirección. Devuelve /info o None."""
    estilos()
    with st.sidebar:
        st.markdown(
            '<div class="tx-brand"><span class="tx-mark"></span><span class="tx-name">Taxis NYC</span></div>'
            '<p class="tx-brand-sub">Demanda de taxis amarillos, enero de 2024 (NYC TLC)</p>',
            unsafe_allow_html=True,
        )
        animar_al_ver()
        with st.status("Conectando con la API…", expanded=False) as estado:
            try:
                info = get_info()
                estado.update(label="API en línea", state="complete")
                try:
                    st.badge("API en línea", color="green")   # función avanzada: st.badge
                except Exception:
                    st.success("API en línea")
            except requests.RequestException as e:
                estado.update(label="API sin conexión", state="error")
                info = None
                _aviso_api_caida(e)

        with st.popover("⚙️ Configurar API"):            # función avanzada: st.popover
            st.text_input(
                "Dirección de la API",
                value=api_url(),
                key="API_URL_manual",
                on_change=_guardar_api_url,
                help="En producción se define en Secrets como API_URL. Aquí puedes "
                     "sobrescribirla para pruebas (p. ej. http://localhost:8000).",
            )
            if st.button("Probar de nuevo"):
                st.cache_data.clear()
                st.rerun()
    return info


def _guardar_api_url():
    st.session_state["API_URL_guardada"] = st.session_state["API_URL_manual"].strip().rstrip("/")


def _aviso_api_caida(error: Exception):
    """Mensaje claro cuando la API no responde (en vez de un error de Python)."""
    st.error(
        "No se pudo conectar con la API en "
        f"`{api_url()}`. Si está en Render, el plan gratuito la **duerme** tras 15 "
        "minutos sin uso: abre el link de la API en el navegador, espera ~1 minuto y recarga."
    )
    with st.expander("Detalle técnico"):
        st.code(str(error))


def exigir_api(info: dict | None):
    """Corta la página con un mensaje claro si la API no está disponible."""
    if info is None:
        st.warning("Esta página necesita la API. Revisa la barra lateral.")
        st.stop()


# ------------------------- Selector de zona (se recuerda entre páginas) -------------------------
def selector_zona(info: dict, key: str = "zona") -> dict:
    """Selectbox de zona que recuerda la elección en session_state y en la URL."""
    zonas = info["zonas"]
    ids = [z["id"] for z in zonas]
    etiqueta = {z["id"]: f'{z["nombre"]} ({z["distrito"]})' for z in zonas}

    # Recuperar de la URL o de session_state (funciones avanzadas: st.query_params + st.session_state)
    if "zona_id" not in st.session_state:
        en_url = st.query_params.get("zona")
        st.session_state["zona_id"] = int(en_url) if (en_url and int(en_url) in ids) else (
            ZONA_INICIAL if ZONA_INICIAL in ids else ids[0])

    actual = st.session_state["zona_id"]
    elegido = st.selectbox(
        "Zona", ids, index=ids.index(actual) if actual in ids else 0,
        format_func=lambda z: etiqueta[z], key=f"sel_{key}",
    )
    st.session_state["zona_id"] = elegido
    st.query_params["zona"] = str(elegido)      # el link recuerda la zona
    return next(z for z in zonas if z["id"] == elegido)


def selector_fecha(info: dict, key: str = "fecha") -> str:
    """Selector de fecha tipo botones (función avanzada: st.segmented_control)."""
    fechas = info["fechas"]
    elegida = st.segmented_control(
        "Fecha", fechas, format_func=_fmt_fecha, default=fechas[0], key=f"seg_{key}",
    )
    return elegida or fechas[0]


def _fmt_fecha(f: str) -> str:
    d = datetime.strptime(f, "%Y-%m-%d")
    etiqueta = f"{DIAS[d.weekday()]} {d.day}"
    return etiqueta + " (mañana)" if f == "2024-02-01" else etiqueta


# ------------------------- Carga de CSV precalculados -------------------------
@st.cache_data(show_spinner=False)
def cargar_segmentacion() -> pd.DataFrame | None:
    ruta = DATA / "zonas_segmentadas.csv"
    return pd.read_csv(ruta) if ruta.exists() else None


@st.cache_data(show_spinner=False)
def cargar_metricas() -> dict | None:
    ruta = DATA / "metricas_modelo.json"
    return json.load(open(ruta, encoding="utf-8")) if ruta.exists() else None


def exigir_datos(obj, nombre: str):
    if obj is None:
        st.error(
            f"Falta `app/data/{nombre}`. Corre **preparacion.ipynb** de arriba a abajo "
            "para generar los archivos precalculados y colócalos en `app/data/`."
        )
        st.stop()
