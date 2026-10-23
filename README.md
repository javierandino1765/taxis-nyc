# Taxis NYC · Una app para quien toma decisiones

**AIMLF1 · Módulo 2 · Actividad en parejas**

Pronóstico con incertidumbre, segmentación de zonas y una recomendación de cuántos taxis enviar,
en una app de Streamlit que consulta su propia API.

## Links de la entrega

| Pieza | Link |
|---|---|
| App (Streamlit Community Cloud) | `https://taxis-nyc-cmme3awb5eye6j6xpadl5u.streamlit.app/?zona=161` |
| API (Render) · su `/docs` debe abrir | `https://taxis-nyc-api-tug5.onrender.com/` |
| Repositorio (público) | `https://github.com/javierandino1765/taxis-nyc` |

## Integrantes

- Alexia Carolina Guevara Mendoza
- Oscar Jasher Villalta Yada
- Javier Alejandro Andino García

## Estructura del repositorio

```
taxis-nyc/
├── preparacion.ipynb          # datos, modelos y métricas (genera TODO lo demás)
├── api/
│   ├── main.py                # la API (FastAPI)
│   ├── modelo_pronostico.ubj  # modelo XGBoost de 9 cuantiles  (lo crea el notebook)
│   ├── info_modelo.json       # zonas, fechas y cuantiles       (lo crea el notebook)
│   ├── demanda.parquet        # 25 ene – 1 feb con variables ya calculadas (lo crea el notebook)
│   └── requirements.txt
├── app/
│   ├── streamlit_app.py       # punto de entrada (st.navigation)
│   ├── comun.py               # API, caché, manejo de errores, selectores
│   ├── paginas/               # una página por archivo
│   │   ├── 1_pronostico.py
│   │   ├── 2_decision.py
│   │   ├── 3_segmentacion.py
│   │   ├── 4_ficha.py
│   │   └── 5_monitoreo.py     # extra (+10)
│   ├── data/                  # zonas_segmentadas.csv y metricas_modelo.json (los crea el notebook)
│   ├── .streamlit/config.toml # tema de colores
│   └── requirements.txt
└── README.md
```

> **La idea del diseño:** el notebook hace el trabajo pesado una vez; la API solo *busca y predice*;
> la app solo *lee archivos y dibuja*. El modelo nunca sale del servidor de la API.

## Cómo correrlo (orden importante)

### 0. Generar los artefactos — `preparacion.ipynb`

Abre el notebook en Colab o Jupyter y córrelo **de arriba a abajo** (*Run all*). Al terminar deja:

- en `api/`: `modelo_pronostico.ubj`, `info_modelo.json`, `demanda.parquet`;
- en `app/data/`: `zonas_segmentadas.csv`, `metricas_modelo.json`.

(Si lo corres en Colab, usa la última celda para descargar un zip y copia los archivos a cada carpeta.)

### 1. La API en local

```bash
cd api
python -m venv .venv && source .venv/bin/activate   # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Abre `http://localhost:8000/docs` y prueba `GET /pronostico?zona_id=161&fecha=2024-01-25`.

### 2. La app en local

```bash
cd app
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Por defecto la app busca la API en `http://localhost:8000`. Puedes cambiar la dirección en la barra
lateral (**⚙️ Configurar API**) sin tocar el código.

## Cómo publicarlo

### API en Render

1. render.com → entrar con GitHub → **New → Web Service** → elegir el repositorio.
2. **Root Directory:** `api`
3. **Build Command:** `pip install -r requirements.txt`
4. **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. **Instance Type:** Free → **Deploy**. Al terminar, abre `https://<tu-api>.onrender.com/docs`.

> Render (plan gratuito) **duerme** la API tras 15 minutos sin uso; la primera petición después tarda
> cerca de un minuto. La app ya usa `timeout=90` y avisa cuando eso pasa.

### App en Streamlit Community Cloud

1. share.streamlit.io → **Create app** → el mismo repositorio.
2. **Main file path:** `app/streamlit_app.py`
3. **Advanced settings → Secrets:**
   ```toml
   API_URL = "https://<tu-api>.onrender.com"
   ```

## Contrato de la API

| Endpoint | Recibe | Devuelve |
|---|---|---|
| `GET /` | nada | que la API está en línea |
| `GET /info` | nada | zonas pronosticables (id, nombre, distrito), fechas y cuantiles |
| `GET /pronostico` | `zona_id`, `fecha` (AAAA-MM-DD) | las 24 horas, cada una con cuantiles, `real` (o `null`) y `hace_una_semana` |

Si la zona o la fecha no existen, responde **404** con un mensaje claro.

## Funciones avanzadas de Streamlit usadas (≥ 5)

`st.navigation` + `st.Page` · `@st.fragment` · `@st.dialog` · `st.plotly_chart(on_select="rerun")` ·
`st.column_config` (ProgressColumn y LineChartColumn) · `@st.cache_data(ttl=3600)` · `st.secrets` ·
`st.session_state` + `st.query_params` · `st.segmented_control` / `st.pills` · `st.metric(border, chart_data, delta)` ·
`st.badge` / `st.popover` · `st.status` / `st.toast` · `st.feedback` · `st.download_button` · `.streamlit/config.toml`.
