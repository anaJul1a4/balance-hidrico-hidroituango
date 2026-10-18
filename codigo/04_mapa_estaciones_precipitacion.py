"""
Punto 3 - Estaciones de precipitación IDEAM (promedios climatológicos 1981-2010) dentro de la cuenca
y en su vecindario.
Salidas: trabajo1/resultados/03_estaciones_precipitacion/
    estaciones_precipitacion.gpkg / .csv   (dentro = True/False, completa = 12 meses con dato)
    mapa_estaciones_precipitacion.png
"""
import re
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import BoundaryNorm, LightSource
from matplotlib.lines import Line2D

import sys  # noqa: E402
sys.path.insert(0, str(Path(__file__).parent))
import escalas as E  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEL = ROOT / "trabajo1" / "resultados" / "01_delimitacion"
OUT = ROOT / "trabajo1" / "resultados" / "03_estaciones_precipitacion"
OUT.mkdir(parents=True, exist_ok=True)
CRS = "EPSG:3116"
VECINDARIO_M = 20000
MESES = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]


def dms(s):
    """'75°52'48.8"W' -> -75.8802"""
    s = str(s).replace(",", ".")
    m = re.findall(r"[\d.]+", s)
    if len(m) < 3:
        return np.nan
    v = float(m[0]) + float(m[1]) / 60 + float(m[2]) / 3600
    return -v if ("W" in s or "S" in s) else v


xl = ROOT / "CLIMATOLOGIA_IDEAM" / "Promedios Climatológicos  1981 - 2010.xlsx"
p = pd.read_excel(xl, sheet_name="Lluvia", header=1, usecols=range(21))  # sólo el bloque de precipitación
p["lon"], p["lat"] = p.LONGITUD.map(dms), p.LATITUD.map(dms)
p = p.dropna(subset=["lon", "lat"])  # quita las filas de convenciones al final de la hoja
p["completa"] = p[MESES].notna().all(axis=1)
gp = gpd.GeoDataFrame(p, geometry=gpd.points_from_xy(p.lon, p.lat), crs=4326).to_crs(CRS)

cuenca = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="cuenca")
geom = cuenca.geometry[0]
gp["dist_km"] = gp.distance(geom) / 1000
gp = gp[gp.dist_km <= VECINDARIO_M / 1000].copy()
gp["dentro"] = gp.dist_km == 0
gp.to_file(OUT / "estaciones_precipitacion.gpkg", layer="estaciones")
gp.drop(columns="geometry").to_csv(OUT / "estaciones_precipitacion.csv", index=False, encoding="utf-8-sig")

rio = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="rio_principal")
with rasterio.open(DEL / "dem_cuenca_90m_3116.tif") as src:
    z = src.read(1, masked=True).filled(np.nan).astype(float)
    ext = (src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top)
    dx = src.res[0]

fig, ax = plt.subplots(figsize=(10, 15))
hs = LightSource(azdeg=315, altdeg=45).hillshade(np.nan_to_num(z, nan=np.nanmin(z)), vert_exag=3, dx=dx, dy=dx)
ax.imshow(np.where(np.isnan(z), np.nan, hs), cmap="gray", vmin=0, vmax=1.3, extent=ext, zorder=1)
gpd.GeoSeries([geom.buffer(VECINDARIO_M)], crs=CRS).boundary.plot(ax=ax, color="0.4", lw=0.8, ls="--", zorder=2)
rio.plot(ax=ax, color="#08519c", linewidth=1.6, zorder=3)
cuenca.boundary.plot(ax=ax, color="black", linewidth=1.2, zorder=4)

bins = E.P_CL  # escala común de P anual (escalas.py)
cmap, norm = E.P["cmap"], E.P["norm"]
ok = gp[gp.completa]
for dentro, mk, sz in [(False, "^", 28), (True, "o", 30)]:
    s = ok[ok.dentro == dentro]
    ax.scatter(s.geometry.x, s.geometry.y, c=s.ANUAL, cmap=cmap, norm=norm, marker=mk, s=sz,
               edgecolors="black", linewidths=0.4, zorder=6)
inc = gp[~gp.completa]
ax.scatter(inc.geometry.x, inc.geometry.y, marker="x", c="red", s=22, linewidths=0.9, zorder=6)

sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
cb = E.barra(fig, sm, E.P, ok.ANUAL, ax=ax, shrink=0.35, pad=0.02)
cb.set_label("Precipitación media anual 1981–2010 (mm/año)", fontsize=8); cb.ax.tick_params(labelsize=7)

minx, miny, maxx, maxy = cuenca.total_bounds
ax.set_xlim(minx - 35000, maxx + 35000); ax.set_ylim(miny - 25000, maxy + 25000)
ax.set_aspect("equal"); ax.ticklabel_format(style="plain"); ax.tick_params(labelsize=7)
ax.set_xlabel("Este (m)", fontsize=8); ax.set_ylabel("Norte (m)", fontsize=8)
plt.setp(ax.get_yticklabels(), rotation=90, va="center")
ax.grid(color="0.7", lw=0.3, ls=":")
ax.annotate("N", xy=(0.92, 0.70), xytext=(0.92, 0.645), xycoords="axes fraction", ha="center", fontsize=14,
            fontweight="bold", arrowprops=dict(facecolor="black", width=4, headwidth=12))

n_in, n_out = (ok.dentro).sum(), (~ok.dentro).sum()
ax.legend(handles=[
    Line2D([], [], ls="", marker="o", ms=7, mfc="#41b6c4", mec="black", label=f"Dentro de la cuenca ({n_in})"),
    Line2D([], [], ls="", marker="^", ms=7, mfc="#41b6c4", mec="black", label=f"Vecindario ≤ 20 km ({n_out})"),
    Line2D([], [], ls="", marker="x", ms=7, mec="red", label=f"Serie incompleta, < 12 meses ({len(inc)})"),
    Line2D([], [], color="0.4", lw=0.8, ls="--", label="Límite del vecindario (20 km)"),
    Line2D([], [], color="black", lw=1.2, label="Límite de la cuenca"),
    Line2D([], [], color="#08519c", lw=1.6, label="Río Cauca"),
], loc="upper left", fontsize=8, framealpha=0.92)
ax.set_title("Estaciones de precipitación IDEAM (promedios 1981–2010)\nCuenca del río Cauca hasta Hidroituango",
             fontsize=11, fontweight="bold")
ax.text(0.99, 0.005, "MAGNA-SIRGAS / Colombia Bogotá (EPSG:3116)\nFuente: IDEAM, Promedios Climatológicos 1981–2010",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=6.5)
fig.tight_layout()
fig.savefig(OUT / "mapa_estaciones_precipitacion.png", dpi=300)

print(f"dentro: {gp.dentro.sum()}  vecindario: {(~gp.dentro).sum()}  incompletas: {len(inc)}")
print(gp.groupby("dentro").ANUAL.describe().round(0).to_string())
print(gp.groupby(["dentro", "CAT"]).size().unstack(0).fillna(0).astype(int).to_string())
print(gp.groupby("dentro").ELEV.describe().round(0).to_string())
