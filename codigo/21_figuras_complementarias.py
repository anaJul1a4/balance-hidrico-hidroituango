"""
Figuras y datos complementarios para el informe (puntos 5, 6, 7, 8, 11, 12, 13 y 14).

  p5  pisos térmicos (Caldas) sobre el mapa de Tmed · coherencia mapa–estaciones de temperatura
  p6  Ra por mes y latitud (Anexo 3) · ETP anual contra Tmed (muestra de celdas)
  p8  caudal medio de cada año completo por estación
  p11 verificación de los productos en toda Colombia con lugares de referencia
  p12 R = P − ETR por producto (panel) · estaciones en el espacio de Budyko y P necesaria para cerrar el balance
  p13 mes de máxima lluvia, número de temporadas lluviosas e índice de estacionalidad (Walsh y Lawler, 1981)
  p14 comparación punto a píxel: P de cada producto en la celda de cada estación frente a la P medida

Salidas: trabajo1/resultados/15_complementarias/
"""
import re
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from rasterio.features import geometry_mask
from scipy.optimize import brentq

sys.path.insert(0, str(Path(__file__).parent))
from productos import abrir  # noqa: E402
import escalas as E  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "trabajo1" / "resultados"
DAT = ROOT / "trabajo1" / "datos"
DEL = RES / "01_delimitacion"
OUT = RES / "15_complementarias"
OUT.mkdir(parents=True, exist_ok=True)
SEG = 365.25 * 86400
MES3 = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def leer(p, todas=False):
    with rasterio.open(p) as s:
        a = (s.read() if todas else s.read(1)).astype("float64"); a[a == s.nodata] = np.nan
        return a, s.transform


def dms(s):
    s = str(s).replace(",", ".")
    m = re.findall(r"[\d.]+", s)
    if len(m) < 3:
        return np.nan
    v = float(m[0]) + float(m[1]) / 60 + float(m[2]) / 3600
    return -v if ("W" in s or "S" in s) else v


def budyko(p, etp):
    f = etp / p
    return p * np.sqrt(f * np.tanh(1 / f) * (1 - np.exp(-f)))


Z, aff = leer(DEL / "dem_cuenca_90m_3116.tif")
mask = np.isfinite(Z)
ext = (aff.c, aff.c + aff.a * Z.shape[1], aff.f + aff.e * Z.shape[0], aff.f)
cuenca = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="cuenca")
rio = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="rio_principal")
minx, miny, maxx, maxy = cuenca.total_bounds
T = {v: leer(RES / "07_mapas_temperatura" / f"{v}_90m_3116.tif")[0] for v in ["Tmax", "Tmed", "Tmin"]}
ETP = leer(RES / "08_etp_etr" / "ETP_anual_hargreaves_90m_3116.tif")[0]
P = {"IDEAM": leer(RES / "04_precipitacion_interpolada" / "P_anual_kriging_90m_3116.tif")[0],
     "CHIRPS": leer(RES / "11_mapas_productos" / "P_CHIRPS_1981_2010_90m_3116.tif")[0],
     "ERA5-Land": leer(RES / "11_mapas_productos" / "P_ERA5_Land_1981_2010_90m_3116.tif")[0],
     "ERA5": leer(RES / "11_mapas_productos" / "P_ERA5_1981_2010_90m_3116.tif")[0]}
coefT = pd.read_csv(RES / "05_temperatura_elevacion" / "coeficientes_T_Z.csv", index_col=0)


def marco(ax, titulo, fs=10):
    rio.plot(ax=ax, color="#08306b", lw=0.8); cuenca.boundary.plot(ax=ax, color="black", lw=1)
    ax.set_xlim(minx - 10000, maxx + 10000); ax.set_ylim(miny - 10000, maxy + 10000); ax.set_aspect("equal")
    ax.ticklabel_format(style="plain"); ax.set_xticks([700000, 800000]); ax.tick_params(labelsize=6); ax.set_title(titulo, fontsize=fs, fontweight="bold")
    ax.set_xlabel("Este (m)", fontsize=7); ax.set_ylabel("Norte (m)", fontsize=7)
    plt.setp(ax.get_yticklabels(), rotation=90, va="center"); ax.grid(color="0.7", lw=0.3, ls=":")


def norte(ax):
    ax.annotate("N", xy=(0.9, 0.975), xytext=(0.9, 0.92), xycoords="axes fraction", ha="center", fontsize=11, fontweight="bold",
                arrowprops=dict(facecolor="black", width=3, headwidth=9))


