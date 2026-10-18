"""
Verificación del punto de cierre: la cuenca debe llegar sólo hasta la presa de Hidroituango, que está entre las
desembocaduras del río San Andrés (aguas arriba, incluido) y del río Ituango (aguas abajo, excluido).

Comprobaciones:
  1. Distancia del cierre a la presa (Wikipedia: 7°08'04" N, 75°39'43" W).
  2. Área acumulada a lo largo del Cauca ±30 km del cierre: posición de las confluencias.
  3. Comparación con el área acumulada de HydroSHEDS (sa_riv_30s, red de drenaje del curso).
Salida: trabajo1/resultados/01_delimitacion/verificacion_cierre.png y verificacion_cierre.csv
"""
import sys
from pathlib import Path

import numpy as np
np.in1d = np.isin

import geopandas as gpd
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import pandas as pd
import rasterio
from matplotlib.colors import LightSource
from matplotlib.lines import Line2D
from pyproj import Transformer
from pysheds.grid import Grid
from pysheds.view import Raster

sys.path.insert(0, str(Path(__file__).parent))
from priority_flood import condicionar  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEL = ROOT / "trabajo1" / "resultados" / "01_delimitacion"
DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)
OFF = {64: (-1, 0), 128: (-1, 1), 1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1)}
PRESA = (-75.66194, 7.13444)
CELDA_30S = 0.849                              # km² de una celda de 30" a ≈ 5° N (HydroSHEDS)

grid = Grid.from_raster(str(DEL / "dem_glo30_90m_3116.tif"))
dem = grid.read_raster(str(DEL / "dem_glo30_90m_3116.tif"))
F = np.asarray(grid.flowdir(Raster(condicionar(dem), viewfinder=dem.viewfinder), dirmap=DIRMAP))
A = np.asarray(grid.accumulation(Raster(F, viewfinder=dem.viewfinder), dirmap=DIRMAP)) * 0.0081
aff = grid.affine
to3116 = Transformer.from_crs(4326, 3116, always_xy=True)
cierre = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="punto_cierre").geometry[0]
c0, r0 = map(int, ~aff * (cierre.x, cierre.y))

# recorrido del cauce principal ±330 celdas
up, (r, c) = [(r0, c0)], (r0, c0)
for _ in range(330):
    cand = [(r - dr, c - dc) for code, (dr, dc) in OFF.items() if F[r - dr, c - dc] == code]
    r, c = max(cand, key=lambda p: A[p]); up.append((r, c))
dn, (r, c) = [], (r0, c0)
for _ in range(360):
    dr, dc = OFF[F[r, c]]; r, c = r + dr, c + dc; dn.append((r, c))
path = up[::-1] + dn
xy = np.array([aff * (b + .5, a + .5) for a, b in path])
s = np.r_[0, np.cumsum(np.hypot(*np.diff(xy, axis=0).T))]; s -= s[len(up) - 1]
ent = []
for i in range(1, len(path)):
    salto = A[path[i]] - A[path[i - 1]]
    if salto > 100:
        ent.append({"km desde el cierre": s[i] / 1000, "área antes (km²)": A[path[i - 1]], "aporte (km²)": salto,
                    "x": xy[i, 0], "y": xy[i, 1]})
ent = pd.DataFrame(ent)
xp, yp = to3116.transform(*PRESA)
d_presa = np.hypot(cierre.x - xp, cierre.y - yp)

# HydroSHEDS
hs = gpd.read_file(f"zip://{ROOT / 'CARTOGRAFIA' / 'RED_DRENAJE.zip'}!sa_riv_30s_col.shp")
cerca = hs[hs.distance(cierre) < 1500].sort_values("UP_CELLS")
cauca_arriba = cerca[cerca.UP_CELLS > 40000].UP_CELLS.min()
ituango_hs = cerca[(cerca.UP_CELLS > 300) & (cerca.UP_CELLS < 2000)].UP_CELLS.max()

res = pd.Series({"Área de la cuenca delimitada (km²)": A[r0, c0], "Distancia cierre – presa (m)": d_presa,
                 "Área HydroSHEDS aguas arriba del río Ituango (km²)": cauca_arriba * CELDA_30S,
                 "Diferencia con HydroSHEDS (%)": 100 * (A[r0, c0] / (cauca_arriba * CELDA_30S) - 1),
                 "Río Ituango en el DEM (km²)": float(ent.loc[ent["km desde el cierre"].between(0, 2), "aporte (km²)"].iloc[0]),
                 "Río Ituango en HydroSHEDS (km²)": ituango_hs * CELDA_30S,
                 "Río San Andrés en el DEM (km²)": float(ent.loc[ent["km desde el cierre"].between(-10, -3), "aporte (km²)"].iloc[0])})
res.to_csv(DEL / "verificacion_cierre.csv", encoding="utf-8-sig")
print(res.round(1).to_string()); print(ent.round(1).drop(columns=["x", "y"]).to_string(index=False))

# ----------------------------------------------------------------------------- mapa de detalle
W = 22000
x0, x1, y0, y1 = cierre.x - W, cierre.x + W, cierre.y - W, cierre.y + W
r_a, c_a = map(int, (~aff * (x0, y1))[::-1]); r_b, c_b = map(int, (~aff * (x1, y0))[::-1])
r_a, c_a = max(r_a, 0), max(c_a, 0); r_b, c_b = min(r_b, F.shape[0]), min(c_b, F.shape[1])   # ventana dentro del DEM
while (np.asarray(dem)[r_a, c_a:c_b] <= -1000).any():           # descarta filas sin datos en el borde norte del DEM
    r_a += 1
