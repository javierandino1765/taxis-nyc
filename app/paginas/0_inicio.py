"""Página de inicio · Plan del día. Resume en una pantalla las cuatro preguntas de la gerente.
No calcula nada nuevo: reúne lo que muestran Pronóstico, Segmentación, Decisión y la Ficha."""
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

import comun

info = comun.barra_lateral_api()

comun.encabezado("Plan del día",
                 "Lo esencial para planificar la flota en una zona: qué esperar, qué tipo de zona es, "
                 "cuántos taxis enviar y cuánto confiar en el pronóstico.")
comun.exigir_api(info)

with st.container(border=True, key="card-toolbar"):
    c1, _ = st.columns([0.5, 0.5])
    with c1:
        zona = comun.selector_zona(info)
    fecha = comun.selector_fecha(info)

try:
    datos = comun.get_pronostico(zona["id"], fecha)
except requests.RequestException:
    st.error("La API no respondió a tiempo. Intenta de nuevo en un minuto.")
    st.stop()

h = pd.DataFrame(datos["horas"])
h = pd.concat([h.drop(columns="cuantiles"), pd.json_normalize(h["cuantiles"])], axis=1)
hay_real = h["real"].notna().any()
hora_pico = int(h.loc[h["p50"].idxmax(), "hora"])

seg = comun.cargar_segmentacion()
met = comun.cargar_metricas()
tipo = comun.tipo_de_zona(zona["id"])
colores = comun.color_grupos(seg["nombre_grupo"].unique()) if seg is not None else {}

# --- La forma del día: barras por hora, coloreadas por intensidad. Interactivo: un clic en
#     una barra muestra el detalle de esa hora a la derecha. ---
with st.container(border=True, key="card-cinta"):
    st.subheader(f'{zona["nombre"]}, {comun._fmt_fecha(fecha)}: viajes esperados hora por hora')
    g_izq, g_der = st.columns([0.68, 0.32], gap="medium")
    tope = float(h["p50"].max()) or 1.0
    fig = go.Figure(go.Bar(
        x=h["hora"], y=h["p50"],
        marker=dict(color=h["p50"], cmin=0, cmax=tope, line_width=0,
                    colorscale=[[0, "#E8EAED"], [0.45, "#F7D670"], [1, "#C98A00"]]),
        customdata=h[["p10", "p90"]].to_numpy(),
        hovertemplate="%{x}:00<br>Esperados: %{y:,.0f}<br>Rango 10%–90%: "
                      "%{customdata[0]:,.0f}–%{customdata[1]:,.0f}<extra></extra>",
        unselected=dict(marker=dict(opacity=0.35)),
    ))
    fig.update_layout(height=300, xaxis_title="Hora del día", yaxis_title="Viajes esperados",
                      xaxis=dict(dtick=2), bargap=0.15, hovermode="closest", clickmode="event+select",
                      yaxis=dict(range=[0, tope * 1.12]), margin=dict(l=10, r=10, t=10, b=10))
    with g_izq:
        ev = st.plotly_chart(comun.fig_taxis(fig), width="stretch", theme=None,
                             config={"displayModeBar": False}, on_select="rerun",
                             selection_mode="points", key="graf_inicio")

    hs = comun.hora_elegida(ev, hora_pico)
    fila = h.loc[h["hora"] == hs].iloc[0]
    real_h = None if pd.isna(fila["real"]) else float(fila["real"])
    sem_h = None if pd.isna(fila["hace_una_semana"]) else float(fila["hace_una_semana"])
    with g_der:
        st.markdown(
            f'<div class="tx-hour"><h5>{hs:02d}:00 a {hs:02d}:59</h5>'
            f'<p class="hint">{"Hora pico del día. " if hs == hora_pico else ""}'
            f'Haz clic en una barra para ver esa hora.</p>'
            f'<div class="big">{fila["p50"]:,.0f}<small>viajes esperados</small></div>'
            f'{comun.regla_rango(float(fila["p10"]), float(fila["p50"]), float(fila["p90"]), real_h, float(h["p90"].max()))}'
            f'<dl><dt>Rango 10%–90%</dt><dd>{fila["p10"]:,.0f}–{fila["p90"]:,.0f}</dd>'
            f'<dt>Real</dt><dd>{f"{real_h:,.0f}" if real_h is not None else "Pendiente"}</dd>'
            f'<dt>Hace una semana</dt><dd>{f"{sem_h:,.0f}" if sem_h is not None else "—"}</dd></dl></div>',
            unsafe_allow_html=True,
        )

