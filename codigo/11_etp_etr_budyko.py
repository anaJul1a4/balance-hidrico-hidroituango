"""
Puntos 6 y 7 - Evapotranspiración potencial (Hargreaves-Samani) y real (Budyko), celda a celda (DEM GLO-30, 90 m).

Punto 6 (Anexos 2 y 3), para cada mes m y cada celda:
    Tmax_m, Tmin_m = T0_m − α_m·Z            (regresiones mensuales del punto 4)
    Tmed_m = (Tmax_m + Tmin_m) / 2            (Anexo 2)
    J = día juliano representativo (Anexo 3.9); φ = latitud de la celda (rad)
    dr = 1 + 0.033 cos(2πJ/365);  δ = 0.409 sen(2πJ/365 − 1.39);  ωs = arccos(−tan φ · tan δ)
    Ra = (1440/π)·0.0820·dr·[ωs sen φ sen δ + cos φ cos δ sen ωs]   (MJ m⁻² día⁻¹);  Ra_mm = 0.408·Ra
    ETP_d = 0.0023·Ra_mm·(Tmed + 17.8)·√(Tmax − Tmin);   ETP_m = ETP_d·Nd;   ETP_anual = Σ ETP_m
Punto 7: φ = ETP/P;  ETR = P·[φ·tanh(1/φ)·(1 − e^(−φ))]^½   (Budyko, 1974)
También R = P − ETR (insumo del punto 9).

Salidas: trabajo1/resultados/08_etp_etr/
    ETP_anual, ETR_anual, indice_aridez, R_P_menos_ETR (GeoTIFF 90 m), mapas PNG, resúmenes CSV
"""
from pathlib import Path

import geopandas as gpd
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import BoundaryNorm, LightSource
from matplotlib.lines import Line2D
from pyproj import Transformer

import sys  # noqa: E402
sys.path.insert(0, str(Path(__file__).parent))
import escalas as E  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEL = ROOT / "trabajo1" / "resultados" / "01_delimitacion"
P4 = ROOT / "trabajo1" / "resultados" / "05_temperatura_elevacion"
P3 = ROOT / "trabajo1" / "resultados" / "04_precipitacion_interpolada"
OUT = ROOT / "trabajo1" / "resultados" / "08_etp_etr"
OUT.mkdir(parents=True, exist_ok=True)
MESES = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
J = [15, 45, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349]          # Anexo 3.9
ND = [31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]                 # febrero promedio (años bisiestos)
GSC = 0.0820

# ----------------------------------------------------------------------------- insumos
with rasterio.open(DEL / "dem_cuenca_90m_3116.tif") as src:
    Z = src.read(1, masked=True).astype("float64")
    prof, aff = src.profile, src.transform
mask = ~Z.mask
rr, cc = np.nonzero(mask)
z = Z.data[rr, cc]
xs, ys = rasterio.transform.xy(aff, rr, cc)
lon, lat = Transformer.from_crs("EPSG:3116", 4326, always_xy=True).transform(np.asarray(xs), np.asarray(ys))
phi_lat = np.deg2rad(lat)
with rasterio.open(P3 / "P_anual_kriging_90m_3116.tif") as src:
    assert src.transform == aff and src.shape == Z.shape
    P = src.read(1)[rr, cc].astype("float64")
cm = pd.read_csv(P4 / "coeficientes_T_Z_mensual.csv").set_index(["variable", "mes"])

# ----------------------------------------------------------------------------- punto 6: Hargreaves-Samani mensual
etp_anual = np.zeros_like(z)
mens = []
for m, (mes, j, nd) in enumerate(zip(MESES, J, ND)):
    tmax = cm.loc[("Tmax", mes), "T0"] - cm.loc[("Tmax", mes), "alfa"] * z
    tmin = cm.loc[("Tmin", mes), "T0"] - cm.loc[("Tmin", mes), "alfa"] * z
    tmed = (tmax + tmin) / 2
    dr = 1 + 0.033 * np.cos(2 * np.pi * j / 365)
    dec = 0.409 * np.sin(2 * np.pi * j / 365 - 1.39)
    ws = np.arccos(-np.tan(phi_lat) * np.tan(dec))
    ra = (1440 / np.pi) * GSC * dr * (ws * np.sin(phi_lat) * np.sin(dec) + np.cos(phi_lat) * np.cos(dec) * np.sin(ws))
    ra_mm = 0.408 * ra
    etp_d = 0.0023 * ra_mm * (tmed + 17.8) * np.sqrt(tmax - tmin)
    etp_m = etp_d * nd
    etp_anual += etp_m
    mens.append({"mes": mes, "J": j, "Nd": nd, "Ra media (MJ/m²/d)": ra.mean(), "Ra_mm media (mm/d)": ra_mm.mean(),
                 "Tmax media (°C)": tmax.mean(), "Tmin media (°C)": tmin.mean(), "Tmed media (°C)": tmed.mean(),
                 "ETP_d media (mm/d)": etp_d.mean(), "ETP_m media cuenca (mm)": etp_m.mean()})