# ============================================================================= p5: pisos térmicos
PISOS = [("Nival / glacial", -50, 6, "#f7fbff"), ("Páramo", 6, 12, "#9ecae1"), ("Frío", 12, 18, "#a1d99b"),
         ("Templado", 18, 24, "#fed976"), ("Cálido", 24, 50, "#fd8d3c")]
t0, al = coefT.loc["Tmed", "T0"], coefT.loc["Tmed", "alfa"]
pis = []
tm = T["Tmed"][mask]
for n, a, b, c in PISOS:
    pis.append({"piso": n, "Tmed (°C)": f"< {b}" if a < -10 else (f"> {a}" if b > 40 else f"{a}–{b}"),
                "elevación (m)": f"> {(t0 - b) / al:,.0f}" if a < -10 else (f"< {(t0 - a) / al:,.0f}" if b > 40 else
                                                                            f"{(t0 - b) / al:,.0f}–{(t0 - a) / al:,.0f}"),
                "% del área": 100 * ((tm >= a) & (tm < b)).mean(), "área (km²)": ((tm >= a) & (tm < b)).sum() * 0.0081})
pis = pd.DataFrame(pis)
pis.to_csv(OUT / "pisos_termicos.csv", index=False, encoding="utf-8-sig")
clases = np.full(Z.shape, np.nan)
for i, (n, a, b, c) in enumerate(PISOS):
    clases[mask & (T["Tmed"] >= a) & (T["Tmed"] < b)] = i
fig, ax = plt.subplots(figsize=(8, 12))
ax.imshow(clases, cmap=ListedColormap([p[3] for p in PISOS]), vmin=-0.5, vmax=4.5, extent=ext, interpolation="nearest")
marco(ax, "Pisos térmicos según la temperatura media (Caldas)"); norte(ax)
ax.legend(handles=[Patch(fc=c, ec="0.4", label=f"{n} ({r['Tmed (°C)']} °C) · {r['% del área']:.1f} %")
                   for (n, a, b, c), (_, r) in zip(PISOS, pis.iterrows())], loc="upper left", fontsize=8, framealpha=0.92)
ax.text(0.99, 0.005, "Tmed = T0 − α·Z sobre el DEM GLO-30 (90 m) · EPSG:3116", transform=ax.transAxes, ha="right", fontsize=7)
fig.tight_layout(); fig.savefig(OUT / "pisos_termicos.png", dpi=220); plt.close(fig)

# ============================================================================= p5: coherencia mapa–estaciones
inv = pd.read_excel(RES / "05_temperatura_elevacion" / "Punto4_temperatura_elevacion.xlsx", sheet_name="Inventario")
inv = inv[inv["Seleccionada"] == "Sí"]
raw = pd.read_excel(ROOT / "CLIMATOLOGIA_IDEAM" / "Promedios Climatológicos  1981 - 2010.xlsx", sheet_name="Temperatura", header=1)
raw = raw.dropna(subset=["CODIGO"]).drop_duplicates("CODIGO").set_index("CODIGO")
inv = inv.join(raw[["LONGITUD", "LATITUD"]], on="Código")
ge = gpd.GeoDataFrame(inv, geometry=gpd.points_from_xy(inv.LONGITUD.map(dms), inv.LATITUD.map(dms)), crs=4326).to_crs(3116)
rr, cc = rasterio.transform.rowcol(aff, ge.geometry.x, ge.geometry.y)
coh = pd.DataFrame({"estacion": ge.Nombre.values, "Z catálogo": ge["Z catálogo (m)"].values, "Z DEM": [Z[r, c] for r, c in zip(rr, cc)],
                    **{f"{v} obs": ge[f"{v} (°C)"].values for v in ["Tmax", "Tmed", "Tmin"]},
                    **{f"{v} mapa": [T[v][r, c] for r, c in zip(rr, cc)] for v in ["Tmax", "Tmed", "Tmin"]}})
coh.round(2).to_csv(OUT / "coherencia_temperatura.csv", index=False, encoding="utf-8-sig")

