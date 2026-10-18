"""
Punto 8 - Mapa de estaciones hidrométricas IDEAM candidatas, según disponibilidad de datos locales.
Insumos: trabajo1/datos/estaciones_caudal_priorizacion.csv
         trabajo1/datos/catalogo_ideam_zona26_hidrometricas.json (datos.gov.co, dataset hp9r-jxuu)
"""
import json
from pathlib import Path

import geopandas as gpd
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import LightSource
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[2]
DAT = ROOT / "trabajo1" / "datos"
DEL = ROOT / "trabajo1" / "resultados" / "01_delimitacion"
OUT = ROOT / "trabajo1" / "resultados" / "02_estaciones_caudal"
OUT.mkdir(parents=True, exist_ok=True)
CRS = "EPSG:3116"

est = pd.read_csv(DAT / "estaciones_caudal_priorizacion.csv", dtype={"codigo_ideam": str})
cat = pd.DataFrame(json.load(open(DAT / "catalogo_ideam_zona26_hidrometricas.json", encoding="utf-8")))
cat = cat.drop_duplicates("codigo")
cat["codigo_ideam"] = cat.codigo.str[2:]
# ojo: en el campo `ubicaci_n` del dataset lat/lon vienen invertidos; `latitud`/`longitud` están bien
cat["lon"], cat["lat"] = cat.longitud.astype(float), cat.latitud.astype(float)
est = est.merge(cat[["codigo_ideam", "lon", "lat"]], on="codigo_ideam", how="left")
assert est.lon.notna().all(), est[est.lon.isna()]
est["tenemos"] = est.datos_locales.str.lower() != "no"
gest = gpd.GeoDataFrame(est, geometry=gpd.points_from_xy(est.lon, est.lat), crs=4326).to_crs(CRS)
gest.drop(columns=["lon", "lat"]).to_file(OUT / "estaciones_caudal.gpkg", layer="estaciones")

cuenca = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="cuenca")
dren = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="drenajes")
rio = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="rio_principal")
with rasterio.open(DEL / "dem_cuenca_90m_3116.tif") as src:
    z = src.read(1, masked=True).filled(np.nan).astype(float)
    ext = (src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top)
    dx = src.res[0]

fig, ax = plt.subplots(figsize=(10, 15))
hs = LightSource(azdeg=315, altdeg=45).hillshade(np.nan_to_num(z, nan=np.nanmin(z)), vert_exag=3, dx=dx, dy=dx)
ax.imshow(np.where(np.isnan(z), np.nan, hs), cmap="gray", vmin=0, vmax=1.3, extent=ext, zorder=1)
dren[dren.orden >= 2].plot(ax=ax, color="#6baed6", linewidth=0.3 + 0.3 * (dren[dren.orden >= 2].orden - 2), zorder=2)
rio.plot(ax=ax, color="#08519c", linewidth=2, zorder=3)
cuenca.boundary.plot(ax=ax, color="black", linewidth=1.2, zorder=4)

MARK = {"salida": "*", "cuenca": "o", "cabecera": "^", "regional": "s"}
SIZE = {1: 150, 2: 90, 3: 55}
COL = {True: "#1a9850", False: "#d73027"}
for _, s in gest.iterrows():
    ms = SIZE[s.prioridad] * (2.2 if s.rol == "salida" else 1)
    ax.scatter(s.geometry.x, s.geometry.y, marker=MARK[s.rol], s=ms, c=COL[s.tenemos],
               edgecolors="black", linewidths=0.7, zorder=6)
    # etiquetas: cauce principal a la derecha, tributarios a la izquierda
    izq = s.rol == "regional" or s.estacion in ("LOMITAS",)
    ax.annotate(f"{s.estacion.title()} (P{s.prioridad})", (s.geometry.x, s.geometry.y),
                xytext=(-7 if izq else 7, 0), textcoords="offset points", ha="right" if izq else "left",
                va="center", fontsize=6.5, zorder=7,
                path_effects=[pe.withStroke(linewidth=2.2, foreground="white")])

minx, miny, maxx, maxy = cuenca.total_bounds
ax.set_xlim(minx - 45000, maxx + 45000); ax.set_ylim(miny - 15000, maxy + 30000)
ax.set_aspect("equal"); ax.ticklabel_format(style="plain"); ax.tick_params(labelsize=7)
ax.set_xlabel("Este (m)", fontsize=8); ax.set_ylabel("Norte (m)", fontsize=8)
plt.setp(ax.get_yticklabels(), rotation=90, va="center")
ax.grid(color="0.7", lw=0.3, ls=":")
ax.annotate("N", xy=(0.93, 0.70), xytext=(0.93, 0.645), xycoords="axes fraction", ha="center", fontsize=14,
            fontweight="bold", arrowprops=dict(facecolor="black", width=4, headwidth=12))

n_si, n_no = gest.tenemos.sum(), (~gest.tenemos).sum()
leg = [Line2D([], [], ls="", marker="o", ms=9, mfc=COL[True], mec="black", label=f"Con datos locales ({n_si})"),
       Line2D([], [], ls="", marker="o", ms=9, mfc=COL[False], mec="black", label=f"Sin datos — por descargar ({n_no})"),
       Line2D([], [], ls="", label="")]
leg += [Line2D([], [], ls="", marker=m, ms=9, mfc="white", mec="black", label=f"Rol: {r}") for r, m in MARK.items()]
leg += [Line2D([], [], ls="", label="Tamaño: prioridad P1 > P2 > P3"),
        Line2D([], [], color="#08519c", lw=2, label="Río Cauca"),
        Line2D([], [], color="black", lw=1.2, label="Límite de la cuenca")]
ax.legend(handles=leg, loc="upper left", fontsize=8, framealpha=0.92)
ax.set_title("Estaciones hidrométricas IDEAM candidatas — cuenca del río Cauca hasta Hidroituango",
             fontsize=11, fontweight="bold")
ax.text(0.99, 0.005, "MAGNA-SIRGAS / Colombia Bogotá (EPSG:3116)\nCoordenadas: Catálogo Nacional de Estaciones IDEAM",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=6.5)
fig.tight_layout()
fig.savefig(OUT / "mapa_estaciones_caudal.png", dpi=300)
print(gest[["rol", "prioridad", "estacion", "tenemos"]].to_string(index=False))
