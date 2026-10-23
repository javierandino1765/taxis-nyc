# Carpeta de datos de la app

Esta carpeta debe contener **dos archivos que genera `preparacion.ipynb`**:

- `zonas_segmentadas.csv` — una fila por zona: variables, grupo de K-Means, componentes de PCA y perfil horario.
- `metricas_modelo.json` — todas las cifras que muestra la **Ficha del modelo**.

Corre el notebook de arriba a abajo y copia aquí ambos archivos (el notebook ya los guarda en
`app/data/` si lo ejecutas en la raíz del repositorio). Mientras no existan, las páginas de
**Segmentación** y **Ficha del modelo** mostrarán un aviso en vez de caerse.
