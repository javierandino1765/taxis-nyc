"""API de pronóstico de demanda de taxis en NYC (enero 2024).

Expone el modelo XGBoost de 9 cuantiles como un servicio web. La API NO recalcula
lags ni reentrena: carga los archivos que generó `preparacion.ipynb`, busca las filas
que le piden en `demanda.parquet` (que ya traen las variables calculadas) y predice.

Endpoints (contrato de la sección 4.1 de la guía):
    GET  / -> la API está en línea
    GET  /info -> zonas pronosticables, fechas y cuantiles
    GET  /pronostico?zona_id=&fecha=  -> las 24 horas del día, con cuantiles, real y hace_una_semana

Para correrla en local:   uvicorn main:app --reload
Documentación interactiva: http://localhost:8000/docs
"""
import json
import os
from datetime import date

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from xgboost import XGBRegressor

# --- Cargar los artefactos (rutas relativas a este archivo, no al cwd) ---
AQUI = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(AQUI, "info_modelo.json"), encoding="utf-8") as f:
    INFO = json.load(f)

VARIABLES = INFO["variables"]            # incluye 'zona' al final
CUANTILES = INFO["cuantiles"]            # [0.1, 0.2, ..., 0.9]
ZONAS = [z["id"] for z in INFO["zonas"]]  # orden exacto de categorías del entrenamiento
NOMBRES = {z["id"]: z for z in INFO["zonas"]}

modelo = XGBRegressor()
modelo.load_model(os.path.join(AQUI, "modelo_pronostico.ubj"))

DEMANDA = pd.read_parquet(os.path.join(AQUI, "demanda.parquet"))
DEMANDA["hora"] = pd.to_datetime(DEMANDA["hora"])

app = FastAPI(title="Pronóstico de demanda de taxis NYC", version="1.0")


def _predecir(filas: pd.DataFrame) -> np.ndarray:
    """Predice los 9 cuantiles para un conjunto de filas y los ordena por fila."""
    X = filas.copy()
    # Reconstruir la categoría 'zona' con el MISMO orden de categorías del entrenamiento.
    X["zona"] = pd.Categorical(X["PULocationID"].astype(int), categories=ZONAS)
    pred = modelo.predict(X[VARIABLES])
    return np.sort(pred, axis=1)   # evita cuantiles cruzados (p60 < p50)


@app.get("/")
def estado():
    return {"estado": "ok", "mensaje": "API de pronóstico de demanda de taxis NYC"}


@app.get("/info")
def info():
    """Lo que la app necesita para armar sus formularios."""
    return {
        "modelo": f"XGBoost · {len(CUANTILES)} cuantiles",
        "cuantiles": CUANTILES,
        "horizonte_horas": INFO.get("horizonte_horas", 24),
        "fechas": INFO["fechas"],
        "zonas": INFO["zonas"],
    }


@app.get("/pronostico")
def pronostico(zona_id: int, fecha: date):
    """Las 24 horas de un día para una zona: cuantiles, valor real y el de hace una semana."""
    if zona_id not in NOMBRES:
        raise HTTPException(status_code=404,
                            detail=f"La zona {zona_id} no se pronostica. Revisa /info.")

    filas = DEMANDA[(DEMANDA["PULocationID"] == zona_id) &
                    (DEMANDA["hora"].dt.date == fecha)].sort_values("hora")
    if filas.empty:
        raise HTTPException(status_code=404,
                            detail=f"No hay datos para la zona {zona_id} en {fecha}. Revisa /info.")

    pred = _predecir(filas)
    horas = []
    for i, (_, row) in enumerate(filas.reset_index(drop=True).iterrows()):
        real = row["viajes"]
        hace_sem = row.get("lag_168", np.nan)
        horas.append({
            "hora": int(row["hora"].hour),
            "real": None if pd.isna(real) else int(round(real)),
            "hace_una_semana": None if pd.isna(hace_sem) else int(round(hace_sem)),
            "cuantiles": {f"p{int(q * 100)}": round(float(pred[i, j]), 1)
                          for j, q in enumerate(CUANTILES)},
        })

    z = NOMBRES[zona_id]
    return {
        "zona": {"id": z["id"], "nombre": z["nombre"], "distrito": z["distrito"]},
        "fecha": str(fecha),
        "horas": horas,
    }
