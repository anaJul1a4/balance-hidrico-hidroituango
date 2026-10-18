"""
Punto 11 - Mapas de precipitación media anual multianual 1981-2010 de CHIRPS, ERA5-Land y ERA5.

Cada producto: suma anual de los 12 meses → promedio 1981-2010 en su grilla original → remuestreo por vecino más
cercano a la grilla de 90 m de la cuenca (EPSG:3116), que conserva las celdas originales y deja los productos en la
misma grilla que la ETP del punto 6 (insumo del punto 12).

Salidas: trabajo1/resultados/11_mapas_productos/
    P_<producto>_1981_2010_90m_3116.tif, mapa_<producto>.png, panel_P_productos.png, panel_razon_IDEAM.png,
    resumen_productos.csv
"""
from pathlib import Path
import sys

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import xarray as xr
from matplotlib.colors import BoundaryNorm, LightSource, TwoSlopeNorm
from matplotlib.lines import Line2D
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject

sys.path.insert(0, str(Path(__file__).parent))
from productos import abrir  # noqa: E402
import escalas as E  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "PRECIPITACION_COLOMBIA-20261003T131021Z-1-001" / "PRECIPITACION_COLOMBIA"
RES = ROOT / "trabajo1" / "resultados"
DEL = RES / "01_delimitacion"
OUT = RES / "11_mapas_productos"
OUT.mkdir(parents=True, exist_ok=True)
PRODUCTOS = {
    "CHIRPS": ("CHIRPS/CHIRPS_mensual_Colombia_1981_2025.nc", "lat", "lon", "0.05°"),
    "ERA5-Land": ("ERA5_LAND/ERA5_Land_precipitacion_mensual_Colombia_1981_2025.nc", "latitude", "longitude", "0.1°"),
    "ERA5": ("ERA5/ERA5_precipitacion_mensual_Colombia_1981_2025.nc", "latitude", "longitude", "0.25°"),
}

with rasterio.open(DEL / "dem_cuenca_90m_3116.tif") as src:
    Z = src.read(1, masked=True)
    prof, aff, shape = src.profile, src.transform, src.shape
mask = ~Z.mask
with rasterio.open(RES / "04_precipitacion_interpolada" / "P_anual_kriging_90m_3116.tif") as s:
    P_ide = s.read(1).astype("float64"); P_ide[P_ide == s.nodata] = np.nan

campos = {"IDEAM (kriging)": P_ide}
prof.update(dtype="float32", nodata=-9999, compress="deflate")
for nom, (f, la, lo, resol) in PRODUCTOS.items():
    ds = abrir(nom).rename({"lat": la, "lon": lo})          # CHIRPS = v2.0 (IRI); ver productos.py
    p = ds.precip.sel(time=slice("1981-01-01", "2010-12-31"))
    assert p.sizes["time"] == 360
    anual = p.groupby("time.year").sum("time").mean("year")
    if anual[la][0] < anual[la][-1]:                       # filas de norte a sur
        anual = anual.isel({la: slice(None, None, -1)})
    lats, lons = anual[la].values, anual[lo].values
    dx, dy = abs(lons[1] - lons[0]), abs(lats[1] - lats[0])
    src_tr = from_origin(lons[0] - dx / 2, lats[0] + dy / 2, dx, dy)
    dst = np.full(shape, np.nan)
    reproject(anual.values.astype("float64"), dst, src_transform=src_tr, src_crs="EPSG:4326", dst_transform=aff,
              dst_crs="EPSG:3116", resampling=Resampling.nearest, src_nodata=np.nan, dst_nodata=np.nan)
    dst[~mask] = np.nan
    campos[nom] = dst
    with rasterio.open(OUT / f"P_{nom.replace('-', '_')}_1981_2010_90m_3116.tif", "w", **prof) as d:
        d.write(np.where(np.isnan(dst), -9999, dst).astype("float32"), 1)

# ----------------------------------------------------------------------------- resumen
ok = mask & np.isfinite(P_ide)
filas = []
for nom, a in campos.items():
    v, r = a[ok], P_ide[ok]
    filas.append({"producto": nom, "P media cuenca (mm/año)": v.mean(), "mínimo (mm/año)": v.min(), "máximo (mm/año)": v.max(),
                  "razón media / IDEAM": v.mean() / r.mean(), "sesgo vs IDEAM (%)": 100 * (v.mean() / r.mean() - 1),
                  "correlación espacial con IDEAM": np.corrcoef(v, r)[0, 1]})
res = pd.DataFrame(filas).set_index("producto")
res.to_csv(OUT / "resumen_productos.csv", encoding="utf-8-sig")
print(res.round(3).to_string())

# ----------------------------------------------------------------------------- mapas
cuenca = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="cuenca")
rio = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="rio_principal")
cierre = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="punto_cierre")
ext = (aff.c, aff.c + aff.a * shape[1], aff.f + aff.e * shape[0], aff.f)
zf = Z.filled(np.nan).astype(float)
hs = LightSource(azdeg=315, altdeg=45).hillshade(np.nan_to_num(zf, nan=np.nanmin(zf)), vert_exag=3, dx=aff.a, dy=aff.a)
minx, miny, maxx, maxy = cuenca.total_bounds
CLASES = E.P_CL  # escala común de P anual (escalas.py)
cmapP, normP = E.P["cmap"], E.P["norm"]
RESOL = {"IDEAM (kriging)": "estaciones, 90 m", **{k: v[3] for k, v in PRODUCTOS.items()}}


