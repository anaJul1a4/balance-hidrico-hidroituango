"""
Punto 5 - Mapas de temperatura máxima, mínima y media por álgebra de mapas:  T(celda) = T0 − α · Z(celda)
con las relaciones T–Z del punto 4 (coeficientes_T_Z.csv) y el DEM Copernicus GLO-30 de 90 m recortado a la cuenca.

Salidas: trabajo1/resultados/07_mapas_temperatura/
    Tmax_90m_3116.tif, Tmin_90m_3116.tif, Tmed_90m_3116.tif
    mapa_Tmax.png, mapa_Tmin.png, mapa_Tmed.png, mapas_temperatura_panel.png, temperatura_por_franja.png
    resumen_temperatura.csv, franjas_elevacion.csv, contraste_estaciones.csv
"""
import re
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
DEL = ROOT / "trabajo1" / "resultados" / "01_delimitacion"
P4 = ROOT / "trabajo1" / "resultados" / "05_temperatura_elevacion"
OUT = ROOT / "trabajo1" / "resultados" / "07_mapas_temperatura"
OUT.mkdir(parents=True, exist_ok=True)
VARS = {"Tmax": "Temperatura máxima media", "Tmin": "Temperatura mínima media", "Tmed": "Temperatura media"}
Z_EST = (500.0, 4150.0)          # rango de elevación de las 47 estaciones usadas en las regresiones
VMIN, VMAX = -6, 36              # misma escala de color en los tres mapas para poder compararlos

coef = pd.read_csv(P4 / "coeficientes_T_Z.csv", index_col=0)
with rasterio.open(DEL / "dem_cuenca_90m_3116.tif") as src:
    Z = src.read(1, masked=True).astype("float64")
    prof, aff = src.profile, src.transform
mask = ~Z.mask
zc = Z.compressed()
area_celda = abs(aff.a * aff.e) / 1e6

# ----------------------------------------------------------------------------- álgebra de mapas
T = {}
prof.update(dtype="float32", nodata=-9999, compress="deflate")
for v in VARS:
    t = coef.loc[v, "T0"] - coef.loc[v, "alfa"] * Z          # T = T0 − α·Z en cada celda
    T[v] = t
    with rasterio.open(OUT / f"{v}_90m_3116.tif", "w", **prof) as d:
        d.write(t.filled(-9999).astype("float32"), 1)

# ----------------------------------------------------------------------------- coherencia
inc = ((T["Tmin"] >= T["Tmed"]) | (T["Tmed"] >= T["Tmax"])).filled(False).sum()
dif_med = (T["Tmed"] - (T["Tmax"] + T["Tmin"]) / 2).compressed()
extrap_alto, extrap_bajo = (zc > Z_EST[1]).mean() * 100, (zc < Z_EST[0]).mean() * 100
res = {}
for v in VARS:
    tc = T[v].compressed()
    res[v] = {"media cuenca (°C)": tc.mean(), "mínimo (°C)": tc.min(), "máximo (°C)": tc.max(),
              "percentil 5 (°C)": np.percentile(tc, 5), "percentil 95 (°C)": np.percentile(tc, 95),
              "área < 0 °C (km²)": (tc < 0).sum() * area_celda, "área > 24 °C (km²)": (tc > 24).sum() * area_celda,
              "T0 (°C)": coef.loc[v, "T0"], "α (°C/km)": coef.loc[v, "alfa_km"], "R²": coef.loc[v, "R2"]}
res = pd.DataFrame(res).T
res.to_csv(OUT / "resumen_temperatura.csv", encoding="utf-8-sig")
z0 = {v: coef.loc[v, "T0"] / coef.loc[v, "alfa"] for v in VARS}      # elevación de la isoterma 0 °C
print(res.round(2).to_string())
print(f"celdas incoherentes (no Tmin<Tmed<Tmax): {inc}")
print(f"Tmed − (Tmax+Tmin)/2: media {dif_med.mean():.2f} °C, rango {dif_med.min():.2f} a {dif_med.max():.2f}")
print(f"extrapolación: {extrap_alto:.2f} % del área sobre {Z_EST[1]:.0f} m, {extrap_bajo:.2f} % bajo {Z_EST[0]:.0f} m")
print("isoterma 0 °C:", {k: round(v) for k, v in z0.items()})

# franjas de elevación
bandas = [0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 6000]
fr = pd.DataFrame({"Z": zc, **{v: T[v].compressed() for v in VARS}})
fr["franja"] = pd.cut(fr.Z, bandas, right=False, labels=[f"{a}–{b}" if b < 6000 else f"≥{a}" for a, b in zip(bandas, bandas[1:])])
tab = fr.groupby("franja", observed=True).agg(area_km2=("Z", lambda s: len(s) * area_celda),
                                              Tmax=("Tmax", "mean"), Tmin=("Tmin", "mean"), Tmed=("Tmed", "mean"))
