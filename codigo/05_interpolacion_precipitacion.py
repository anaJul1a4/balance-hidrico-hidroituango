"""
Punto 3 - Mapa de precipitación media anual multianual (IDEAM 1981-2010) por interpolación espacial.

Se comparan IDW (potencias 1-3, 12 vecinos) y Kriging Ordinario (variograma ajustado) mediante
validación cruzada "leave-one-out"; el método con menor RMSE genera el mapa final sobre la grilla
de 90 m del DEM GLO-30 (EPSG:3116).

Estaciones: todas las de dentro de la cuenca + las del vecindario (≤ 20 km) de la zona IDEAM 26 (Cauca).
Se excluyen las del vecindario de otras vertientes (Pacífico 11/52/53/54, Magdalena 21/22/23, Nechí 27)
y la estación Briceño (26230160, 6455 mm/año): fuera de la cuenca, en la vertiente expuesta al Bajo Cauca,
sin estaciones vecinas que la corroboren (error LOO > 4000 mm). Se reporta la sensibilidad a su inclusión.
"""
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import LightSource
from matplotlib.lines import Line2D
from scipy.optimize import curve_fit
from scipy.spatial import cKDTree
from scipy.spatial.distance import cdist, pdist

sys.path.insert(0, str(Path(__file__).parent))
import escalas as E  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEL = ROOT / "trabajo1" / "resultados" / "01_delimitacion"
EST = ROOT / "trabajo1" / "resultados" / "03_estaciones_precipitacion"
OUT = ROOT / "trabajo1" / "resultados" / "04_precipitacion_interpolada"
# --todas: usa las 358 estaciones del mapa de estaciones (dentro + vecindario <= 20 km de cualquier vertiente,
# incluida Briceño), sin filtros; resultados en la subcarpeta todas_estaciones/
TODAS = "--todas" in sys.argv
if TODAS:
    OUT = OUT / "todas_estaciones"
VEC = "vecindario ≤ 20 km, todas las vertientes" if TODAS else "vecindario, zona 26"
OUT.mkdir(parents=True, exist_ok=True)
CRS = "EPSG:3116"
CHUNK = 200_000
EXCLUIR = {26230160: "Briceño"}

# ----------------------------------------------------------------------------- estaciones
g = gpd.read_file(EST / "estaciones_precipitacion.gpkg")
g["zona"] = g.CODIGO.astype(int).astype(str).str.zfill(8).str[:2]
if not TODAS:
    g = g[g.dentro | (g.zona == "26")].copy()
g_brice = g.copy()  # para el análisis de sensibilidad
if not TODAS:
    g = g[~g.CODIGO.astype(int).isin(EXCLUIR)]
g["x"], g["y"] = g.geometry.x, g.geometry.y
g = g.groupby(["x", "y"], as_index=False).agg(ANUAL=("ANUAL", "mean"), dentro=("dentro", "max"), NOMBRE=("NOMBRE", "first"),
                                              n=("ANUAL", "size"))  # promedia estaciones coincidentes
xy, z = g[["x", "y"]].to_numpy(), g.ANUAL.to_numpy()
n = len(z)
print(f"estaciones usadas: {n} ({g.dentro.sum()} dentro, {(~g.dentro).sum()} {VEC})")

# ----------------------------------------------------------------------------- variograma
MODELOS = {
    "esferico": lambda h, c0, c, a: np.where(h < a, c0 + c * (1.5 * h / a - 0.5 * (h / a) ** 3), c0 + c),
    "exponencial": lambda h, c0, c, a: c0 + c * (1 - np.exp(-3 * h / a)),
    "gaussiano": lambda h, c0, c, a: c0 + c * (1 - np.exp(-3 * (h / a) ** 2)),
}
h = pdist(xy)
sv = 0.5 * pdist(z[:, None], "sqeuclidean")
HMAX, NB = 100_000, 20
edges = np.linspace(0, HMAX, NB + 1)
idx = np.digitize(h, edges) - 1
ok = (idx >= 0) & (idx < NB)
hb = np.array([h[ok & (idx == k)].mean() for k in range(NB)])
gb = np.array([sv[ok & (idx == k)].mean() for k in range(NB)])
nb = np.array([(ok & (idx == k)).sum() for k in range(NB)])