mens = pd.DataFrame(mens).set_index("mes")
mens.to_csv(OUT / "ETP_mensual_cuenca.csv", encoding="utf-8-sig")

# variante "anual × 365" (enunciado del punto 6) para comparar con la suma mensual del Anexo 3
T5 = ROOT / "trabajo1" / "resultados" / "07_mapas_temperatura"
with rasterio.open(T5 / "Tmax_90m_3116.tif") as a, rasterio.open(T5 / "Tmin_90m_3116.tif") as b:
    tmx, tmn = a.read(1)[rr, cc].astype("float64"), b.read(1)[rr, cc].astype("float64")
ra_anual = np.mean([0.408 * (1440 / np.pi) * GSC * (1 + 0.033 * np.cos(2 * np.pi * j / 365)) *
                    (lambda d, w: w * np.sin(phi_lat) * np.sin(d) + np.cos(phi_lat) * np.cos(d) * np.sin(w))(
                        0.409 * np.sin(2 * np.pi * j / 365 - 1.39),
                        np.arccos(-np.tan(phi_lat) * np.tan(0.409 * np.sin(2 * np.pi * j / 365 - 1.39)))) for j in J], axis=0)
etp_365 = 0.0023 * ra_anual * ((tmx + tmn) / 2 + 17.8) * np.sqrt(tmx - tmn) * 365

# ----------------------------------------------------------------------------- punto 7: Budyko
phi = etp_anual / P
etr = P * np.sqrt(phi * np.tanh(1 / phi) * (1 - np.exp(-phi)))
R = P - etr

# ----------------------------------------------------------------------------- rásters
prof.update(dtype="float32", nodata=-9999, compress="deflate")
campos = {"ETP_anual_hargreaves": etp_anual, "indice_aridez_phi": phi, "ETR_anual_budyko": etr, "R_P_menos_ETR": R}
G = {}
for k, v in campos.items():
    a = np.full(Z.shape, np.nan); a[rr, cc] = v; G[k] = a
    with rasterio.open(OUT / f"{k}_90m_3116.tif", "w", **prof) as d:
        d.write(np.where(np.isnan(a), -9999, a).astype("float32"), 1)

# ----------------------------------------------------------------------------- resúmenes
A = mask.sum() * abs(aff.a * aff.e) / 1e6
res = pd.DataFrame({
    "P (mm/año)": [P.mean(), P.min(), P.max()],
    "ETP Hargreaves Σ mensual (mm/año)": [etp_anual.mean(), etp_anual.min(), etp_anual.max()],
    "ETP anual×365 (mm/año)": [etp_365.mean(), etp_365.min(), etp_365.max()],
    "φ = ETP/P": [phi.mean(), phi.min(), phi.max()],
    "ETR Budyko (mm/año)": [etr.mean(), etr.min(), etr.max()],
    "ETR/P": [etr.mean() / P.mean(), (etr / P).min(), (etr / P).max()],
    "R = P − ETR (mm/año)": [R.mean(), R.min(), R.max()],
}, index=["media cuenca", "mínimo", "máximo"]).T
res["Q equivalente (m³/s)"] = np.where(res.index.str.contains("mm/año"), res["media cuenca"] / 1000 * A * 1e6 / (365.25 * 86400), np.nan)
pc = etp_anual.mean() / P.mean(); fb = np.sqrt(pc * np.tanh(1 / pc) * (1 - np.exp(-pc)))
res.loc["Budyko agregado: ETR = P·f(φ medio) (mm/año)"] = [P.mean() * fb, np.nan, np.nan, P.mean() * fb / 1000 * A * 1e6 / (365.25 * 86400)]
res.loc["Budyko agregado: R = P − ETR (mm/año)"] = [P.mean() * (1 - fb), np.nan, np.nan, P.mean() * (1 - fb) / 1000 * A * 1e6 / (365.25 * 86400)]
res.to_csv(OUT / "resumen_balance_largo_plazo.csv", encoding="utf-8-sig")
print(res.round(3).to_string())
print(mens.round(2).to_string())
fr = pd.Series(phi).pipe(lambda s: pd.cut(s, [0, 0.5, 0.75, 1, 1.5, 10], labels=["<0.5 muy húmedo", "0.5–0.75 húmedo",
                                                                                   "0.75–1 subhúmedo", "1–1.5 seco", ">1.5"]))
