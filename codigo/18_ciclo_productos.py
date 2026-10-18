"""
Punto 14 - Comparación del ciclo anual de la precipitación entre IDEAM (kriging mensual, punto 13), CHIRPS, ERA5-Land y ERA5.

Ciclo de cada producto: media mensual 1981-2010 en su grilla → vecino más cercano a la grilla de 90 m → promedio sobre
la cuenca (y sobre las tres regiones del punto 13). Indicadores con n = 12 meses:
    Bias = (1/n) Σ (P_prod − P_IDEAM) ;  RMSE = √[(1/n) Σ (P_prod − P_IDEAM)²] ;  r de Pearson
Diagrama de Taylor: desviación estándar normalizada σ_prod/σ_IDEAM, correlación r y RMSE centrado normalizado.

Salidas: trabajo1/resultados/14_ciclo_productos/
    ciclos_productos.csv, metricas_ciclo.csv, metricas_regiones.csv, taylor.png, ciclos_productos.png
"""
from pathlib import Path
import sys

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import xarray as xr
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject

sys.path.insert(0, str(Path(__file__).parent))
from productos import abrir  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "PRECIPITACION_COLOMBIA-20261003T131021Z-1-001" / "PRECIPITACION_COLOMBIA"
RES = ROOT / "trabajo1" / "resultados"
OUT = RES / "14_ciclo_productos"
OUT.mkdir(parents=True, exist_ok=True)
MES3 = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
PRODUCTOS = {
    "CHIRPS": ("CHIRPS/CHIRPS_mensual_Colombia_1981_2025.nc", "lat", "lon"),
    "ERA5-Land": ("ERA5_LAND/ERA5_Land_precipitacion_mensual_Colombia_1981_2025.nc", "latitude", "longitude"),
    "ERA5": ("ERA5/ERA5_precipitacion_mensual_Colombia_1981_2025.nc", "latitude", "longitude"),
}

with rasterio.open(RES / "01_delimitacion" / "dem_cuenca_90m_3116.tif") as s:
    mask = ~s.read(1, masked=True).mask; aff, shape = s.transform, s.shape
with rasterio.open(RES / "13_climatologia" / "P_mensual_kriging_90m_3116.tif") as s:
    ide = s.read().astype("float64"); ide[ide == -9999] = np.nan

sub = gpd.read_file(RES / "06_caudales" / "subcuencas_estaciones.gpkg", layer="areas_drenaje").set_index("codigo")
msk = lambda gm: ~geometry_mask([gm], out_shape=shape, transform=aff)
balsa, virginia = msk(sub.geometry["26027010"]), msk(sub.geometry["26177030"])
REG = {"Cuenca": mask, "Alto Cauca": balsa & mask, "Valle del Cauca": virginia & ~balsa & mask, "Cauca medio": mask & ~virginia}

ciclos = {r: {"IDEAM": [np.nanmean(ide[m][R]) for m in range(12)]} for r, R in REG.items()}
for nom, (f, la, lo) in PRODUCTOS.items():
    ds = abrir(nom).rename({"lat": la, "lon": lo})          # CHIRPS = v2.0 (IRI); ver productos.py
    clim = ds.precip.sel(time=slice("1981-01-01", "2010-12-31")).groupby("time.month").mean("time")
    if clim[la][0] < clim[la][-1]:
        clim = clim.isel({la: slice(None, None, -1)})
    lats, lons = clim[la].values, clim[lo].values
    dx, dy = abs(lons[1] - lons[0]), abs(lats[1] - lats[0])
    tr = from_origin(lons[0] - dx / 2, lats[0] + dy / 2, dx, dy)
    for r in REG:
        ciclos[r][nom] = []
    for m in range(12):
        dst = np.full(shape, np.nan)
        reproject(clim.isel(month=m).values.astype("float64"), dst, src_transform=tr, src_crs="EPSG:4326", dst_transform=aff,
                  dst_crs="EPSG:3116", resampling=Resampling.nearest, src_nodata=np.nan, dst_nodata=np.nan)
        for r, R in REG.items():
            ciclos[r][nom].append(np.nanmean(dst[R]))
cic = pd.concat({r: pd.DataFrame(v, index=MES3) for r, v in ciclos.items()}, names=["región", "mes"])
cic.round(2).to_csv(OUT / "ciclos_productos.csv", encoding="utf-8-sig")