# ============================================================================= p6: Ra por mes y latitud; ETP vs Tmed
J = np.array([15, 45, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349])
lat_c = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="cuenca").to_crs(4326).geometry[0]
LAT = {"sur (2.1° N)": lat_c.bounds[1], "centro (4.6° N)": lat_c.centroid.y, "norte (7.2° N)": lat_c.bounds[3]}
ra = {}
for n, la in LAT.items():
    phi = np.deg2rad(la); dr = 1 + 0.033 * np.cos(2 * np.pi * J / 365); dec = 0.409 * np.sin(2 * np.pi * J / 365 - 1.39)
    ws = np.arccos(-np.tan(phi) * np.tan(dec))
    ra[n] = 0.408 * (1440 / np.pi) * 0.0820 * dr * (ws * np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.sin(ws))
pd.DataFrame(ra, index=MES3).round(3).to_csv(OUT / "Ra_mes_latitud.csv", encoding="utf-8-sig")
idx = np.flatnonzero(mask.ravel()); rng = np.random.default_rng(1); s = rng.choice(idx, 3000, replace=False)
pd.DataFrame({"Tmed": T["Tmed"].ravel()[s], "ETP": ETP.ravel()[s], "Z": Z.ravel()[s]}).round(1).to_csv(
    OUT / "ETP_vs_Tmed.csv", index=False, encoding="utf-8-sig")

# ============================================================================= p8: caudal de cada año completo
Qm = pd.read_csv(DAT / "caudales_ideam" / "Q_mensual_completa.csv", index_col=0, parse_dates=True)
disp = pd.read_csv(DAT / "caudales_ideam" / "disponibilidad_caudales.csv", dtype={"codigo": str})
val = disp[disp["apta (>=15 anos 1981-2010)"] == True]
qa = {}
for r in val.itertuples():
    s_ = Qm[r.codigo].loc["1960":"2025"]
    qa[r.estacion.title()] = s_.groupby(s_.index.year).apply(lambda x: x.mean() if x.count() == 12 else np.nan)
pd.DataFrame(qa).round(1).to_csv(OUT / "Q_anual_estaciones.csv", encoding="utf-8-sig")

# ============================================================================= p11: verificación nacional
LUG = {"Quibdó": (5.69, -76.66), "Buenaventura": (3.88, -77.03), "Cali": (3.45, -76.53), "Popayán": (2.44, -76.61),
       "Manizales": (5.07, -75.52), "Medellín": (6.25, -75.58), "Villavicencio": (4.14, -73.63), "Riohacha": (11.54, -72.91)}
cu4326 = cuenca.to_crs(4326)
fig, axs = plt.subplots(1, 3, figsize=(17, 7.4), constrained_layout=True)
CL = E.P_CL; cm, nm = E.P["cmap"], E.P["norm"]  # escala común de P anual (escalas.py)
ver = []
for ax, n in zip(axs, ["CHIRPS v3.0", "ERA5-Land", "ERA5"]):
    p = abrir(n).precip.sel(time=slice("1981", "2010"))
    a = p.groupby("time.year").sum("time", min_count=1).mean("year")
    im = ax.pcolormesh(a.lon, a.lat, a, cmap=cm, norm=nm, shading="nearest")
    cu4326.boundary.plot(ax=ax, color="red", lw=1.2)
    for lugar, (la, lo) in LUG.items():
        v = float(a.sel(lat=la, lon=lo, method="nearest"))
        ver.append({"producto": n, "lugar": lugar, "P (mm/año)": v})
        dxy = {"Quibdó": (-0.25, 0.3), "Buenaventura": (-0.25, -0.4), "Cali": (0.25, -0.2), "Popayán": (0.25, -0.5),
               "Manizales": (0.25, -0.1), "Medellín": (0.25, 0.35)}.get(lugar, (0.2, 0))
        ax.plot(lo, la, "o", ms=4, mfc="white", mec="black")
        ax.text(lo + dxy[0], la + dxy[1], f"{lugar} {v:,.0f}".replace(",", " "), fontsize=6.5,
                ha="right" if lugar in ("Quibdó", "Buenaventura") else "left",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75))
    ax.set_xlim(-80, -66.5); ax.set_ylim(-4.3, 13); ax.set_aspect("equal"); ax.tick_params(labelsize=7)
    ax.set_title(n + (" (Colombia; v2.0 sólo se descargó para la cuenca)" if n == "CHIRPS v3.0" else ""), fontsize=9.5, fontweight="bold")
    ax.set_xlabel("Longitud (°)", fontsize=8); ax.set_ylabel("Latitud (°)", fontsize=8); ax.grid(alpha=0.3)
    cb = E.barra(fig, im, E.P, a.values, ax=ax, shrink=0.6, pad=0.02)
    cb.set_label("P media anual 1981–2010 (mm/año)", fontsize=8)
