"""
Figura «antes y después» del mapeo de cuantiles para la página web, con el mismo estilo de las figuras originales de la página
(21_figuras_complementarias.py, R_por_producto): precipitación (fila superior) y escorrentía R = P − ETR (fila inferior) de ERA5 y
ERA5-Land sin corregir y corregidos. Escalas de color por variable de escalas.py.

Salida: resultados/17_quantile_mapping/QM_P_R_pagina.png
"""
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
import escalas as E  # noqa: E402

RES = Path(__file__).resolve().parents[1] / "resultados"
DEL = RES / "01_delimitacion"
QMD = RES / "17_quantile_mapping"


def leer(p):
    with rasterio.open(p) as s:
        a = s.read(1).astype("float64"); a[a == s.nodata] = np.nan
        return a, s.transform


def budyko(p, etp):
    f = etp / p
    return p * np.sqrt(f * np.tanh(1 / f) * (1 - np.exp(-f)))


Z, aff = leer(DEL / "dem_cuenca_90m_3116.tif")
mask = np.isfinite(Z)
ext = (aff.c, aff.c + aff.a * Z.shape[1], aff.f + aff.e * Z.shape[0], aff.f)
cuenca = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="cuenca")
rio = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="rio_principal")
minx, miny, maxx, maxy = cuenca.total_bounds
ETP = leer(RES / "08_etp_etr" / "ETP_anual_hargreaves_90m_3116.tif")[0]


def marco(ax, titulo, fs=10):
    rio.plot(ax=ax, color="#08306b", lw=0.8); cuenca.boundary.plot(ax=ax, color="black", lw=1)
    ax.set_xlim(minx - 10000, maxx + 10000); ax.set_ylim(miny - 10000, maxy + 10000); ax.set_aspect("equal")
    ax.ticklabel_format(style="plain"); ax.set_xticks([700000, 800000]); ax.tick_params(labelsize=6)
    ax.set_title(titulo, fontsize=fs, fontweight="bold")
    ax.set_xlabel("Este (m)", fontsize=7); ax.set_ylabel("Norte (m)", fontsize=7)
    plt.setp(ax.get_yticklabels(), rotation=90, va="center"); ax.grid(color="0.7", lw=0.3, ls=":")


def norte(ax):
    ax.annotate("N", xy=(0.9, 0.975), xytext=(0.9, 0.92), xycoords="axes fraction", ha="center", fontsize=11, fontweight="bold",
                arrowprops=dict(facecolor="black", width=3, headwidth=9))


COLS = [("ERA5", "sin corregir", "P_ERA5_sin_corregir_90m_3116.tif"),
        ("ERA5", "mapeo de cuantiles", "P_ERA5_con_mapeo_de_cuantiles_90m_3116.tif"),
        ("ERA5-Land", "sin corregir", "P_ERA5_Land_sin_corregir_90m_3116.tif"),
        ("ERA5-Land", "mapeo de cuantiles", "P_ERA5_Land_con_mapeo_de_cuantiles_90m_3116.tif")]
fig, axs = plt.subplots(2, 4, figsize=(22, 21), gridspec_kw=dict(wspace=0.45, hspace=0.12))
for j, (prod, estado, f) in enumerate(COLS):
    p = np.where(mask, leer(QMD / f)[0], np.nan)          # sólo la cuenca
    r = p - budyko(p, ETP)
    for i, (a, esc, nom, et) in enumerate([(p, E.P, "P", "P (mm/año)"), (r, E.R, "R", "R = P − ETR (mm/año)")]):
        ax = axs[i, j]
        im = ax.imshow(a, cmap=esc["cmap"], norm=esc["norm"], extent=ext, interpolation="nearest")
        media = np.nanmean(a[mask])
        marco(ax, f"{prod} · {estado}\n{nom} media {media:,.0f} mm/año".replace(",", " "), 9.5)
        cb = E.barra(fig, im, esc, a[mask], ax=ax, shrink=0.55, pad=0.03)
        cb.set_label(et, fontsize=8)
norte(axs[0, -1])
fig.suptitle("Precipitación (arriba) y escorrentía de largo plazo (abajo) de ERA5 y ERA5-Land antes y después del mapeo de cuantiles "
             "(1981–2010) · EPSG:3116", fontsize=12, fontweight="bold", y=0.92)
fig.savefig(QMD / "QM_P_R_pagina.png", dpi=180, bbox_inches="tight"); plt.close(fig)
print("ok QM_P_R_pagina.png")