# --- Las cuatro preguntas ---
q = 0.8   # costos de referencia de la guía: $10 taxi ocioso y $40 pasajero perdido
enviados = h["p80"]


def tarjeta(clave, numero, pregunta, titular, detalle, pagina, boton, icono, extra=""):
    with st.container(border=True, key=f"card-{clave}", height="stretch"):
        st.markdown(
            f'<div class="tx-q"><p class="tx-q-num"><span>{numero}</span>{pregunta}</p>'
            f'<p class="tx-q-big">{extra}{titular}</p><p class="tx-q-txt">{detalle}</p></div>',
            unsafe_allow_html=True,
        )
        st.page_link(pagina, label=boton, icon=icono)


a, b = st.columns(2, gap="medium")
with a:
    tarjeta("q1", 1, "Qué esperar",
            f'{h["p50"].sum():,.0f} viajes',
            f'Rango del día (80%): {h["p10"].sum():,.0f}–{h["p90"].sum():,.0f}. '
            f'Hora pico a las {hora_pico:02d}:00 con {h["p50"].max():,.0f} viajes.',
            "paginas/1_pronostico.py", "Ver el pronóstico por hora", ":material/insights:")
with b:
    if tipo and seg is not None:
        sub = seg[seg["nombre_grupo"] == tipo]
        tarjeta("q2", 2, "Qué tipo de zona es", tipo,
                f'Comparte grupo con {len(sub) - 1} zonas más: distancia mediana de '
                f'{sub["dist_mediana"].median():.1f} millas y {sub["pct_22a5"].median():.0f}% de viajes de noche.',
                "paginas/3_segmentacion.py", "Ver la segmentación", ":material/scatter_plot:",
                extra=f'<span class="tx-q-dot" style="background:{colores.get(tipo, "#5A6470")}"></span>')
    else:
        tarjeta("q2", 2, "Qué tipo de zona es", "Sin grupo",
                "Esta zona no está en la segmentación precalculada.",
                "paginas/3_segmentacion.py", "Ver la segmentación", ":material/scatter_plot:")

c, d = st.columns(2, gap="medium")
with c:
    tarjeta("q3", 3, "Qué hacer",
            f"Envía {enviados.sum():,.0f} taxis",
            f"Con los costos de referencia ($10 un taxi ocioso, $40 un pasajero perdido) conviene cubrir "
            f"el cuantil 80% en cada hora. Máximo de {enviados.max():,.0f} taxis en una hora.",
            "paginas/2_decision.py", "Ajustar costos y descargar el plan", ":material/balance:")
with d:
    if met:
        err_tipo = met["error_por_tipo_zona"].get(tipo) if tipo else None
        titular = f"{err_tipo:.1f} viajes por hora" if err_tipo is not None else f'{met["mae_modelo"]:.1f} viajes por hora'
        quien = f"en zonas de tipo {tipo}" if err_tipo is not None else "en promedio"
        tarjeta("q4", 4, "Cuánto confiar", titular,
                f'Es el error medio del pronóstico {quien} en la semana de prueba. El rango del 80% '
                f'acertó el {met["cobertura_80"]:.0f}% de las horas.',
                "paginas/4_ficha.py", "Leer la ficha del modelo", ":material/description:")
