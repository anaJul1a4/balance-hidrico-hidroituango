"""
Punto 2 - Mapa de la cuenca del río Cauca hasta Hidroituango.
Requiere haber corrido 01_delimitacion_glo30.py
"""
import zipfile
from pathlib import Path

import geopandas as gpd
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import LightSource
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "trabajo1" / "resultados" / "01_delimitacion"
GPKG = OUT / "cuenca_cauca_hidroituango.gpkg"
CRS = "EPSG:3116"

cuenca = gpd.read_file(GPKG, layer="cuenca")
dren = gpd.read_file(GPKG, layer="drenajes")
rio = gpd.read_file(GPKG, layer="rio_principal")
cierre = gpd.read_file(GPKG, layer="punto_cierre")

# departamentos (zip del curso, MAGNA-SIRGAS Origen Nacional -> EPSG:3116)
tmp = OUT / "_deptos"
if not tmp.exists():
    zipfile.ZipFile(ROOT / "CARTOGRAFIA" / "Departamentos_Junio_2026_shp.zip").extractall(tmp)
deptos = gpd.read_file(next(tmp.rglob("*.shp"))).to_crs(CRS)
deptos["geometry"] = deptos.simplify(500)
col_nom = next(c for c in deptos.columns if "NOM" in c.upper() or "DPTO" in c.upper() and deptos[c].dtype == object)

with rasterio.open(OUT / "dem_cuenca_90m_3116.tif") as src:
    z = src.read(1, masked=True).astype(float)
    ext = (src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top)
    dx = src.res[0]

minx, miny, maxx, maxy = cuenca.total_bounds
pad = 25000
xlim, ylim = (minx - pad, maxx + pad), (miny - pad, maxy + pad)

fig = plt.figure(figsize=(10, 14))
ax = fig.add_axes([0.06, 0.05, 0.70, 0.88])

# DEM + sombreado
ls = LightSource(azdeg=315, altdeg=45)
zf = z.filled(np.nan)
hs = ls.hillshade(np.nan_to_num(zf, nan=np.nanmin(zf)), vert_exag=3, dx=dx, dy=dx)
cmap = plt.get_cmap("terrain")
norm = plt.Normalize(0, np.nanmax(zf))
im = ax.imshow(zf, cmap=cmap, norm=norm, extent=ext, zorder=1)
ax.imshow(np.where(np.isnan(zf), np.nan, hs), cmap="gray", alpha=0.35, extent=ext, zorder=2)

deptos.boundary.plot(ax=ax, color="0.35", lw=0.6, ls="--", zorder=3)
for _, d in deptos.iterrows():
    p = d.geometry.representative_point()
    nom = str(d[col_nom]).title()
    if xlim[0] < p.x < xlim[1] and ylim[0] < p.y < ylim[1] and "Litigio" not in nom:
        ax.text(p.x, p.y, nom.upper(), fontsize=7, color="0.2", ha="center", style="italic", zorder=8,
                path_effects=[pe.withStroke(linewidth=2, foreground="white")])

# drenajes, grosor según orden de Strahler
omax = dren.orden.max()
dren.plot(ax=ax, color="#1f4e9c", linewidth=0.3 + 0.35 * (dren.orden - 1), zorder=4)
rio.plot(ax=ax, color="#08306b", linewidth=2.2, zorder=5)
cuenca.boundary.plot(ax=ax, color="black", linewidth=1.4, zorder=6)
cierre.plot(ax=ax, color="red", marker="^", markersize=120, edgecolor="black", zorder=7)
cx, cy = cierre.geometry[0].x, cierre.geometry[0].y
ax.annotate("Punto de cierre\nPresa Hidroituango", (cx, cy), xytext=(cx + 30000, cy + 8000), fontsize=8,
            arrowprops=dict(arrowstyle="-", lw=0.7), zorder=8)

