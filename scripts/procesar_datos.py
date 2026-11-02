"""Limpia los datos originales y crea las tablas para el análisis y el dashboard.

Entrada: datos/originales/   ·   Salida: datos/procesados/
Ejecutar desde la raíz del repo:  uv run python scripts/procesar_datos.py
"""
import unicodedata
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent      # carpeta del repo, funcione desde donde se ejecute
ORIG = RAIZ / "datos" / "originales"
PROC = RAIZ / "datos" / "procesados"
PROC.mkdir(parents=True, exist_ok=True)

SE_CORTE = 42          # última semana de 2026 en la sala CDC (corte 24/10/2026)
ANIOS = range(2000, 2026)


def inicio_semana_epi(anio, semana):
    """Domingo en que empieza una semana epidemiológica. La SE 1 es la que contiene el 4 de enero."""
    cuatro_ene = date(anio, 1, 4)
    inicio_se1 = cuatro_ene - timedelta(days=(cuatro_ene.weekday() + 1) % 7)
    return inicio_se1 + timedelta(weeks=int(semana) - 1)


def normalizar(texto):
    """'Huánuco ' -> 'HUANUCO': mayúsculas, sin tildes ni espacios sobrantes (como en la base del CDC)."""
    sin_tildes = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return sin_tildes.strip().upper()


def leer_poblacion_inei(ruta):
    """Une las 9 hojas del INEI (3 años cada una) en una tabla larga: departamento, anio, poblacion."""
    partes = []
    for hoja in pd.read_excel(ruta, sheet_name=None, header=None, dtype={0: str}).values():
        anios = [int(a) for a in hoja.iloc[2].dropna().tolist()[2:]]           # fila 3: Ubigeo, Departamento, años
        filas = hoja[hoja[0].str.fullmatch(r"\d{2}0000", na=False) & (hoja[0] != "000000")]  # departamentos, sin "Perú"
        for i, anio in enumerate(anios):
            partes.append(pd.DataFrame({
                "departamento": filas[1].map(normalizar),
                "anio": anio,
                "poblacion": filas[2 + 3 * i].astype(int),                   # columna "Total" de ese año
            }))
    pob = pd.concat(partes, ignore_index=True)
    pob["departamento"] = pob["departamento"].replace({"PROV. CONST. DEL CALLAO": "CALLAO"})
    return pob


# ── 1. Casos 2000-2025 (datos abiertos) ──────────────────────────────
dengue = pd.read_csv(
    ORIG / "dengue_2000_2025.csv",
    dtype={"ubigeo": str},
    usecols=["departamento", "provincia", "distrito", "ubigeo", "ano", "semana", "tipo_dx"],
).rename(columns={"ano": "anio"})

assert dengue["tipo_dx"].isin(["C", "P"]).all(), "Aparecieron casos que no son C ni P"
dengue["ubigeo"] = dengue["ubigeo"].str.zfill(6)
for col in ["departamento", "provincia", "distrito"]:   # el CSV original trae "\ufffd" (�) en lugar de Ñ: FERRE�AFE, CA�ETE…
    dengue[col] = dengue[col].str.replace("\ufffd", "Ñ")
dengue["hasta_se42"] = dengue["semana"] <= SE_CORTE
print(f"Casos 2000-2025 (C+P): {len(dengue):,}")

# ── 2. Casos 2026 (sala CDC, tabla 1) y población 2000-2026 (INEI) ────
cdc = pd.read_excel(ORIG / "cdc_dengue_2026_SE42_casos_defunciones.xlsx")
cdc = cdc.rename(columns={"geo": "departamento"})
cdc["departamento"] = cdc["departamento"].map(normalizar)
departamentos = sorted(cdc["departamento"])

pob = leer_poblacion_inei(ORIG / "inei_poblacion_departamento_2000_2026.xlsx")
assert len(pob) == 25 * 27, f"Se esperaban 25 departamentos x 27 años y hay {len(pob)} filas"
assert set(pob["departamento"]) == set(departamentos), set(pob["departamento"]) ^ set(departamentos)

faltan = set(dengue["departamento"]) - set(departamentos)
assert not faltan, f"Departamentos que no están en el CDC: {faltan}"

# ── 3. Tabla departamento × año ──────────────────────────────────────
base = pd.MultiIndex.from_product([departamentos, ANIOS], names=["departamento", "anio"]).to_frame(index=False)
conteo = (dengue.groupby(["departamento", "anio"])
          .agg(casos=("semana", "size"), casos_se42=("hasta_se42", "sum"))
          .reset_index())
dep = base.merge(conteo, on=["departamento", "anio"], how="left")
dep[["casos", "casos_se42"]] = dep[["casos", "casos_se42"]].fillna(0).astype(int)