Zs = np.asarray(dem)[r_a:r_b, c_a:c_b].astype(float); As = A[r_a:r_b, c_a:c_b]
ext = (aff.c + c_a * aff.a, aff.c + c_b * aff.a, aff.f + r_b * aff.e, aff.f + r_a * aff.e)
cuenca = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="cuenca")
fig, ax = plt.subplots(figsize=(9, 9))
ls = LightSource(azdeg=315, altdeg=40)
ax.imshow(ls.shade(Zs, cmap=plt.get_cmap("gist_earth"), vert_exag=2, blend_mode="soft", dx=90, dy=90, vmin=0, vmax=3500), extent=ext)
for lim, lw in [(20, .6), (300, 1.3), (5000, 3)]:
    m = np.ma.masked_where(As < lim, np.ones_like(As))
    ax.contour(np.linspace(ext[0], ext[1], As.shape[1]), np.linspace(ext[3], ext[2], As.shape[0]), As >= lim, levels=[.5],
               colors="#1f5fbf", linewidths=lw)
cuenca.boundary.plot(ax=ax, color="black", linewidth=2.2, zorder=5)
gpd.GeoSeries([cuenca.geometry[0]]).plot(ax=ax, facecolor="#ffffff", alpha=0.18, zorder=4)
ax.plot(cierre.x, cierre.y, "^", ms=15, mfc="red", mec="black", zorder=7, label=f"Punto de cierre ({res['Área de la cuenca delimitada (km²)']:,.0f} km²)".replace(",", " "))
ax.plot(xp, yp, "*", ms=17, mfc="yellow", mec="black", zorder=7, label=f"Presa (7°08′04″ N, 75°39′43″ W) · {d_presa:.0f} m del cierre")
txt = dict(fontsize=10, fontweight="bold", path_effects=[pe.withStroke(linewidth=3, foreground="white")], zorder=8)
ki = ent[ent["km desde el cierre"].between(0, 2)].iloc[0]; ks = ent[ent["km desde el cierre"].between(-10, -3)].iloc[0]
ax.annotate(f"Río Ituango\n{ki['aporte (km²)']:.0f} km² · EXCLUIDO\n(entra {ki['km desde el cierre'] * 1000:.0f} m aguas abajo)",
            (ki.x, ki.y), xytext=(ki.x - 17000, ki.y + 9000), arrowprops=dict(arrowstyle="->", lw=1.2), color="#b30000", **txt)
ax.annotate(f"Río San Andrés\n{ks['aporte (km²)']:.0f} km² · incluido", (ks.x, ks.y), xytext=(ks.x + 3000, ks.y - 12000),
            arrowprops=dict(arrowstyle="->", lw=1.2), color="#004d00", **txt)
ax.text(cierre.x + 9000, cierre.y + 9500, "Río Cauca →\nhacia Pto. Valdivia", color="#0b2f6b", **txt)
ax.text(cierre.x - 20000, cierre.y - 19000, "Río Cauca\n(aguas arriba)", color="#0b2f6b", **txt)
ax.set_xlim(x0, x1); ax.set_ylim(y0, min(y1, ext[3])); ax.set_aspect("equal")
ax.ticklabel_format(style="plain"); ax.tick_params(labelsize=7); ax.set_xlabel("Este (m)"); ax.set_ylabel("Norte (m)")
ax.grid(color="0.8", lw=0.3, ls=":")
ax.annotate("N", xy=(0.95, 0.97), xytext=(0.95, 0.9), xycoords="axes fraction", ha="center", fontsize=13, fontweight="bold",
            arrowprops=dict(facecolor="black", width=3.5, headwidth=10))
ax.add_patch(plt.Rectangle((x0 + 2000, y0 + 2000), 5000, 600, fc="black", zorder=9))
ax.add_patch(plt.Rectangle((x0 + 7000, y0 + 2000), 5000, 600, fc="white", ec="black", zorder=9))
ax.text(x0 + 2000, y0 + 3200, "0", fontsize=7, zorder=9); ax.text(x0 + 12000, y0 + 3200, "10 km", fontsize=7, ha="center", zorder=9)
ax.legend(handles=[Line2D([], [], color="black", lw=2.2, label="Límite de la cuenca"),
                   Line2D([], [], color="#1f5fbf", lw=1.3, label="Drenajes del DEM (≥ 20 km²)"),
                   Line2D([], [], ls="", marker="^", ms=10, mfc="red", mec="black", label=ax.get_legend_handles_labels()[1][0]),
                   Line2D([], [], ls="", marker="*", ms=12, mfc="yellow", mec="black", label=ax.get_legend_handles_labels()[1][1])],
          loc="upper left", fontsize=8, framealpha=0.92)
ax.set_title("Verificación del punto de cierre: presa de Hidroituango\nentre las desembocaduras de los ríos San Andrés e Ituango",
             fontsize=11, fontweight="bold")
ax.text(0.99, 0.01, "DEM Copernicus GLO-30 (90 m) · MAGNA-SIRGAS / Colombia Bogotá (EPSG:3116)", transform=ax.transAxes,
        ha="right", va="bottom", fontsize=7, path_effects=[pe.withStroke(linewidth=2, foreground="white")])
fig.tight_layout(); fig.savefig(DEL / "verificacion_cierre.png", dpi=220); plt.close(fig)
print("listo")