print((fr.value_counts(normalize=True).sort_index() * 100).round(1).to_string())

# contraste con la ETP reportada por el IDEAM en estaciones de la cuenca
import re  # noqa: E402


def dms(s):
    s = str(s).replace(",", ".")
    mm = re.findall(r"[\d.]+", s)
    if len(mm) < 3:
        return np.nan
    v = float(mm[0]) + float(mm[1]) / 60 + float(mm[2]) / 3600
    return -v if ("W" in s or "S" in s) else v


ide = pd.read_excel(ROOT / "CLIMATOLOGIA_IDEAM" / "Promedios Climatológicos  1981 - 2010.xlsx",
                    sheet_name="Evapotranspiración Potencial", header=1)
ide["lon"], ide["lat"] = ide.LONGITUD.map(dms), ide.LATITUD.map(dms)
ide = ide.dropna(subset=["lon", "lat", "ANUAL"])
gi = gpd.GeoDataFrame(ide, geometry=gpd.points_from_xy(ide.lon, ide.lat), crs=4326).to_crs("EPSG:3116")
cuenca = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="cuenca")
gi = gi[gi.within(cuenca.geometry[0])].copy()
r2, c2 = rasterio.transform.rowcol(aff, gi.geometry.x, gi.geometry.y)
gi["ETP_mapa"] = [G["ETP_anual_hargreaves"][a, b] for a, b in zip(r2, c2)]
gi = gi.dropna(subset=["ETP_mapa"])
e = gi.ETP_mapa - gi.ANUAL
con = {"n estaciones": len(gi), "ETP IDEAM media (mm)": gi.ANUAL.mean(), "ETP Hargreaves en esos puntos (mm)": gi.ETP_mapa.mean(),
       "sesgo (mm)": e.mean(), "sesgo (%)": 100 * e.mean() / gi.ANUAL.mean(), "RMSE (mm)": np.sqrt((e ** 2).mean()),
       "r": np.corrcoef(gi.ANUAL, gi.ETP_mapa)[0, 1]}
pd.Series(con).to_csv(OUT / "contraste_ETP_IDEAM.csv", encoding="utf-8-sig")
print(pd.Series(con).round(2).to_string())

# ----------------------------------------------------------------------------- mapas
rio = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="rio_principal")
cierre = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="punto_cierre")
ext = (aff.c, aff.c + aff.a * Z.shape[1], aff.f + aff.e * Z.shape[0], aff.f)
zf = Z.filled(np.nan)
hs = LightSource(azdeg=315, altdeg=45).hillshade(np.nan_to_num(zf, nan=np.nanmin(zf)), vert_exag=3, dx=aff.a, dy=aff.a)
X = np.linspace(ext[0], ext[1], Z.shape[1]); Yc = np.linspace(ext[3], ext[2], Z.shape[0])
minx, miny, maxx, maxy = cuenca.total_bounds

ESPEC = {
    "ETP_anual_hargreaves": dict(t="Evapotranspiración potencial anual — Hargreaves-Samani", u="ETP (mm/año)",
                                 esc=E.ETP, lev=np.arange(800, 1901, 200)),
    "indice_aridez_phi": dict(t="Índice de aridez φ = ETP / P", u="φ (adimensional)", cmap="RdYlBu_r",
                              bounds=[0.2, 0.4, 0.5, 0.6, 0.75, 1.0, 1.25, 1.5, 2.0], lev=[0.5, 0.75, 1.0]),
    "ETR_anual_budyko": dict(t="Evapotranspiración real anual — Budyko", u="ETR (mm/año)",
                             esc=E.ETR, lev=np.arange(600, 1501, 200)),  # mismas clases que la ETP
    "R_P_menos_ETR": dict(t="Escorrentía de largo plazo R = P − ETR", u="R (mm/año)", 
                          esc=E.R, lev=np.arange(500, 2501, 500)),
}


