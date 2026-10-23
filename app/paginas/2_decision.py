"""Página 2 · Decisión: ¿cuántos taxis enviar? (Parte 3, problema del vendedor de periódicos)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

import comun

info = comun.barra_lateral_api()

comun.encabezado("¿Cuántos taxis enviar?",
                 "El pronóstico no es la decisión. La cantidad correcta depende de qué cuesta más: "
                 "un taxi esperando sin pasajero, o un pasajero que no encuentra taxi.")

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
cu = pd.json_normalize(h["cuantiles"])
h = pd.concat([h.drop(columns="cuantiles"), cu], axis=1)
cuantiles = info["cuantiles"]


@st.fragment   # función avanzada: @st.fragment (mover un control no recarga toda la página)
def panel_decision(h: pd.DataFrame):
    with st.container(border=True, key="card-costos"):
        a, b = st.columns(2, gap="large")
        costo_ocioso = a.slider("Costo de un taxi una hora sin pasajero (USD)", 1, 50, 10,
                                help="Combustible y hora del conductor desperdiciados.")
        costo_perdido = b.slider("Costo de un pasajero que no encontró taxi (USD)", 1, 100, 40,
                                 help="Viaje perdido y cliente que se va a la competencia.")

    q_opt = costo_perdido / (costo_perdido + costo_ocioso)
    q_cerca = min(cuantiles, key=lambda q: abs(q - q_opt))
    col_env = f"p{int(q_cerca * 100)}"

    enviados = h[col_env]
    real = h["real"]
    hay_real = real.notna().any()

    # Costos (solo si hay datos reales): se calculan antes para mostrarlos en la respuesta
    def costo(env):
        e = np.maximum(env - real, 0) * costo_ocioso
        p = np.maximum(real - env, 0) * costo_perdido
        return float((e + p)[real.notna()].sum())

    if hay_real:
        c_recom = costo(enviados)
        c_p50 = costo(h["p50"])
        c_sem = costo(h["hace_una_semana"])

    # --- La respuesta primero ---
    hora_pico = int(h.loc[enviados.idxmax(), "hora"])
    q_txt = f"{int(q_cerca * 100)}%"
    if hay_real:
        stat3 = ('<div class="tx-stat"><p class="lab">Costo con esta regla</p>'
                 f'<div class="val hi">${c_recom:,.0f}</div></div>')
    else:
        stat3 = ('<div class="tx-stat"><p class="lab">Costo del día</p>'
                 '<div class="val">Pendiente</div></div>')
    st.markdown(
        f'<div class="tx-answer">'
        f'<div><p class="tx-kicker">Recomendación para {zona["nombre"]}, {comun._fmt_fecha(fecha)}</p>'
        f'<p class="tx-big">Envía {enviados.sum():,.0f} taxis</p>'
        f'<p class="tx-sub">en el día. Así se cubre el {q_txt} de la demanda esperada en cada hora.</p></div>'
        f'<div class="tx-stat"><p class="lab">Máximo en una hora</p>'
        f'<div class="val">{enviados.max():,.0f}</div></div>'
        f'<div class="tx-stat"><p class="lab">Hora de más taxis</p>'
        f'<div class="val">{hora_pico:02d}:00</div></div>'
        f'{stat3}</div>',
        unsafe_allow_html=True,
    )

    # --- El porqué ---
    caja = st.container(border=True, key="card-formula")
    f1 = f2 = caja
    with f1:
        st.latex(r"\text{cuantil óptimo} = \frac{C_\text{perdido}}{C_\text{perdido} + C_\text{ocioso}}"
                 rf" = \frac{{{costo_perdido}}}{{{costo_perdido} + {costo_ocioso}}} = {q_opt:.2f}")
    with f2:
        st.markdown(
            f"Perder un pasajero cuesta **{costo_perdido / costo_ocioso:.1f} veces** lo que cuesta un taxi "
            f"ocioso. La regla óptima es cubrir el **cuantil {int(q_cerca * 100)}%** de la demanda: "
            f"se envía la cantidad del pronóstico en ese cuantil."
        )

    # Gráfico: barras de taxis recomendados + pronóstico central + demanda real.
    # Interacción: un clic en una barra muestra el detalle de esa hora.
    with st.container(border=True, key="card-plan"):
        st.subheader("Plan por hora")
        p_izq, p_der = st.columns([0.68, 0.32], gap="medium")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=h["hora"], y=enviados, name=f"Taxis recomendados (p{int(q_cerca*100)})",
                             marker_color=comun.COLOR["amarillo"], marker_line_width=0,
                             hovertemplate="%{y:.0f}", unselected=dict(marker=dict(opacity=0.35))))
        fig.add_trace(go.Scatter(x=h["hora"], y=h["p50"], mode="lines",
                                 line=dict(color=comun.COLOR["asfalto"], width=2.5),
                                 name="Pronóstico central (p50)", hovertemplate="%{y:.0f}"))
        if hay_real:
            fig.add_trace(go.Scatter(x=h["hora"], y=real, mode="markers",
                                     marker=dict(color=comun.COLOR["real"], size=8,
                                                 line=dict(color="#FFFFFF", width=1)),
                                     name="Demanda real", hovertemplate="%{y:.0f}",
                                     unselected=dict(marker=dict(opacity=0.35))))
        tope_y = float(max(enviados.max(), real.max() if hay_real else 0)) * 1.15
        fig.update_layout(height=400, xaxis_title="Hora", yaxis_title="Taxis / viajes",
                          bargap=0.18, xaxis=dict(dtick=2), yaxis=dict(range=[0, tope_y]),
                          legend=dict(orientation="h", y=-0.22, x=0), clickmode="event+select",
                          margin=dict(l=10, r=10, t=10, b=10))
        with p_izq:
            ev = st.plotly_chart(comun.fig_taxis(fig), width="stretch", theme=None, config={"displayModeBar": False},
                                 on_select="rerun", selection_mode="points", key="graf_plan")

        hs = comun.hora_elegida(ev, hora_pico)
        i = h.index[h["hora"] == hs][0]
        env_h = float(enviados[i])
        if pd.notna(real[i]):
            r_h = float(real[i])
            sobran, faltan = max(env_h - r_h, 0), max(r_h - env_h, 0)
            costo_h = sobran * costo_ocioso + faltan * costo_perdido
            filas_h = (f'<dt>Demanda real</dt><dd>{r_h:,.0f}</dd>'
                       f'<dt>Taxis sin pasajero</dt><dd>{sobran:,.0f}</dd>'
                       f'<dt>Pasajeros sin taxi</dt><dd>{faltan:,.0f}</dd>'
                       f'<dt>Costo de esa hora</dt><dd>${costo_h:,.0f}</dd>')
        else:
            filas_h = '<dt>Demanda real</dt><dd>Pendiente</dd>'
        with p_der:
            st.markdown(
                f'<div class="tx-hour"><h5>{hs:02d}:00 a {hs:02d}:59</h5>'
                f'<p class="hint">Haz clic en una barra para ver esa hora.</p>'
                f'<div class="big">{env_h:,.0f}<small>taxis a enviar</small></div>'
                f'<dl><dt>Pronóstico central</dt><dd>{h.loc[i, "p50"]:,.0f}</dd>{filas_h}</dl></div>',
                unsafe_allow_html=True,
            )

    # Comparar costos (solo si hay datos reales)
    if hay_real:
        filas = [
            (f"Recomendación (p{int(q_cerca*100)})", "lo que propone la app", c_recom),
            ("Enviar el pronóstico central (p50)", "la mediana, sin ajustar por costos", c_p50),
            ("Enviar lo de hace una semana", "la regla simple", c_sem),
        ]
        tope = max(c for *_, c in filas) or 1
        mejor = min(c for *_, c in filas)
        html = ['<div class="tx-cmp"><p class="tx-cmp-t">Si este día se hubiera decidido así, el costo habría sido:</p>']
        for nombre, desc, c in filas:
            if c == c_recom:
                dif = comun.pill("base de comparación", "flat")
            else:
                d = (c - c_recom) / c_recom * 100 if c_recom else 0
                dif = comun.pill(f"{d:+.0f}% vs. la recomendación", "down" if d > 0 else "up")
            html.append(
                f'<div class="tx-row{" best" if c == mejor else ""}">'
                f'<div class="name">{nombre}<span>{desc}</span></div>'
                f'<div class="track"><div class="bar" style="width:{c / tope * 100:.1f}%"></div></div>'
                f'<div class="amt">${c:,.0f}</div><div class="dif">{dif}</div></div>')
        html.append("</div>")
        st.markdown("".join(html), unsafe_allow_html=True)
    else:
        st.info("El 1 de febrero es “mañana”: aún no hay demanda real, así que no se puede calcular "
                "el costo. La recomendación y el plan descargable sí están disponibles.",
                icon=":material/schedule:")

    st.write("")
    # Descargar el plan (función avanzada: st.download_button)
    plan = pd.DataFrame({"hora": h["hora"], "taxis_recomendados": enviados.round().astype(int)})
    d1, d2, _ = st.columns([0.3, 0.42, 0.28])
    d1.download_button("Descargar plan por hora", plan.to_csv(index=False).encode("utf-8"),
                       file_name=f'plan_taxis_{zona["id"]}_{fecha}.csv', mime="text/csv",
                       icon=":material/download:", type="primary", width="stretch")

    with d2.popover("¿Por qué no enviar el pronóstico central?", icon=":material/lightbulb:",
                    width="stretch"):
        st.write(
            "El pronóstico central (p50) acierta el promedio, pero quedarse corto cuesta más que "
            f"pasarse (aquí {costo_perdido/costo_ocioso:.1f} a 1). Cuando perder un pasajero es más "
            "caro, conviene enviar **de más**: por eso se usa un cuantil alto y no la mediana. "
            "Es el mismo razonamiento del umbral por costo que vimos en clasificación."
        )


panel_decision(h)