def metricas(ref, p):
    ref, p = np.asarray(ref), np.asarray(p)
    d = p - ref
    rc = np.sqrt(np.mean(((p - p.mean()) - (ref - ref.mean())) ** 2))
    return {"Sesgo (mm/mes)": d.mean(), "Sesgo (%)": 100 * d.mean() / ref.mean(), "RMSE (mm/mes)": np.sqrt(np.mean(d ** 2)),
            "r": np.corrcoef(ref, p)[0, 1], "σ normalizada": p.std() / ref.std(), "RMSE centrado normalizado": rc / ref.std(),
            "Total anual (mm)": p.sum(), "Mes máximo": MES3[int(p.argmax())], "Mes mínimo": MES3[int(p.argmin())],
            "Amplitud máx−mín (mm)": p.max() - p.min(), "Amplitud relativa (máx−mín)/media": (p.max() - p.min()) / p.mean(),
            "Meses de máximos (2 picos)": ", ".join(MES3[i] for i in sorted(np.argsort(-p)[:2])),
            "Meses de mínimos (2)": ", ".join(MES3[i] for i in sorted(np.argsort(p)[:2]))}


met = pd.DataFrame({k: metricas(ciclos["Cuenca"]["IDEAM"], ciclos["Cuenca"][k]) for k in ["IDEAM", *PRODUCTOS]}).T
met.to_csv(OUT / "metricas_ciclo.csv", encoding="utf-8-sig")
mreg = pd.DataFrame({(r, k): {m: metricas(ciclos[r]["IDEAM"], ciclos[r][k])[m] for m in ["r", "Sesgo (%)", "RMSE (mm/mes)"]}
                     for r in REG for k in PRODUCTOS}).T
mreg.to_csv(OUT / "metricas_regiones.csv", encoding="utf-8-sig")
pd.set_option("display.width", 250)
print(cic.loc["Cuenca"].round(0).T.to_string())
print(met.round(3).to_string())
print(mreg.round(2).to_string())

# ----------------------------------------------------------------------------- figuras
COL = {"IDEAM": "#222222", "CHIRPS": "#2a78d6", "ERA5-Land": "#eb6834", "ERA5": "#1baf7a"}
fig, axs = plt.subplots(1, 2, figsize=(13, 4.8))
for k, c in COL.items():
    y = np.array(ciclos["Cuenca"][k])
    axs[0].plot(MES3, y, "-o", color=c, lw=2 if k == "IDEAM" else 1.6, ms=5, label=k)
    axs[1].plot(MES3, 100 * y / y.sum(), "-o", color=c, lw=2 if k == "IDEAM" else 1.6, ms=5, label=k)
axs[0].set_ylabel("Precipitación media mensual (mm)"); axs[0].set_title("Ciclo anual (magnitud)", fontsize=10)
axs[1].set_ylabel("% del total anual"); axs[1].set_title("Ciclo normalizado (estacionalidad)", fontsize=10)
for a in axs:
    a.grid(alpha=0.3); a.legend(fontsize=8)
fig.suptitle("Cuenca del río Cauca hasta Hidroituango, 1981–2010", fontsize=11)
fig.tight_layout(); fig.savefig(OUT / "ciclos_productos.png", dpi=200); plt.close(fig)

# diagrama de Taylor (normalizado por la σ del IDEAM)
fig = plt.figure(figsize=(7, 6.2))
ax = fig.add_subplot(111, projection="polar")
ax.set_thetamin(0); ax.set_thetamax(90)
smax = 2.0
rs = np.array([0.0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0])
ax.set_thetagrids(np.degrees(np.arccos(rs)), [f"{r:g}" for r in rs])
ax.set_rlim(0, smax); ax.set_rlabel_position(90)
tt = np.linspace(0, np.pi / 2, 200)
for rc in [0.25, 0.5, 0.75, 1.0, 1.25, 1.5]:                      # contornos de RMSE centrado normalizado
    x = 1 + rc * np.cos(np.linspace(0, np.pi, 300)); y = rc * np.sin(np.linspace(0, np.pi, 300))
    rr, th = np.hypot(x, y), np.arctan2(y, x)
    ok = (rr <= smax) & (th <= np.pi / 2)
    ax.plot(th[ok], rr[ok], color="0.6", lw=0.7, ls="--")
ax.plot(tt, np.ones_like(tt), color="0.3", lw=0.8, ls=":")
ax.plot(0, 1, "k*", ms=16, label="IDEAM (referencia)")
for k in PRODUCTOS:
    r, s = met.loc[k, "r"], met.loc[k, "σ normalizada"]
    ax.plot(np.arccos(r), s, "o", ms=11, color=COL[k], mec="black", label=f"{k}  (r = {r:.2f}, σ = {s:.2f})")
ax.text(np.radians(45), smax * 1.13, "Correlación", ha="center", fontsize=9, rotation=-45)
ax.set_xlabel("Desviación estándar normalizada (σ producto / σ IDEAM)", fontsize=9, labelpad=20)
ax.legend(loc="upper right", bbox_to_anchor=(1.32, 1.12), fontsize=8)
ax.set_title("Diagrama de Taylor del ciclo anual (n = 12)\nlíneas discontinuas: RMSE centrado normalizado", fontsize=10, pad=24)
fig.tight_layout(); fig.savefig(OUT / "taylor.png", dpi=200, bbox_inches="tight"); plt.close(fig)
print("listo")