def mapa(ax, a, titulo, cmap, norm, completo):
    im = ax.imshow(a, cmap=cmap, norm=norm, extent=ext, zorder=1, interpolation="nearest")
    ax.imshow(np.where(mask, hs, np.nan), cmap="gray", alpha=0.18, extent=ext, zorder=2)
    rio.plot(ax=ax, color="#08306b", linewidth=1.3 if completo else 0.9, zorder=4)
    cuenca.boundary.plot(ax=ax, color="black", linewidth=1.0, zorder=5)
    cierre.plot(ax=ax, color="white", marker="^", markersize=70 if completo else 40, edgecolor="black", zorder=6)
    ax.set_xlim(minx - 12000, maxx + 12000); ax.set_ylim(miny - 12000, maxy + 12000); ax.set_aspect("equal")
    ax.ticklabel_format(style="plain"); ax.set_xticks([700000, 800000]); ax.tick_params(labelsize=7 if completo else 6)
    ax.set_xlabel("Este (m)", fontsize=8); ax.set_ylabel("Norte (m)", fontsize=8)
    plt.setp(ax.get_yticklabels(), rotation=90, va="center"); ax.grid(color="0.7", lw=0.3, ls=":")
    ax.set_title(titulo, fontsize=10.5 if completo else 9.5, fontweight="bold")
    return im


def norte_escala(ax):
    ax.annotate("N", xy=(0.93, 0.975), xytext=(0.93, 0.925), xycoords="axes fraction", ha="center", fontsize=12,
                fontweight="bold", arrowprops=dict(facecolor="black", width=3.5, headwidth=10))
    sx, sy = minx - 5000, miny - 5000
    for i, colr in enumerate(["black", "white", "black", "white"]):
        ax.add_patch(plt.Rectangle((sx + i * 12500, sy), 12500, 3000, fc=colr, ec="black", lw=0.6, zorder=9))
    for i, tt in enumerate(["0", "", "25", "", "50"]):
        ax.text(sx + i * 12500, sy + 5000, tt, ha="center", fontsize=6.5, zorder=9)
    ax.text(sx + 54000, sy + 1500, "km", ha="left", va="center", fontsize=6.5, zorder=9)


for nom in PRODUCTOS:
    fig, ax = plt.subplots(figsize=(9, 13.5))
    im = mapa(ax, campos[nom], f"Precipitación media anual 1981–2010 — {nom} ({RESOL[nom]})", cmapP, normP, True)
    norte_escala(ax)
    cb = E.barra(fig, im, E.P, campos[nom], ax=ax, shrink=0.4, pad=0.02); cb.set_label("P (mm/año)", fontsize=8)
    ax.text(0.98, 0.005, f"Media de la cuenca: {res.loc[nom, 'P media cuenca (mm/año)']:,.0f} mm/año\n".replace(",", " ")
            + "MAGNA-SIRGAS / Colombia Bogotá (EPSG:3116)", transform=ax.transAxes, ha="right", va="bottom", fontsize=7)
    ax.legend(handles=[Line2D([], [], color="#08306b", lw=1.3, label="Río Cauca"), Line2D([], [], color="black", lw=1, label="Límite de la cuenca"),
                       Line2D([], [], ls="", marker="^", ms=8, mfc="white", mec="black", label="Punto de cierre")],
              loc="upper left", fontsize=7.5, framealpha=0.9)
    fig.tight_layout(); fig.savefig(OUT / f"mapa_{nom.replace('-', '_')}.png", dpi=220); plt.close(fig)

orden = ["IDEAM (kriging)", "CHIRPS", "ERA5-Land", "ERA5"]
fig, axs = plt.subplots(1, 4, figsize=(24, 11.5), gridspec_kw=dict(wspace=0.45))
for ax, nom in zip(axs, orden):
    im = mapa(ax, campos[nom], f"{nom}\n{RESOL[nom]} · media {res.loc[nom, 'P media cuenca (mm/año)']:,.0f} mm/año".replace(",", " "),
              cmapP, normP, False)
    cb = E.barra(fig, im, E.P, campos[nom], ax=ax, shrink=0.55, pad=0.03)
    cb.set_label("P (mm/año)", fontsize=8)
norte_escala(axs[-1])
fig.suptitle("Precipitación media anual multianual 1981–2010 — misma escala de color · MAGNA-SIRGAS / Colombia Bogotá (EPSG:3116)",
             fontsize=12, fontweight="bold")
fig.savefig(OUT / "panel_P_productos.png", dpi=200, bbox_inches="tight"); plt.close(fig)

fig, axs = plt.subplots(1, 3, figsize=(16, 11.5))
norm_r = TwoSlopeNorm(vmin=0.5, vcenter=1.0, vmax=5.0)
for ax, nom in zip(axs, orden[1:]):
    im = mapa(ax, campos[nom] / P_ide, f"{nom} / IDEAM\nrazón media {res.loc[nom, 'razón media / IDEAM']:.2f} · "
              f"r espacial {res.loc[nom, 'correlación espacial con IDEAM']:.2f}", "RdBu_r", norm_r, False)
norte_escala(axs[-1])
cb = fig.colorbar(im, ax=axs, shrink=0.55, pad=0.015, ticks=[0.5, 0.75, 1, 1.5, 2, 3, 4, 5])
cb.set_label("P producto / P IDEAM (1 = igual; > 1 sobreestima)", fontsize=9)
fig.suptitle("Razón entre cada producto y la precipitación interpolada de estaciones IDEAM (1981–2010)", fontsize=12, fontweight="bold")
fig.savefig(OUT / "panel_razon_IDEAM.png", dpi=200, bbox_inches="tight"); plt.close(fig)