fig.suptitle("Verificación de lectura: precipitación anual en Colombia con lugares de referencia · WGS84 (EPSG:4326) · rojo: cuenca",
             fontsize=11, fontweight="bold")
fig.savefig(OUT / "verificacion_productos_colombia.png", dpi=170, bbox_inches="tight"); plt.close(fig)
pd.DataFrame(ver).pivot(index="lugar", columns="producto", values="P (mm/año)").round(0).to_csv(OUT / "verificacion_lugares.csv", encoding="utf-8-sig")

# ============================================================================= p12: R por producto y espacio de Budyko por estación
R = {k: p - budyko(p, ETP) for k, p in P.items()}
CLr = E.R_CL; cmr, nmr = E.R["cmap"], E.R["norm"]  # escala común de R (escalas.py)
fig, axs = plt.subplots(1, 4, figsize=(22, 11), gridspec_kw=dict(wspace=0.45))
for ax, (k, a) in zip(axs, R.items()):
    im = ax.imshow(a, cmap=cmr, norm=nmr, extent=ext, interpolation="nearest")
    marco(ax, f"{k}\nR media {np.nanmean(a[mask]):,.0f} mm/año".replace(",", " "), 9.5)
    cb = E.barra(fig, im, E.R, a[mask], ax=ax, shrink=0.55, pad=0.03)
    cb.set_label("R = P − ETR (mm/año)", fontsize=8)
norte(axs[-1])
fig.suptitle("Escorrentía de largo plazo con cada fuente de precipitación (misma ETP de Hargreaves) · EPSG:3116", fontsize=12, fontweight="bold")
fig.savefig(OUT / "R_por_producto.png", dpi=180, bbox_inches="tight"); plt.close(fig)

b9 = pd.read_csv(RES / "09_balance" / "balance_subcuencas.csv", dtype={"codigo": str})
sub = gpd.read_file(RES / "06_caudales" / "subcuencas_estaciones.gpkg", layer="areas_drenaje")
geoms = {r.codigo: r.geometry for r in sub.itertuples()}; geoms["HIDRO"] = cuenca.geometry[0]
bud = []
for r in b9.itertuples():
    m = ~geometry_mask([geoms[r.codigo]], out_shape=Z.shape, transform=aff)
    m[::, :] &= mask
    sel = np.flatnonzero(m.ravel())[::5]                   # 1 de cada 5 celdas: suficiente para promedios de ≥ 5 000 km²
    e = ETP.ravel()[sel]
    R_obs = r._8 * SEG / (r._3 * 1e6) * 1000
    for k, p in P.items():
        pp = p.ravel()[sel]; ok = np.isfinite(pp) & np.isfinite(e)
        f = lambda kk: np.mean(kk * pp[ok] - budyko(kk * pp[ok], e[ok])) - R_obs
        kk = brentq(f, 0.05, 5.0)
        Pm = pp[ok].mean()
        bud.append({"codigo": r.codigo, "estacion": r.estacion, "producto": k, "phi": e[ok].mean() / Pm, "ETRobs/P": (Pm - R_obs) / Pm,
                    "ETRbudyko/P": np.mean(budyko(pp[ok], e[ok])) / Pm, "P (mm)": Pm, "P necesaria (mm)": kk * Pm,
                    "corrección de P necesaria (%)": 100 * (kk - 1),
                    "balance posible": bool(0 <= Pm - R_obs <= e[ok].mean())})
bud = pd.DataFrame(bud)
bud.round(4).to_csv(OUT / "budyko_estaciones_productos.csv", index=False, encoding="utf-8-sig")
print(bud.pivot(index="estacion", columns="producto", values="corrección de P necesaria (%)").round(1).to_string())