ajustes = {}
var = z.var()
for nom, f in MODELOS.items():
    try:
        p, _ = curve_fit(f, hb, gb, p0=[0.1 * var, var, 60_000], sigma=gb / np.sqrt(nb),  # pesos de Cressie N/γ²
                         bounds=([0, 0, 5_000], [2 * var, 3 * var, 400_000]), maxfev=20_000)
        ajustes[nom] = (p, np.sum(nb * ((f(hb, *p) - gb) / gb) ** 2))
    except RuntimeError:
        pass
mod = min(ajustes, key=lambda k: ajustes[k][1])
c0, c, a = ajustes[mod][0]
gamma = lambda d: np.where(d > 0, MODELOS[mod](d, c0, c, a), 0.0)
print(f"variograma {mod}: pepita={c0:.0f}  meseta parcial={c:.0f}  rango={a/1000:.1f} km")


# ----------------------------------------------------------------------------- interpoladores
def ok_matriz(pts):
    m = len(pts)
    A = np.ones((m + 1, m + 1))
    A[:m, :m] = gamma(cdist(pts, pts))
    A[m, m] = 0.0
    return A


def ok_predecir(pts, vals, q, Ainv=None, var_k=False):
    """Kriging ordinario global en forma dual: z*(x) = [γ(x-xi), 1] · A⁻¹ [z, 0]."""
    if Ainv is None:
        Ainv = np.linalg.inv(ok_matriz(pts))
    w = Ainv @ np.r_[vals, 0.0]
    out, sig = np.empty(len(q)), np.empty(len(q)) if var_k else None
    for i in range(0, len(q), CHUNK):
        G = np.ones((len(q[i:i + CHUNK]), len(pts) + 1))
        G[:, :-1] = gamma(cdist(q[i:i + CHUNK], pts))
        out[i:i + CHUNK] = G @ w
        if var_k:
            sig[i:i + CHUNK] = np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", G, Ainv, G), 0))
    return out, sig


def idw_predecir(pts, vals, q, p=2.0, k=12):
    tree = cKDTree(pts)
    out = np.empty(len(q))
    for i in range(0, len(q), CHUNK):
        d, j = tree.query(q[i:i + CHUNK], k=min(k, len(pts)))
        d = np.maximum(d, 1.0)
        w = 1 / d ** p
        out[i:i + CHUNK] = (w * vals[j]).sum(1) / w.sum(1)
    return out


# ----------------------------------------------------------------------------- validación cruzada LOO
def metricas(obs, est):
    e = est - obs
    return {"RMSE (mm)": np.sqrt(np.mean(e ** 2)), "MAE (mm)": np.mean(np.abs(e)), "Sesgo (mm)": e.mean(),
            "R2": 1 - np.sum(e ** 2) / np.sum((obs - obs.mean()) ** 2), "r": np.corrcoef(obs, est)[0, 1]}


cv, pred_cv = {}, {}
for p in [1.0, 1.5, 2.0, 2.5, 3.0]:
    e = np.array([idw_predecir(np.delete(xy, i, 0), np.delete(z, i), xy[i:i + 1], p=p)[0] for i in range(n)])
    cv[f"IDW p={p:g}"], pred_cv[f"IDW p={p:g}"] = metricas(z, e), e
e = np.array([ok_predecir(np.delete(xy, i, 0), np.delete(z, i), xy[i:i + 1])[0][0] for i in range(n)])
cv[f"Kriging ordinario ({mod})"], pred_cv[f"Kriging ordinario ({mod})"] = metricas(z, e), e
cvdf = pd.DataFrame(cv).T.sort_values("RMSE (mm)")
cvdf.round(3).to_csv(OUT / "validacion_cruzada.csv", encoding="utf-8-sig")
pd.DataFrame({"nombre": g.NOMBRE, "x": g.x, "y": g.y, "dentro": g.dentro, "P observada": z,
              **{f"P estimada {k}": v for k, v in pred_cv.items()}}).round(1).to_csv(
    OUT / "validacion_cruzada_estaciones.csv", index=False, encoding="utf-8-sig")
print(cvdf.round(3).to_string())
mejor = cvdf.index[0]
print("mejor método:", mejor)

# ----------------------------------------------------------------------------- grilla 90 m
with rasterio.open(DEL / "dem_cuenca_90m_3116.tif") as src:
    dem = src.read(1, masked=True)
    prof, aff = src.profile, src.transform
mask = ~dem.mask
rr, cc = np.nonzero(mask)
qx, qy = rasterio.transform.xy(aff, rr, cc)
q = np.c_[qx, qy]