# 2026: solo hay datos hasta la SE 42 → "casos" (año completo) queda vacío
dep_2026 = cdc[["departamento", "casos"]].rename(columns={"casos": "casos_se42"}).assign(anio=2026)
dep = pd.concat([dep, dep_2026], ignore_index=True)

dep = dep.merge(pob, on=["departamento", "anio"], how="left", validate="one_to_one")
assert dep["poblacion"].notna().all(), "Hay departamento-año sin población"
dep["incidencia"] = (dep["casos"] / dep["poblacion"] * 100_000).round(1)          # casos por 100 mil hab.
dep["incidencia_se42"] = (dep["casos_se42"] / dep["poblacion"] * 100_000).round(1)
dep["fuente"] = dep["anio"].map(lambda a: "Sala situacional CDC (SE 1-42)" if a == 2026 else "Datos abiertos CDC-MINSA")
dep = dep.sort_values(["departamento", "anio"])
dep.to_csv(PROC / "dengue_departamento_anio.csv", index=False)

# ── 4. Serie nacional por semana ─────────────────────────────────────
sem = dengue.groupby(["anio", "semana"]).size().rename("casos").reset_index()
sem["fecha_inicio"] = [inicio_semana_epi(a, s) for a, s in zip(sem["anio"], sem["semana"])]
sem.to_csv(PROC / "dengue_nacional_semana.csv", index=False)

# ── 5. Detalle por distrito ──────────────────────────────────────────
nombres = dengue.drop_duplicates("ubigeo")[["ubigeo", "departamento", "provincia", "distrito"]]
dis = (dengue.groupby(["ubigeo", "anio"])
       .agg(casos=("semana", "size"), casos_se42=("hasta_se42", "sum"))
       .reset_index()
       .merge(nombres, on="ubigeo", how="left"))
dis = dis[["ubigeo", "departamento", "provincia", "distrito", "anio", "casos", "casos_se42"]]
dis.to_csv(PROC / "dengue_distrito_anio.csv", index=False)

# ── 6. Temperatura del mar (NOAA, Niño 1+2 y 3.4) ────────────────────
noaa = pd.read_csv(
    ORIG / "noaa_sstoi_nino12.txt", sep=r"\s+", skiprows=1,
    names=["anio", "mes", "t_nino12", "anom_nino12", "t_nino3", "anom_nino3",
           "t_nino4", "anom_nino4", "t_nino34", "anom_nino34"],
)
noaa = noaa[noaa["anio"] >= 2000].copy()
noaa["fecha"] = pd.to_datetime({"year": noaa["anio"], "month": noaa["mes"], "day": 1})
noaa = noaa[["anio", "mes", "fecha", "anom_nino12", "anom_nino34"]]
noaa.to_csv(PROC / "nino_anomalia_mensual.csv", index=False)

# ── 7. Episodios oficiales de El Niño costero (ENFEN) ─────────────────
episodios = pd.DataFrame([
    {"episodio": "El Niño costero 2017", "inicio": "2016-12-01", "fin": "2017-05-31",
     "fuente": "ENFEN, comunicados oficiales 10-2017 y 12-2017"},
    {"episodio": "El Niño costero 2023-24", "inicio": "2023-03-16", "fin": "2024-04-05",
     "fuente": "ENFEN, comunicados oficiales 03-2023 y 06-2024 (periodo de alerta)"},
])
episodios.to_csv(PROC / "nino_episodios_enfen.csv", index=False)

# ── 8. Validaciones ──────────────────────────────────────────────────
def total(anio, col):
    return int(dep.loc[dep["anio"] == anio, col].sum())

print("\nValidación contra la sala CDC")
print(f"  2025 completo: {total(2025, 'casos'):,}  (CDC: 35,853)")
print(f"  2025 SE 1-42:  {total(2025, 'casos_se42'):,}  (CDC: 32,594)")
print(f"  2026 SE 1-42:  {total(2026, 'casos_se42'):,}  (CDC: 82,554)")
print(f"  2026 / 2025 a la misma semana: {total(2026, 'casos_se42') / total(2025, 'casos_se42'):.2f} veces")

comp = (dep[dep["anio"] == 2026].set_index("departamento")[["incidencia_se42"]]
        .join(cdc.set_index("departamento")["incidencia_100mil_hab"].rename("incidencia_cdc")))
comp["dif_%"] = ((comp["incidencia_se42"] / comp["incidencia_cdc"] - 1) * 100).round(1)
print("\nIncidencia 2026 (población INEI) vs sala CDC, 5 mayores (dif_% esperado < 2 %):")
print(comp.sort_values("incidencia_se42", ascending=False).head().to_string())

print("\nMayores anomalías Niño 1+2 desde 2000:")
print(noaa.nlargest(5, "anom_nino12").to_string(index=False))

print("\nArchivos creados en datos/procesados/:")
for f in sorted(PROC.glob("*.csv")):
    print(f"  {f.name}: {len(pd.read_csv(f)):,} filas")