tab["% área"] = 100 * tab.area_km2 / tab.area_km2.sum()
tab.to_csv(OUT / "franjas_elevacion.csv", encoding="utf-8-sig")
print(tab.round(1).to_string())


# ----------------------------------------------------------------------------- contraste con estaciones
def dms(s):
    s = str(s).replace(",", ".")
    m = re.findall(r"[\d.]+", s)
    if len(m) < 3:
        return np.nan
    x = float(m[0]) + float(m[1]) / 60 + float(m[2]) / 3600
    return -x if ("W" in s or "S" in s) else x


est = pd.read_excel(P4 / "Punto4_temperatura_elevacion.xlsx", sheet_name="Inventario")
est = est[est["Seleccionada"] == "Sí"]
t_raw = pd.read_excel(ROOT / "CLIMATOLOGIA_IDEAM" / "Promedios Climatológicos  1981 - 2010.xlsx",
                      sheet_name="Temperatura", header=1)
t_raw = t_raw.set_index("CODIGO")[["LONGITUD", "LATITUD"]]
est = est.join(t_raw, on="Código")
ge = gpd.GeoDataFrame(est, geometry=gpd.points_from_xy(est.LONGITUD.map(dms), est.LATITUD.map(dms)), crs=4326).to_crs(
    "EPSG:3116")
rr, cc = rasterio.transform.rowcol(aff, ge.geometry.x, ge.geometry.y)
con = []
for v, col in [("Tmax", "Tmax (°C)"), ("Tmin", "Tmin (°C)"), ("Tmed", "Tmed (°C)")]:
    mapa = np.array([T[v][r, c] for r, c in zip(rr, cc)], dtype=float)
    e = mapa - ge[col].to_numpy()
    con.append({"variable": v, "n": len(e), "sesgo (°C)": np.nanmean(e), "RMSE (°C)": np.sqrt(np.nanmean(e ** 2)),
                "RMSE usando Z catálogo (°C)": coef.loc[v, "s"] * np.sqrt((len(e) - 2) / len(e))})
con = pd.DataFrame(con).set_index("variable")
con.to_csv(OUT / "contraste_estaciones.csv", encoding="utf-8-sig")
print(con.round(2).to_string())

# ----------------------------------------------------------------------------- mapas
cuenca = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="cuenca")
rio = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="rio_principal")
cierre = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="punto_cierre")
ext = (aff.c, aff.c + aff.a * Z.shape[1], aff.f + aff.e * Z.shape[0], aff.f)
zf = Z.filled(np.nan)
hs = LightSource(azdeg=315, altdeg=45).hillshade(np.nan_to_num(zf, nan=np.nanmin(zf)), vert_exag=3, dx=aff.a, dy=aff.a)
X = np.linspace(ext[0], ext[1], Z.shape[1]); Y = np.linspace(ext[3], ext[2], Z.shape[0])
minx, miny, maxx, maxy = cuenca.total_bounds
CMAP = "RdYlBu_r"


def mapa(ax, v, completo=True):
    tf = T[v].filled(np.nan)
    im = ax.imshow(tf, cmap=CMAP, vmin=VMIN, vmax=VMAX, extent=ext, zorder=1)
    ax.imshow(np.where(mask, hs, np.nan), cmap="gray", alpha=0.22, extent=ext, zorder=2)
    cs = ax.contour(X, Y, tf, levels=np.arange(-4, 37, 4), colors="0.2", linewidths=0.35, zorder=3)
    ax.clabel(cs, fmt="%d", fontsize=5 if not completo else 6)
    if np.nanmin(tf) < 0:
        ax.contour(X, Y, tf, levels=[0], colors="#08306b", linewidths=1.1, zorder=3)
    rio.plot(ax=ax, color="#08306b", linewidth=1.0 if not completo else 1.5, zorder=4)
    cuenca.boundary.plot(ax=ax, color="black", linewidth=1.0, zorder=5)
    cierre.plot(ax=ax, color="white", marker="^", markersize=50 if not completo else 90, edgecolor="black", zorder=6)
    ax.set_xlim(minx - 15000, maxx + 15000); ax.set_ylim(miny - 15000, maxy + 15000); ax.set_aspect("equal")
    ax.set_xlabel("Este (m)", fontsize=8); ax.set_ylabel("Norte (m)", fontsize=8)
    ax.ticklabel_format(style="plain"); ax.tick_params(labelsize=6 if not completo else 7)
    plt.setp(ax.get_yticklabels(), rotation=90, va="center"); ax.grid(color="0.7", lw=0.3, ls=":")
    r = coef.loc[v]
    ax.set_title(f"{VARS[v]}\n{v} = {r.T0:.2f} − {r.alfa:.5f}·Z   (R² = {r.R2:.3f})", fontsize=9 if not completo else 10.5,
                 fontweight="bold")
    s = res.loc[v]
    ax.text(0.98, 0.005, f"Media de la cuenca: {s['media cuenca (°C)']:.1f} °C\nRango: {s['mínimo (°C)']:.1f} a "
            f"{s['máximo (°C)']:.1f} °C", transform=ax.transAxes, ha="right", va="bottom", fontsize=7 if completo else 6,
            path_effects=[pe.withStroke(linewidth=2, foreground="white")])
    return im


