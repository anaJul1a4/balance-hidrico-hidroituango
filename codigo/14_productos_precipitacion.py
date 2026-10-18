"""
Punto 10 - Productos alternativos de precipitación: CHIRPS, ERA5-Land y ERA5.

Verifica, para la cuenca delimitada, la cobertura temporal y espacial de los archivos mensuales del curso
(PRECIPITACION_COLOMBIA, 1981-2025) y calcula la precipitación anual promedio de la cuenca de cada producto.
Promedio areal: celdas cuyo centro cae dentro de la cuenca, ponderadas por cos(latitud).

Salidas: trabajo1/resultados/10_productos/
    cobertura_productos.csv     resolución, periodo, meses completos, celdas en la cuenca
    P_anual_cuenca_productos.csv precipitación anual de la cuenca 1981-2025 por producto
"""
from pathlib import Path
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
from shapely import contains_xy

sys.path.insert(0, str(Path(__file__).parent))
from productos import abrir  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "PRECIPITACION_COLOMBIA-20261003T131021Z-1-001" / "PRECIPITACION_COLOMBIA"
OUT = ROOT / "trabajo1" / "resultados" / "10_productos"
OUT.mkdir(parents=True, exist_ok=True)
PRODUCTOS = {
    "CHIRPS": ("CHIRPS/CHIRPS_mensual_Colombia_1981_2025.nc", "lat", "lon"),
    "ERA5-Land": ("ERA5_LAND/ERA5_Land_precipitacion_mensual_Colombia_1981_2025.nc", "latitude", "longitude"),
    "ERA5": ("ERA5/ERA5_precipitacion_mensual_Colombia_1981_2025.nc", "latitude", "longitude"),
}
cuenca = gpd.read_file(ROOT / "trabajo1" / "resultados" / "01_delimitacion" / "cuenca_cauca_hidroituango.gpkg",
                       layer="cuenca").to_crs(4326).geometry[0]

cob, anual = [], {}
for nom, (f, la, lo) in PRODUCTOS.items():
    ds = abrir(nom).rename({"lat": la, "lon": lo})          # CHIRPS = v2.0 (IRI); ver productos.py
    p = ds.precip
    LO, LA = np.meshgrid(ds[lo].values, ds[la].values)
    m = contains_xy(cuenca, LO, LA)
    v = p.values[:, m]
    w = np.cos(np.deg2rad(LA[m]))
    serie = pd.Series((v * w).sum(1) / w.sum(), index=pd.to_datetime(ds.time.values).to_period("M").to_timestamp())
    anual[nom] = serie.groupby(serie.index.year).sum()
    cob.append({"producto": nom, "resolución (°)": abs(float(ds[lo][1] - ds[lo][0])), "unidades": p.attrs.get("units", ""),
                "inicio": serie.index.min().strftime("%Y-%m"), "fin": serie.index.max().strftime("%Y-%m"),
                "meses": len(serie), "meses completos en la cuenca": int(np.isfinite(v).all(1).sum()),
                "celdas en la cuenca": int(m.sum()), "fuente del archivo": p.attrs.get("source", "")})
cob = pd.DataFrame(cob).set_index("producto")
anual = pd.DataFrame(anual)
cob.to_csv(OUT / "cobertura_productos.csv", encoding="utf-8-sig")
anual.round(1).to_csv(OUT / "P_anual_cuenca_productos.csv", encoding="utf-8-sig")
pd.set_option("display.width", 200)
print(cob.to_string())
print(pd.DataFrame({"1981-2010": anual.loc[1981:2010].mean(), "1991-2020": anual.loc[1991:2020].mean(),
                    "1981-2025": anual.mean()}).round(0).to_string())
