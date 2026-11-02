"""Genera las imágenes del reel en reel/recursos/ con el estilo del video (fondo oscuro, textos grandes).

Ejecutar desde la raíz del repo, con el entorno principal:

    uv run python scripts/figuras_reel.py
"""
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.colors import BoundaryNorm, ListedColormap

warnings.filterwarnings("ignore", message="Geometry is in a geographic CRS")
RAIZ = Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesados"
SALIDA = RAIZ / "reel" / "recursos"
SALIDA.mkdir(parents=True, exist_ok=True)

# colores del reel (reel.py) + azul para los casos
FONDO, TEXTO, SUAVE, ACENTO, CAJA = "#1C1A17", "#F7F3EC", "#B8AE9F", "#F08A4B", "#2A2723"
AZUL = "#5598E7"
plt.rcParams.update({
    "figure.facecolor": FONDO, "axes.facecolor": FONDO, "savefig.facecolor": FONDO,
    "text.color": TEXTO, "axes.labelcolor": SUAVE, "xtick.color": SUAVE, "ytick.color": SUAVE,
    "axes.edgecolor": CAJA, "font.size": 15, "axes.titlesize": 19, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
})
miles = lambda v, _=None: f"{v:,.0f}".replace(",", " ")

dep = pd.read_csv(PROC / "dengue_departamento_anio.csv")
sem = pd.read_csv(PROC / "dengue_nacional_semana.csv", parse_dates=["fecha_inicio"])
mar = pd.read_csv(PROC / "nino_anomalia_mensual.csv", parse_dates=["fecha"])
epi = pd.read_csv(PROC / "nino_episodios_enfen.csv", parse_dates=["inicio", "fin"])
nombre = {"SAN MARTIN": "San Martín", "MADRE DE DIOS": "Madre de Dios", "LA LIBERTAD": "La Libertad",
          "HUANUCO": "Huánuco", "JUNIN": "Junín", "ANCASH": "Áncash", "APURIMAC": "Apurímac"}
nom = lambda d: nombre.get(d, d.title())


def guardar(fig, archivo):
    fig.savefig(SALIDA / archivo, dpi=200, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print("  ", SALIDA / archivo)


# 1. Serie: casos por semana + anomalía del mar, con los episodios del ENFEN
fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 5.4), sharex=True, gridspec_kw={"height_ratios": [1.6, 1], "hspace": 0.25})
for ax in (a1, a2):
    for _, e in epi.iterrows():
        ax.axvspan(e["inicio"], e["fin"], color=ACENTO, alpha=0.18, lw=0)
a1.plot(sem["fecha_inicio"], sem["casos"], color=AZUL, lw=1.6)
a1.yaxis.set_major_formatter(miles)
a1.set_title("Casos de dengue por semana, Perú", pad=10)
for (_, e), alto in zip(epi.iterrows(), (0.55, 0.97)):
    a1.text(e["inicio"] - pd.Timedelta(days=60), a1.get_ylim()[1] * alto, e["episodio"].replace("El Niño costero", "Niño costero\n"),
            ha="right", va="top", fontsize=12, color=ACENTO, fontweight="bold", linespacing=1.1)
a2.plot(mar["fecha"], mar["anom_nino12"], color=ACENTO, lw=2)
a2.axhline(0, color=SUAVE, lw=0.8)
a2.set_title("Mar frente a la costa norte: anomalía en °C", fontsize=15, pad=6)
pico = mar.loc[mar["anom_nino12"].idxmax()]
a2.annotate(f"+{pico['anom_nino12']:.2f} °C", (pico["fecha"], pico["anom_nino12"]), xytext=(-8, -4),
            textcoords="offset points", ha="right", fontsize=14, fontweight="bold", color=TEXTO)
a2.set_xlim(pd.Timestamp("2000-01-01"), mar["fecha"].max() + pd.Timedelta(days=45))
a2.xaxis.set_major_locator(mdates.YearLocator(4))
a2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
guardar(fig, "serie.png")