ax.set_xlim(xlim); ax.set_ylim(ylim); ax.set_aspect("equal")
ax.ticklabel_format(style="plain")
ax.tick_params(labelsize=7)
ax.set_xlabel("Este (m)", fontsize=8); ax.set_ylabel("Norte (m)", fontsize=8)
plt.setp(ax.get_yticklabels(), rotation=90, va="center")
ax.grid(color="0.6", lw=0.3, ls=":")

# norte
ax.annotate("N", xy=(0.92, 0.965), xytext=(0.92, 0.905), xycoords="axes fraction", ha="center", fontsize=14,
            fontweight="bold", arrowprops=dict(facecolor="black", width=4, headwidth=12))
# escala gráfica 100 km
sx, sy = xlim[0] + 15000, ylim[0] + 15000
for i, col in enumerate(["black", "white", "black", "white"]):
    ax.add_patch(plt.Rectangle((sx + i * 25000, sy), 25000, 4000, fc=col, ec="black", lw=0.6, zorder=9))
for i, t in enumerate(["0", "25", "50", "75", "100 km"]):
    ax.text(sx + i * 25000, sy + 6500, t, ha="center", fontsize=7, zorder=9)

ax.legend(handles=[
    Patch(fc="none", ec="black", lw=1.4, label="Límite de la cuenca"),
    Line2D([], [], color="#08306b", lw=2.2, label="Río principal (Cauca)"),
    Line2D([], [], color="#1f4e9c", lw=1.0, label=f"Red de drenaje (Strahler 1–{omax}, A ≥ 25 km²)"),
    Line2D([], [], marker="^", color="w", mfc="red", mec="black", ms=10, label="Punto de cierre"),
    Line2D([], [], color="0.35", lw=0.6, ls="--", label="Límite departamental"),
], loc="upper left", fontsize=8, framealpha=0.9)

cax = fig.add_axes([0.80, 0.35, 0.025, 0.30])
cb = fig.colorbar(im, cax=cax); cb.set_label("Elevación (m s.n.m.)", fontsize=8); cb.ax.tick_params(labelsize=7)

# mapa de localización
axi = fig.add_axes([0.74, 0.70, 0.24, 0.24])
deptos.plot(ax=axi, color="0.9", edgecolor="0.6", lw=0.3)
cuenca.plot(ax=axi, color="#c0392b")
axi.set_xticks([]); axi.set_yticks([]); axi.set_xlabel(""); axi.set_ylabel(""); axi.set_title("Localización", fontsize=8)
axi.set_xlim(deptos.total_bounds[0], 1.85e6); axi.set_ylim(deptos.total_bounds[1], deptos.total_bounds[3])

area = cuenca.area_km2[0]
fig.text(0.78, 0.27,
         "Sistema de coordenadas:\nMAGNA-SIRGAS / Colombia Bogotá\n(EPSG:3116), Transversa de\nMercator, datum MAGNA\n\n"
         f"Área: {area:,.0f} km²\n\nFuente DEM: Copernicus GLO-30\n(remuestreado a 90 m)\nDelimitación: D8 (pysheds)\n"
         "Límites: DANE/IGAC 2026", fontsize=7, va="top")
fig.suptitle("Cuenca del río Cauca hasta la presa de Hidroituango", fontsize=13, fontweight="bold", y=0.975)
fig.savefig(OUT / "mapa_cuenca_cauca_hidroituango.png", dpi=300)
print("mapa guardado")

# perfil longitudinal del río principal
perf = np.load(OUT / "perfil_rio_principal.npy")
f2, a2 = plt.subplots(figsize=(9, 3.5))
a2.plot(perf[:, 0], perf[:, 1], color="#08306b")
a2.set_xlabel("Distancia desde el nacimiento (km)"); a2.set_ylabel("Elevación (m s.n.m.)")
a2.set_title("Perfil longitudinal del río Cauca hasta Hidroituango"); a2.grid(alpha=0.3)
f2.tight_layout(); f2.savefig(OUT / "perfil_rio_principal.png", dpi=200)