def mapa(ax, k, completo=True):
    s, a = ESPEC[k], G[k]
    if "esc" in s:
        im = ax.imshow(a, cmap=s["esc"]["cmap"], norm=s["esc"]["norm"], extent=ext, zorder=1)
    elif "bounds" in s:
        cmap = plt.get_cmap(s["cmap"], len(s["bounds"]) - 1); norm = BoundaryNorm(s["bounds"], cmap.N)
        im = ax.imshow(a, cmap=cmap, norm=norm, extent=ext, zorder=1)
    else:
        im = ax.imshow(a, cmap=s["cmap"], vmin=s["vmin"], vmax=s["vmax"], extent=ext, zorder=1)
    ax.imshow(np.where(mask, hs, np.nan), cmap="gray", alpha=0.2, extent=ext, zorder=2)
    cs = ax.contour(X, Yc, a, levels=s["lev"], colors="0.15", linewidths=0.4, zorder=3)
    ax.clabel(cs, fmt="%g", fontsize=6)
    rio.plot(ax=ax, color="#08306b", linewidth=1.4 if completo else 1.0, zorder=4)
    cuenca.boundary.plot(ax=ax, color="black", linewidth=1.0, zorder=5)
    cierre.plot(ax=ax, color="white", marker="^", markersize=80 if completo else 45, edgecolor="black", zorder=6)
    ax.set_xlim(minx - 15000, maxx + 15000); ax.set_ylim(miny - 15000, maxy + 15000); ax.set_aspect("equal")
    ax.ticklabel_format(style="plain"); ax.set_xticks([700000, 800000]); ax.tick_params(labelsize=7 if completo else 6)
    ax.set_xlabel("Este (m)", fontsize=8); ax.set_ylabel("Norte (m)", fontsize=8)
    plt.setp(ax.get_yticklabels(), rotation=90, va="center"); ax.grid(color="0.7", lw=0.3, ls=":")
    ax.set_title(s["t"], fontsize=10.5 if completo else 9, fontweight="bold")
    v = np.nanmean(a)
    ax.text(0.98, 0.005, f"Media de la cuenca: {v:.2f}" if k == "indice_aridez_phi" else f"Media de la cuenca: {v:.0f} mm/año",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=7.5 if completo else 6.5,
            path_effects=[pe.withStroke(linewidth=2, foreground="white")])
    return im


for k, s in ESPEC.items():
    fig, ax = plt.subplots(figsize=(9.5, 14))
    im = mapa(ax, k)
    ax.annotate("N", xy=(0.94, 0.975), xytext=(0.94, 0.92), xycoords="axes fraction", ha="center", fontsize=14,
                fontweight="bold", arrowprops=dict(facecolor="black", width=4, headwidth=12))
    sx, sy = minx - 5000, miny
    for i, colr in enumerate(["black", "white", "black", "white"]):
        ax.add_patch(plt.Rectangle((sx + i * 12500, sy), 12500, 3000, fc=colr, ec="black", lw=0.6, zorder=9))
    for i, tt in enumerate(["0", "", "25", "", "50"]):
        ax.text(sx + i * 12500, sy + 5000, tt, ha="center", fontsize=7, zorder=9)
    ax.text(sx + 4 * 12500 + 4000, sy + 1500, "km", ha="left", va="center", fontsize=7, zorder=9)
    ax.legend(handles=[Line2D([], [], color="0.15", lw=0.5, label="Isolíneas"),
                       Line2D([], [], color="#08306b", lw=1.4, label="Río Cauca"),
                       Line2D([], [], color="black", lw=1.0, label="Límite de la cuenca"),
                       Line2D([], [], ls="", marker="^", ms=8, mfc="white", mec="black", label="Punto de cierre (Hidroituango)")],
              loc="upper left", fontsize=7.5, framealpha=0.92)
    cb = E.barra(fig, im, s["esc"], G[k], ax=ax, shrink=0.35, pad=0.02) if "esc" in s else fig.colorbar(im, ax=ax, shrink=0.35, pad=0.02)
    cb.set_label(s["u"], fontsize=8)
    ax.text(0.98, 0.04, "P: kriging IDEAM 1981–2010 · T: regresiones T–Z mensuales · DEM GLO-30 90 m\n"
            "MAGNA-SIRGAS / Colombia Bogotá (EPSG:3116)", transform=ax.transAxes, ha="right", va="bottom", fontsize=6.5,
            path_effects=[pe.withStroke(linewidth=2, foreground="white")])
    fig.tight_layout(); fig.savefig(OUT / f"mapa_{k}.png", dpi=250); plt.close(fig)