for v in VARS:
    fig, ax = plt.subplots(figsize=(9.5, 14))
    im = mapa(ax, v)
    ax.set_xlabel("Este (m)", fontsize=8); ax.set_ylabel("Norte (m)", fontsize=8)
    ax.annotate("N", xy=(0.94, 0.975), xytext=(0.94, 0.92), xycoords="axes fraction", ha="center", fontsize=14,
                fontweight="bold", arrowprops=dict(facecolor="black", width=4, headwidth=12))
    sx, sy = minx - 5000, miny
    for i, colr in enumerate(["black", "white", "black", "white"]):
        ax.add_patch(plt.Rectangle((sx + i * 12500, sy), 12500, 3000, fc=colr, ec="black", lw=0.6, zorder=9))
    for i, tt in enumerate(["0", "", "25", "", "50"]):
        ax.text(sx + i * 12500, sy + 5000, tt, ha="center", fontsize=7, zorder=9)
    ax.text(sx + 4 * 12500 + 4000, sy + 1500, "km", ha="left", va="center", fontsize=7, zorder=9)
    leg = [Line2D([], [], color="0.2", lw=0.5, label="Isotermas cada 4 °C"),
           Line2D([], [], color="#08306b", lw=1.5, label="Río Cauca"),
           Line2D([], [], color="black", lw=1.0, label="Límite de la cuenca"),
           Line2D([], [], ls="", marker="^", ms=8, mfc="white", mec="black", label="Punto de cierre (Hidroituango)")]
    if res.loc[v, "mínimo (°C)"] < 0:
        leg.insert(1, Line2D([], [], color="#08306b", lw=1.1, label=f"Isoterma 0 °C (≈ {z0[v]:,.0f} m)".replace(",", " ")))
    ax.legend(handles=leg, loc="upper left", fontsize=7.5, framealpha=0.92)
    cb = fig.colorbar(im, ax=ax, shrink=0.35, pad=0.02, extend="both"); cb.set_label(f"{v} (°C)", fontsize=8)
    ax.text(0.98, 0.06, "DEM Copernicus GLO-30 (90 m) · Estaciones IDEAM 1981–2010\nMAGNA-SIRGAS / Colombia Bogotá (EPSG:3116)",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=6.5,
            path_effects=[pe.withStroke(linewidth=2, foreground="white")])
    fig.tight_layout(); fig.savefig(OUT / f"mapa_{v}.png", dpi=250); plt.close(fig)

fig, axs = plt.subplots(1, 3, figsize=(17, 11.5))
for ax, v in zip(axs, ["Tmin", "Tmed", "Tmax"]):
    im = mapa(ax, v, completo=False)
fig.colorbar(im, ax=axs, shrink=0.5, pad=0.015, extend="both", label="Temperatura (°C)")
fig.suptitle("Mapas de temperatura por álgebra de mapas T = T0 − α·Z — Cuenca del río Cauca hasta Hidroituango",
             fontsize=12, fontweight="bold")
fig.savefig(OUT / "mapas_temperatura_panel.png", dpi=220, bbox_inches="tight"); plt.close(fig)

# perfil T por franja
fig, ax = plt.subplots(figsize=(8, 5))
for v, c in [("Tmax", "#d7301f"), ("Tmed", "#238b45"), ("Tmin", "#2171b5")]:
    ax.plot(tab[v], range(len(tab)), "o-", c=c, label=v)
ax.barh(range(len(tab)), tab["% área"] / tab["% área"].max() * 10 - 10, left=0, color="0.85", height=0.6,
        label="% del área (escala relativa)")
ax.set_yticks(range(len(tab))); ax.set_yticklabels([f"{f} m  ({p:.1f} %)" for f, p in zip(tab.index, tab["% área"])], fontsize=8)
ax.axvline(0, c="k", lw=0.6); ax.set_xlabel("Temperatura media de la franja (°C)"); ax.grid(alpha=0.3)
ax.set_title("Temperatura por franja de elevación (entre paréntesis: % del área de la cuenca)", fontsize=10)
ax.legend(fontsize=8, loc="lower right")
fig.tight_layout(); fig.savefig(OUT / "temperatura_por_franja.png", dpi=200); plt.close(fig)