# 2. Por año: casos semanas 1-42 (comparable con 2026)
nac = dep.groupby("anio")["casos_se42"].sum()
fig, ax = plt.subplots(figsize=(9, 5))
colores = [ACENTO if a == 2026 else AZUL for a in nac.index]
ax.bar(nac.index, nac.values, color=colores, width=0.75)
for a in (2024, 2026):
    ax.text(a, nac[a] + nac.max() * 0.02, miles(nac[a]), ha="center", va="bottom", fontsize=13, fontweight="bold")
ax.yaxis.set_major_formatter(miles)
ax.set_xticks([2000, 2005, 2010, 2015, 2020, 2026])
ax.set_title("Casos de dengue, semanas 1–42 de cada año", pad=10)
guardar(fig, "anual.png")

# 3. Ranking 2026 por casos (los 3 primeros resaltados)
d26 = dep[dep["anio"] == 2026].nlargest(8, "casos_se42").iloc[::-1]
fig, ax = plt.subplots(figsize=(9, 5))
colores = [ACENTO if i >= len(d26) - 3 else AZUL for i in range(len(d26))]
ax.barh([nom(d) for d in d26["departamento"]], d26["casos_se42"], color=colores, height=0.7)
for y, v in enumerate(d26["casos_se42"]):
    ax.text(v + d26["casos_se42"].max() * 0.01, y, miles(v), va="center", fontsize=13)
ax.xaxis.set_visible(False)
ax.spines["bottom"].set_visible(False)
ax.set_title("Casos de dengue 2026 (semanas 1–42)", pad=10)
guardar(fig, "ranking.png")

# 4. Mapa de incidencia 2026
distritos = gpd.read_file(RAIZ / "datos" / "originales" / "distritos_peru.geojson")
deps = distritos.dissolve(by="departamento", as_index=False)[["departamento", "geometry"]]
deps["geometry"] = deps.buffer(0.001).buffer(-0.001)
deps = deps.merge(dep[dep["anio"] == 2026][["departamento", "incidencia_se42"]], on="departamento")
cortes = [0, 0.01, 50, 150, 400, 700, 1000, 1400]
rampa = ListedColormap(["#3a3833", "#104281", "#1c5cab", "#2a78d6", "#5598e7", "#86b6ef", "#cde2fb"])   # fondo oscuro: más claro = más casos
fig, ax = plt.subplots(figsize=(9, 5.6))
deps.plot(column="incidencia_se42", cmap=rampa, norm=BoundaryNorm(cortes, rampa.N), ax=ax,
          edgecolor=FONDO, linewidth=0.6)
ax.set_axis_off()
ax.set_title("Casos por 100 mil hab., 2026 (semanas 1–42)", pad=8)
x0 = ax.get_xlim()[1] + 0.5
top = deps.nlargest(2, "incidencia_se42")
texto = "\n\n".join(f"{nom(r.departamento)}\n{miles(r.incidencia_se42)}" for r in top.itertuples())
fig.text(0.70, 0.62, texto, fontsize=19, fontweight="bold", va="top", color=TEXTO)
fig.text(0.70, 0.30, "Perú: 238", fontsize=16, color=SUAVE, va="top")
ax.set_position([0.02, 0.02, 0.62, 0.86])
guardar(fig, "mapa.png")

# 5. Tablero: los 4 KPIs
kpis = [("Casos 2026", "82 554", "semanas 1–42"), ("Incidencia", "238.2", "por 100 mil hab."),
        ("Frente a 2025", "+153 %", "a la misma semana"), ("Mayor incidencia", "Madre de Dios", "1 312 por 100 mil hab.")]
fig = plt.figure(figsize=(9, 5))
fig.text(0.03, 0.93, "Tablero interactivo · datos abiertos", fontsize=16, color=SUAVE, va="top")
for i, (et, val, det) in enumerate(kpis):
    x, y = 0.03 + (i % 2) * 0.49, 0.80 - (i // 2) * 0.38
    fig.patches.append(plt.Rectangle((x, y - 0.32), 0.46, 0.32, transform=fig.transFigure, color=CAJA, zorder=0))
    fig.text(x + 0.025, y - 0.05, et, fontsize=14, color=SUAVE, va="top")
    fig.text(x + 0.025, y - 0.12, val, fontsize=28 if len(val) < 9 else 22, fontweight="bold", va="top")
    fig.text(x + 0.025, y - 0.25, det, fontsize=12, color=SUAVE, va="top")
guardar(fig, "tablero.png")