# ============================================================================= p13: estacionalidad
PM = leer(RES / "13_climatologia" / "P_mensual_kriging_90m_3116.tif", True)[0]
F = 10
h, w = Z.shape[0] // F * F, Z.shape[1] // F * F
with np.errstate(all="ignore"):
    B = np.nanmean(PM[:, :h, :w].reshape(12, h // F, F, w // F, F), axis=(2, 4))
tot = B.sum(0); media = tot / 12
mes_max = np.where(np.isfinite(tot), np.argmax(np.nan_to_num(B, nan=-1), axis=0) + 1, np.nan)
SI = np.nansum(np.abs(B - tot / 12), axis=0) / tot
prev, nxt = np.roll(B, 1, axis=0), np.roll(B, -1, axis=0)
picos = ((B > prev) & (B >= nxt) & (B > 1.1 * media)).sum(0).astype(float)
picos[~np.isfinite(tot)] = np.nan; SI[~np.isfinite(tot)] = np.nan
ext2 = (aff.c, aff.c + aff.a * w, aff.f + aff.e * h, aff.f)
fig, axs = plt.subplots(1, 3, figsize=(16, 11))
im0 = axs[0].imshow(mes_max, cmap=ListedColormap(plt.get_cmap("twilight_shifted")(np.linspace(0, 1, 12))), vmin=0.5, vmax=12.5,
                    extent=ext2, interpolation="nearest")
marco(axs[0], "Mes de máxima precipitación")
cb = fig.colorbar(im0, ax=axs[0], shrink=0.5, ticks=range(1, 13), pad=0.02); cb.ax.set_yticklabels(MES3, fontsize=7)
im1 = axs[1].imshow(picos, cmap=ListedColormap(["#fdae6b", "#3182bd", "#08306b"]), vmin=0.5, vmax=3.5, extent=ext2, interpolation="nearest")
marco(axs[1], "Número de temporadas lluviosas")
cb = fig.colorbar(im1, ax=axs[1], shrink=0.5, ticks=[1, 2, 3], pad=0.02); cb.ax.set_yticklabels(["1 (unimodal)", "2 (bimodal)", "3"], fontsize=7)
im2 = axs[2].imshow(SI, cmap="YlOrBr", vmin=0.1, vmax=0.45, extent=ext2, interpolation="nearest")
marco(axs[2], "Índice de estacionalidad (Walsh y Lawler)")
fig.colorbar(im2, ax=axs[2], shrink=0.5, pad=0.02).set_label("SI (< 0.2 lluvia repartida; > 0.4 estación seca marcada)", fontsize=7)
norte(axs[2])
fig.suptitle("Variación espacial del ciclo anual de la precipitación (IDEAM, kriging mensual 1981–2010) · EPSG:3116",
             fontsize=12, fontweight="bold")
fig.savefig(OUT / "estacionalidad.png", dpi=180, bbox_inches="tight"); plt.close(fig)
V = np.isfinite(tot)                                    # sólo celdas de la cuenca
est_res = {"% área bimodal": 100 * np.mean(picos[V] == 2), "% área unimodal": 100 * np.mean(picos[V] == 1),
           "% área con 3 picos": 100 * np.mean(picos[V] == 3),
           "SI medio": np.nanmean(SI), "SI mínimo": np.nanmin(SI), "SI máximo": np.nanmax(SI),
           **{f"% área con máximo en {MES3[m - 1]}": 100 * np.mean(mes_max[V] == m) for m in range(1, 13)}}
pd.Series(est_res).round(2).to_csv(OUT / "estacionalidad_resumen.csv", encoding="utf-8-sig")
print(pd.Series(est_res).round(1).to_string())

# ============================================================================= p14: punto a píxel
cv = pd.read_csv(RES / "04_precipitacion_interpolada" / "validacion_cruzada_estaciones.csv")
cv = cv[cv.dentro == True]
rr, cc = rasterio.transform.rowcol(aff, cv.x, cv.y)
pp = pd.DataFrame({"estacion": cv.nombre.values, "P medida": cv["P observada"].values,
                   "IDEAM (kriging sin la estación)": cv["P estimada Kriging ordinario (gaussiano)"].values,
                   **{k: [P[k][r, c] for r, c in zip(rr, cc)] for k in ["CHIRPS", "ERA5-Land", "ERA5"]}}).dropna()
pp.round(1).to_csv(OUT / "punto_a_pixel.csv", index=False, encoding="utf-8-sig")
met = {k: {"n": len(pp), "sesgo (mm/año)": (pp[k] - pp["P medida"]).mean(),
           "RMSE (mm/año)": np.sqrt(((pp[k] - pp["P medida"]) ** 2).mean()), "r": np.corrcoef(pp[k], pp["P medida"])[0, 1]}
       for k in ["IDEAM (kriging sin la estación)", "CHIRPS", "ERA5-Land", "ERA5"]}
pd.DataFrame(met).T.round(3).to_csv(OUT / "punto_a_pixel_metricas.csv", encoding="utf-8-sig")
print(pd.DataFrame(met).T.round(2).to_string())
print(pis.round(1).to_string(index=False))
print(coh.drop(columns="estacion").describe().round(1).loc[["mean", "min", "max"]].to_string())
print("listo")
