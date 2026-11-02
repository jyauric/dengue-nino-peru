"""Arma web/index.html con los datos procesados.

Lee datos/procesados/*.csv y el mapa de distritos, y mete esos datos como JSON
dentro de web/plantilla.html. Ejecutar desde la raíz del repo, después de procesar_datos.py:

    uv run python web/construir.py
"""
import json
import warnings
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry.polygon import orient

warnings.filterwarnings("ignore", message="Geometry is in a geographic CRS")   # buffer de ~100 m
RAIZ = Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesados"
AQUI = Path(__file__).resolve().parent


def filas(df):
    # JSON sin NaN: pandas los escribe como null
    return json.loads(df.to_json(orient="records", force_ascii=False))


# ── Mapa: unir distritos en departamentos y simplificar para la web (~1 km) ──
distritos = gpd.read_file(RAIZ / "datos" / "originales" / "distritos_peru.geojson").to_crs(4326)
deps = distritos.dissolve(by="departamento", as_index=False)[["departamento", "geometry"]]
deps["geometry"] = (deps.buffer(0.001).buffer(-0.001)       # cierra huecos entre distritos
                    .simplify(0.01, preserve_topology=True)
                    .apply(lambda g: orient(g, sign=-1.0) if g.geom_type == "Polygon"
                           else type(g)([orient(p, sign=-1.0) for p in g.geoms])))
# d3 pide los anillos exteriores en sentido horario: orient(sign=-1)
geo = json.loads(deps.to_json(drop_id=True))
for f in geo["features"]:
    f["geometry"]["coordinates"] = json.loads(
        json.dumps(f["geometry"]["coordinates"]),
        parse_float=lambda v: round(float(v), 3))

# ── Tablas ──
dep = pd.read_csv(PROC / "dengue_departamento_anio.csv")
dep = dep[["departamento", "anio", "casos", "casos_se42", "poblacion"]]

sem = pd.read_csv(PROC / "dengue_nacional_semana.csv")[["fecha_inicio", "casos"]]

noaa = pd.read_csv(PROC / "nino_anomalia_mensual.csv")[["fecha", "anom_nino12"]]

epi = pd.read_csv(PROC / "nino_episodios_enfen.csv")

dis = pd.read_csv(PROC / "dengue_distrito_anio.csv", dtype={"ubigeo": str})
dis = dis[["departamento", "provincia", "distrito", "anio", "casos", "casos_se42"]]

datos = {
    "dep": filas(dep),
    "sem": filas(sem),
    "noaa": filas(noaa),
    "epi": filas(epi),
    "dis": filas(dis),
    "geo": geo,
}
texto = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
texto = texto.replace("</", "<\\/")   # que ningún texto cierre el <script>

plantilla = (AQUI / "plantilla.html").read_text(encoding="utf-8")
assert "__DATOS__" in plantilla
(AQUI / "index.html").write_text(plantilla.replace("__DATOS__", texto), encoding="utf-8")
print(f"web/index.html: {len(texto) / 1024:,.0f} KB de datos")