pk, _ = ok_predecir(xy, z, q)
p_idw = float(cvdf.filter(like="IDW", axis=0).index[0].split("=")[1])
pi = idw_predecir(xy, z, q, p=p_idw)
P = {"kriging": pk, "idw": pi}
prof.update(dtype="float32", nodata=-9999, compress="deflate")
for k, v in P.items():
    arr = np.full(mask.shape, -9999, dtype="float32")
    arr[rr, cc] = np.maximum(v, 0)
    with rasterio.open(OUT / f"P_anual_{k}_90m_3116.tif", "w", **prof) as d:
        d.write(arr, 1)
final = "kriging" if mejor.startswith("Kriging") else "idw"
Pmap = np.full(mask.shape, np.nan)
Pmap[rr, cc] = np.maximum(P[final], 0)

# desviación estándar de kriging (grilla de 900 m, sólo como indicador de incertidumbre)
sub = (slice(None, None, 10), slice(None, None, 10))
r2, c2 = np.nonzero(mask[sub])
qx2, qy2 = rasterio.transform.xy(aff, r2 * 10, c2 * 10)
_, sk = ok_predecir(xy, z, np.c_[qx2, qy2], var_k=True)

area = mask.sum() * abs(aff.a * aff.e) / 1e6
xb = g_brice.groupby([g_brice.geometry.x, g_brice.geometry.y]).ANUAL.mean()
xyb, zb = np.array(xb.index.tolist()), xb.to_numpy()
P_brice = ok_predecir(xyb, zb, q)[0].mean() if final == "kriging" else idw_predecir(xyb, zb, q, p=p_idw).mean()
res = {
    "Método final": mejor,
    "P media cuenca (mm/año)": float(np.nanmean(Pmap)),
    "P media cuenca IDW (mm/año)": float(pi.mean()),
    "P media cuenca Kriging (mm/año)": float(pk.mean()),
    "P mín (mm/año)": float(np.nanmin(Pmap)), "P máx (mm/año)": float(np.nanmax(Pmap)),
    "Volumen anual (km³)": float(np.nanmean(Pmap)) / 1e6 * area,
    "Caudal equivalente (m³/s)": float(np.nanmean(Pmap)) / 1000 * area * 1e6 / (365.25 * 86400),
    "Desv. est. kriging media (mm)": float(sk.mean()),
    "N estaciones": n,
    "P media cuenca incluyendo Briceño (mm/año)": float(P_brice),
    f"Variograma {mod}: pepita / meseta parcial / rango (km)": f"{c0:.0f} / {c:.0f} / {a/1000:.1f}",
}
pd.Series(res, name="valor").to_csv(OUT / "resumen_precipitacion.csv", encoding="utf-8-sig")
print(pd.Series(res).to_string())

# ----------------------------------------------------------------------------- figura: variograma + CV
fig, axs = plt.subplots(1, 2, figsize=(11, 4.2))
axs[0].scatter(hb / 1000, gb, s=12 + nb / nb.max() * 60, c="k", label="Semivariograma experimental")
hh = np.linspace(0, HMAX, 300)
for nom, (p, _) in ajustes.items():
    axs[0].plot(hh / 1000, MODELOS[nom](hh, *p), lw=2 if nom == mod else 1, label=nom + (" (elegido)" if nom == mod else ""))
axs[0].set_xlabel("Distancia (km)"); axs[0].set_ylabel("γ(h) (mm²)"); axs[0].legend(fontsize=8); axs[0].grid(alpha=0.3)
axs[0].set_title("Variograma de la precipitación media anual")
for k in [cvdf.filter(like="IDW", axis=0).index[0], cvdf.filter(like="Kriging", axis=0).index[0]]:
    axs[1].scatter(z, pred_cv[k], s=10, alpha=0.6, label=f"{k}  RMSE={cv[k]['RMSE (mm)']:.0f} mm")
lim = [0, z.max() * 1.05]
axs[1].plot(lim, lim, "k--", lw=0.8); axs[1].set_xlim(lim); axs[1].set_ylim(lim)
axs[1].set_xlabel("P observada (mm/año)"); axs[1].set_ylabel("P estimada LOO (mm/año)")
axs[1].legend(fontsize=7.5); axs[1].grid(alpha=0.3); axs[1].set_title("Validación cruzada (leave-one-out)")
fig.tight_layout(); fig.savefig(OUT / "variograma_validacion_cruzada.png", dpi=200)

