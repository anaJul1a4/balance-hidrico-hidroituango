"""
Sensibilidad del balance a la resolución de la precipitación.

¿El sesgo de ERA5/ERA5-Land se debe a su resolución? Dos pruebas, con la misma ETP de Hargreaves (90 m) y Budyko celda a celda:
  A. Productos llevados a 90 m con distintos remuestreos: vecino más cercano (el usado en el punto 12) y bilineal.
  B. IDEAM (kriging a 90 m) degradado a la grilla de ERA5 (0.25°) y de ERA5-Land (0.1°) por promedio de celdas, y devuelto a
     90 m por vecino más cercano: es la lluvia «observada» vista con la resolución de cada reanálisis.

Salida: resultados/16_sensibilidad_resolucion/balance_resolucion.csv
"""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject

sys.path.insert(0, str(Path(__file__).parent))
from productos import abrir  # noqa: E402

RES = Path(__file__).resolve().parents[1] / "resultados"
OUT = RES / "16_sensibilidad_resolucion"
OUT.mkdir(exist_ok=True)
SEG = 365.25 * 86400


def leer(p):
    with rasterio.open(p) as s:
        a = s.read(1).astype("float64"); a[a == s.nodata] = np.nan
        return a, s.transform, s.crs


ETP, aff, crs = leer(RES / "08_etp_etr" / "ETP_anual_hargreaves_90m_3116.tif")
P_ide = leer(RES / "04_precipitacion_interpolada" / "P_anual_kriging_90m_3116.tif")[0]
shape = ETP.shape


def budyko(p, etp):
    f = etp / p
    return p * np.sqrt(f * np.tanh(1 / f) * (1 - np.exp(-f)))


def a_90m(arr, tr_src, crs_src, metodo):
    dst = np.full(shape, np.nan)
    reproject(arr.astype("float64"), dst, src_transform=tr_src, src_crs=crs_src, src_nodata=np.nan, dst_transform=aff, dst_crs=crs,
              dst_nodata=np.nan, resampling=metodo)
    return dst


def grilla(nombre):
    """Precipitación anual media 1981–2010 de un producto en su grilla nativa (lat/lon) y su transformación."""
    p = abrir(nombre).precip.sel(time=slice("1981", "2010"))
    a = p.groupby("time.year").sum("time", min_count=12).mean("year")
    if a.lat[0] < a.lat[-1]:
        a = a.isel(lat=slice(None, None, -1))
    dx, dy = float(abs(a.lon[1] - a.lon[0])), float(abs(a.lat[1] - a.lat[0]))
    tr = from_origin(float(a.lon[0]) - dx / 2, float(a.lat[0]) + dy / 2, dx, dy)
    return a.values, tr


def degradar(p90, tr_dst, forma):
    """Promedio del campo de 90 m en las celdas de la grilla gruesa y regreso a 90 m por vecino más cercano."""
    g = np.full(forma, np.nan)
    reproject(p90, g, src_transform=aff, src_crs=crs, src_nodata=np.nan, dst_transform=tr_dst, dst_crs="EPSG:4326",
              dst_nodata=np.nan, resampling=Resampling.average)
    return a_90m(g, tr_dst, "EPSG:4326", Resampling.nearest)


# áreas de drenaje (las mismas del punto 9)
b9 = pd.read_csv(RES / "09_balance" / "balance_subcuencas.csv", dtype={"codigo": str})
sub = gpd.read_file(RES / "06_caudales" / "subcuencas_estaciones.gpkg", layer="areas_drenaje")
cuenca = gpd.read_file(RES / "01_delimitacion" / "cuenca_cauca_hidroituango.gpkg", layer="cuenca")
geoms = {r.codigo: r.geometry for r in sub.itertuples()}; geoms["HIDRO"] = cuenca.geometry[0]
mascaras = {c: ~geometry_mask([geoms[c]], out_shape=shape, transform=aff) for c in b9.codigo}
ca = abs(aff.a * aff.e) / 1e6

campos = {"IDEAM 90 m (base)": P_ide}
for n, tag in [("ERA5", "0.25°"), ("ERA5-Land", "0.1°")]:
    a, tr = grilla(n)
    campos[f"{n} → 90 m, vecino más cercano"] = a_90m(a, tr, "EPSG:4326", Resampling.nearest)
    campos[f"{n} → 90 m, bilineal"] = a_90m(a, tr, "EPSG:4326", Resampling.bilinear)
    campos[f"IDEAM degradado a {tag} ({n})"] = degradar(P_ide, tr, a.shape)

filas = []
for nom, p in campos.items():
    etr = budyko(p, ETP)
    for r in b9.itertuples():
        m = mascaras[r.codigo] & np.isfinite(p) & np.isfinite(ETP)
        A = m.sum() * ca
        P, E = np.nanmean(p[m]), np.nanmean(etr[m])
        q = (P - E) / 1000 * A * 1e6 / SEG
        filas.append({"campo": nom, "codigo": r.codigo, "estacion": r.estacion, "P": P, "ETR": E, "Q_est": q, "Q_obs": r._8,
                      "error_%": 100 * (q / r._8 - 1)})
df = pd.DataFrame(filas)
df.to_csv(OUT / "balance_resolucion.csv", index=False, encoding="utf-8-sig")
est = df[df.codigo != "HIDRO"].groupby("campo", sort=False)["error_%"].agg(MAE=lambda e: e.abs().mean(), sesgo="mean")
cie = df[df.codigo == "HIDRO"].set_index("campo")[["P", "ETR", "Q_est", "error_%"]]
res = cie.join(est).round(1)
res.to_csv(OUT / "resumen_resolucion.csv", encoding="utf-8-sig")
pd.set_option("display.width", 200)
print(res.to_string())
