"""Descarga los datos originales del proyecto.

    uv run python scripts/obtener_datos.py

- Dengue 2000-2025: Plataforma Nacional de Datos Abiertos (CDC-MINSA), licencia ODC-By.
- Temperatura del mar Niño 1+2: NOAA Climate Prediction Center.
Si el archivo ya existe no se vuelve a bajar. Cada descarga queda anotada en
datos/originales/registro_descargas.csv (fuente, fecha y tamaño).
"""
import csv
from datetime import datetime
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
ORIG = RAIZ / "datos" / "originales"
ORIG.mkdir(parents=True, exist_ok=True)

FUENTES = {
    "dengue_2000_2025.csv": "https://www.datosabiertos.gob.pe/sites/default/files/datos_abiertos_vigilancia_dengue_2000_2025_0.csv",
    "noaa_sstoi_nino12.txt": "https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices",
}
# algunos servidores del Estado rechazan peticiones sin un User-Agent de navegador
HEADERS = {"User-Agent": "Mozilla/5.0 (proyecto academico dengue-nino-peru)"}
REGISTRO = ORIG / "registro_descargas.csv"


def descargar(nombre, url):
    destino = ORIG / nombre
    if destino.exists():
        print(f"ya existe: {nombre} ({destino.stat().st_size / 1e6:.1f} MB)")
        return
    print(f"descargando {nombre} ...")
    with requests.get(url, headers=HEADERS, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(destino, "wb") as f:
            for bloque in r.iter_content(chunk_size=1 << 20):   # de 1 MB en 1 MB, sin cargar todo en memoria
                f.write(bloque)
    mb = destino.stat().st_size / 1e6
    print(f"  listo: {mb:.1f} MB")
    nuevo = not REGISTRO.exists()
    with open(REGISTRO, "a", newline="") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(["archivo", "url", "fecha_descarga", "mb"])
        w.writerow([nombre, url, datetime.now().strftime("%Y-%m-%d %H:%M"), round(mb, 1)])


for nombre, url in FUENTES.items():
    descargar(nombre, url)