# ----------------------------------------------------------------------------- mapa
cuenca = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="cuenca")
rio = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="rio_principal")
cierre = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="punto_cierre")
ext = (aff.c, aff.c + aff.a * mask.shape[1], aff.f + aff.e * mask.shape[0], aff.f)
zdem = dem.filled(np.nan).astype(float)
hs = LightSource(azdeg=315, altdeg=45).hillshade(np.nan_to_num(zdem, nan=np.nanmin(zdem)), vert_exag=3,
                                                   dx=aff.a, dy=aff.a)

fig, ax = plt.subplots(figsize=(10, 15))
im = ax.imshow(Pmap, cmap=E.P["cmap"], norm=E.P["norm"], extent=ext, zorder=1, interpolation="nearest")
ax.imshow(np.where(mask, hs, np.nan), cmap="gray", alpha=0.25, extent=ext, zorder=2)
X = np.linspace(ext[0], ext[1], mask.shape[1]); Y = np.linspace(ext[3], ext[2], mask.shape[0])
cs = ax.contour(X, Y, Pmap, levels=np.arange(1000, 4001, 500), colors="0.15", linewidths=0.5, zorder=3)
ax.clabel(cs, fmt="%d", fontsize=6)
rio.plot(ax=ax, color="#08306b", linewidth=1.6, zorder=4)
cuenca.boundary.plot(ax=ax, color="black", linewidth=1.3, zorder=5)
gi, go = g[g.dentro], g[~g.dentro]
ax.scatter(gi.x, gi.y, marker="o", s=14, c="white", edgecolors="black", linewidths=0.6, zorder=6)
ax.scatter(go.x, go.y, marker="^", s=20, c="white", edgecolors="black", linewidths=0.6, zorder=6)
cierre.plot(ax=ax, color="red", marker="^", markersize=90, edgecolor="black", zorder=7)

cb = E.barra(fig, im, E.P, Pmap, ax=ax, shrink=0.35, pad=0.02)
cb.set_label("Precipitación media anual (mm/año)", fontsize=8); cb.ax.tick_params(labelsize=7)
minx, miny, maxx, maxy = cuenca.total_bounds
ax.set_xlim(minx - 20000, maxx + 20000); ax.set_ylim(miny - 15000, maxy + 15000)
ax.set_aspect("equal"); ax.ticklabel_format(style="plain"); ax.tick_params(labelsize=7)
ax.set_xlabel("Este (m)", fontsize=8); ax.set_ylabel("Norte (m)", fontsize=8)
plt.setp(ax.get_yticklabels(), rotation=90, va="center")
ax.grid(color="0.7", lw=0.3, ls=":")
ax.annotate("N", xy=(0.92, 0.70), xytext=(0.92, 0.645), xycoords="axes fraction", ha="center", fontsize=14,
            fontweight="bold", arrowprops=dict(facecolor="black", width=4, headwidth=12))
ax.legend(handles=[
    Line2D([], [], ls="", marker="o", ms=6, mfc="white", mec="black", label=f"Estación IDEAM dentro ({gi.shape[0]})"),
    Line2D([], [], ls="", marker="^", ms=6, mfc="white", mec="black", label=f"Estación {VEC} ({go.shape[0]})"),
    Line2D([], [], color="0.15", lw=0.6, label="Isoyetas (cada 500 mm)"),
    Line2D([], [], color="#08306b", lw=1.6, label="Río Cauca"),
    Line2D([], [], color="black", lw=1.3, label="Límite de la cuenca"),
    Line2D([], [], ls="", marker="^", ms=9, mfc="red", mec="black", label="Punto de cierre (Hidroituango)"),
], loc="upper left", fontsize=8, framealpha=0.92)
ax.text(0.99, 0.005,
        f"Método: {mejor}\nP media de la cuenca: {res['P media cuenca (mm/año)']:.0f} mm/año\n"
        f"Validación cruzada: RMSE = {cv[mejor]['RMSE (mm)']:.0f} mm, R² = {cv[mejor]['R2']:.2f}\n"
        "Datos: IDEAM, Promedios Climatológicos 1981–2010\nMAGNA-SIRGAS / Colombia Bogotá (EPSG:3116), celda 90 m",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=7,
        path_effects=[pe.withStroke(linewidth=2, foreground="white")])
ax.set_title("Precipitación media anual multianual 1981–2010" + (" — todas las estaciones" if TODAS else "")
             + "\nCuenca del río Cauca hasta Hidroituango",
             fontsize=11, fontweight="bold")
fig.tight_layout()
fig.savefig(OUT / "mapa_precipitacion_media_anual.png", dpi=300)