fig, axs = plt.subplots(1, 4, figsize=(22, 11.5))
for ax, k in zip(axs, ESPEC):
    im = mapa(ax, k, completo=False)
    kw = dict(ax=ax, shrink=0.55, pad=0.03)
    cb = E.barra(fig, im, ESPEC[k]["esc"], G[k], **kw) if "esc" in ESPEC[k] else fig.colorbar(im, **kw)
    cb.set_label(ESPEC[k]["u"], fontsize=8); cb.ax.tick_params(labelsize=7.5)
    if k == "indice_aridez_phi":
        cb.set_ticks([0.2, 0.5, 0.75, 1.0, 1.5, 2.0])
fig.suptitle("Balance hídrico de largo plazo celda a celda — Cuenca del río Cauca hasta Hidroituango (1981–2010)",
             fontsize=13, fontweight="bold")
fig.savefig(OUT / "mapas_ETP_phi_ETR_R_panel.png", dpi=200, bbox_inches="tight"); plt.close(fig)

# curva de Budyko con las celdas
fig, ax = plt.subplots(figsize=(6.5, 5))
idx = np.random.default_rng(0).choice(len(phi), 20000, replace=False)
ax.scatter(phi[idx], (etr / P)[idx], s=2, c=z[idx], cmap="terrain", alpha=0.5)
f = np.linspace(0.05, 3, 300)
ax.plot(f, np.sqrt(f * np.tanh(1 / f) * (1 - np.exp(-f))), "k", lw=1.5, label="Budyko (1974)")
ax.plot([0, 1, 3], [0, 1, 1], "k--", lw=0.8, label="Límites energía / agua")
phi_c = etp_anual.mean() / P.mean()
ax.scatter([phi_c], [etr.mean() / P.mean()], s=110, marker="*", c="red", edgecolors="black", zorder=5,
           label=f"Cuenca, Budyko celda a celda: φ = {phi_c:.2f}, ETR/P = {etr.mean() / P.mean():.2f}")
ax.scatter([phi_c], [np.sqrt(phi_c * np.tanh(1 / phi_c) * (1 - np.exp(-phi_c)))], s=60, marker="o", c="white",
           edgecolors="red", zorder=5, label="Cuenca, Budyko agregado (φ medio)")
ax.set_xlabel("Índice de aridez φ = ETP / P"); ax.set_ylabel("ETR / P"); ax.set_xlim(0, 2); ax.set_ylim(0, 1.05)
ax.grid(alpha=0.3); ax.legend(fontsize=8, loc="lower right"); ax.set_title("Curva de Budyko (muestra de 20 000 celdas)", fontsize=10)
fig.tight_layout(); fig.savefig(OUT / "curva_budyko.png", dpi=200); plt.close(fig)

# ciclo mensual de ETP
fig, ax = plt.subplots(figsize=(8, 4))
ax.bar(MESES, mens["ETP_m media cuenca (mm)"], color="#fd8d3c")
ax2 = ax.twinx(); ax2.plot(MESES, mens["Ra media (MJ/m²/d)"], "k-o", ms=4)
ax.set_ylabel("ETP mensual media de la cuenca (mm)"); ax2.set_ylabel("Ra (MJ m⁻² día⁻¹)")
ax.set_title("ETP Hargreaves mensual y radiación extraterrestre — media de la cuenca", fontsize=10); ax.grid(alpha=0.3, axis="y")
fig.tight_layout(); fig.savefig(OUT / "ETP_mensual.png", dpi=200); plt.close(fig)
