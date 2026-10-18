"""
Punto 13 - Climatología de la precipitación: ciclo anual de la cuenca y mapas de los doce meses (IDEAM 1981-2010).

Para cada mes m: kriging ordinario (variograma gaussiano ajustado al mes, pesos de Cressie) de la precipitación media
mensual de las 266 estaciones del punto 3, sobre la grilla de 90 m. P̄m de la cuenca = promedio del mapa del mes.
El ciclo se resume también por regiones: alto Cauca (área de La Balsa), Valle del Cauca (La Balsa → La Virginia)
y Cauca medio (La Virginia → Hidroituango).

Salidas: trabajo1/resultados/13_climatologia/
    P_mensual_kriging_90m_3116.tif (12 bandas), panel_P_mensual.png, ciclo_anual.csv, ciclo_regiones.csv
"""
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import BoundaryNorm, LinearSegmentedColormap
from rasterio.features import geometry_mask
from scipy.optimize import curve_fit
from scipy.spatial.distance import cdist, pdist

import sys  # noqa: E402
sys.path.insert(0, str(Path(__file__).parent))
import escalas as E  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "trabajo1" / "resultados"
DEL = RES / "01_delimitacion"
OUT = RES / "13_climatologia"
OUT.mkdir(parents=True, exist_ok=True)
MESES = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
NOMBRES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
CHUNK = 200_000

# estaciones: mismo criterio que el punto 3
g = gpd.read_file(RES / "03_estaciones_precipitacion" / "estaciones_precipitacion.gpkg")
g["zona"] = g.CODIGO.astype(int).astype(str).str.zfill(8).str[:2]
g = g[(g.dentro | (g.zona == "26")) & (g.CODIGO.astype(int) != 26230160)].copy()
g["x"], g["y"] = g.geometry.x, g.geometry.y
g = g.groupby(["x", "y"], as_index=False)[MESES + ["ANUAL"]].mean()
xy = g[["x", "y"]].to_numpy()
print("estaciones:", len(g))

with rasterio.open(DEL / "dem_cuenca_90m_3116.tif") as src:
    Z = src.read(1, masked=True); prof, aff = src.profile, src.transform
mask = ~Z.mask
rr, cc = np.nonzero(mask)
qx, qy = rasterio.transform.xy(aff, rr, cc)
q = np.c_[qx, qy]

gauss = lambda h, c0, c, a: c0 + c * (1 - np.exp(-3 * (h / a) ** 2))
h = pdist(xy)
edges = np.linspace(0, 100_000, 21); k = np.digitize(h, edges) - 1; okb = (k >= 0) & (k < 20)


def kriging_mes(z):
    sv = 0.5 * pdist(z[:, None], "sqeuclidean")
    hb = np.array([h[okb & (k == i)].mean() for i in range(20)])
    gb = np.array([sv[okb & (k == i)].mean() for i in range(20)])
    nb = np.array([(okb & (k == i)).sum() for i in range(20)])
    v = z.var()
    p, _ = curve_fit(gauss, hb, gb, p0=[0.1 * v, v, 60_000], sigma=gb / np.sqrt(nb),
                     bounds=([0, 0, 5_000], [2 * v, 3 * v, 400_000]), maxfev=20_000)
    gam = lambda d: np.where(d > 0, gauss(d, *p), 0.0)
    n = len(z)
    A = np.ones((n + 1, n + 1)); A[:n, :n] = gam(cdist(xy, xy)); A[n, n] = 0
    w = np.linalg.solve(A, np.r_[z, 0.0])
    out = np.empty(len(q))
    for i in range(0, len(q), CHUNK):
        G = np.ones((len(q[i:i + CHUNK]), n + 1)); G[:, :-1] = gam(cdist(q[i:i + CHUNK], xy))
        out[i:i + CHUNK] = G @ w
    return np.maximum(out, 0), p


import sys  # noqa: E402
TIF = OUT / "P_mensual_kriging_90m_3116.tif"
CACHE = TIF.exists() and "--recalcular" not in sys.argv     # reutiliza los mapas ya interpolados
mapas, vario = np.full((12,) + mask.shape, np.nan, dtype="float32"), []
if CACHE:
    with rasterio.open(TIF) as s:
        mapas = s.read().astype("float32"); mapas[mapas == -9999] = np.nan
    vario = pd.read_csv(OUT / "ciclo_anual.csv")[["mes", "pepita", "meseta parcial", "rango (km)"]].to_dict("records")
for m, mes in enumerate([] if CACHE else MESES):
    est, p = kriging_mes(g[mes].to_numpy(float))
    mapas[m][rr, cc] = est
    vario.append({"mes": mes, "pepita": p[0], "meseta parcial": p[1], "rango (km)": p[2] / 1000})
    print(mes, f"media cuenca {est.mean():.1f} mm  rango {p[2] / 1000:.0f} km")
if not CACHE:
    prof.update(dtype="float32", nodata=-9999, compress="deflate", count=12)
    with rasterio.open(TIF, "w", **prof) as d:
        d.write(np.where(np.isnan(mapas), -9999, mapas))

# ----------------------------------------------------------------------------- ciclo anual
with rasterio.open(RES / "04_precipitacion_interpolada" / "P_anual_kriging_90m_3116.tif") as s:
    P_anual = s.read(1)[rr, cc]
ciclo = pd.DataFrame({"mes": MESES, "P media cuenca (mm)": [mapas[m][rr, cc].mean() for m in range(12)],
                      "P media estaciones dentro (mm)": [g.loc[:, m].mean() for m in MESES]}).set_index("mes")
ciclo["% del total anual"] = 100 * ciclo["P media cuenca (mm)"] / ciclo["P media cuenca (mm)"].sum()
ciclo = ciclo.join(pd.DataFrame(vario).set_index("mes"))
ciclo.to_csv(OUT / "ciclo_anual.csv", encoding="utf-8-sig")
print(ciclo.round(1).to_string())
print(f"suma mensual {ciclo['P media cuenca (mm)'].sum():.0f} mm vs mapa anual {P_anual.mean():.0f} mm")

# regiones a partir de las áreas de drenaje del punto 8
sub = gpd.read_file(RES / "06_caudales" / "subcuencas_estaciones.gpkg", layer="areas_drenaje").set_index("codigo")
msk = lambda geom: ~geometry_mask([geom], out_shape=mask.shape, transform=aff)
balsa, virginia = msk(sub.geometry["26027010"]), msk(sub.geometry["26177030"])
REG = {"Alto Cauca (hasta La Balsa)": balsa & mask, "Valle del Cauca (La Balsa → La Virginia)": virginia & ~balsa & mask,
       "Cauca medio (La Virginia → Hidroituango)": mask & ~virginia}
reg = pd.DataFrame({n: [np.nanmean(mapas[m][r]) for m in range(12)] for n, r in REG.items()}, index=MESES)
reg.loc["área (km²)"] = [r.sum() * abs(aff.a * aff.e) / 1e6 for r in REG.values()]
reg.to_csv(OUT / "ciclo_regiones.csv", encoding="utf-8-sig")
print(reg.round(1).to_string())

# ----------------------------------------------------------------------------- panel de 12 mapas
cuenca = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="cuenca")
rio = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="rio_principal")
ext = (aff.c, aff.c + aff.a * mask.shape[1], aff.f + aff.e * mask.shape[0], aff.f)
CL = E.PM_CL; cmap, norm = E.PM["cmap"], E.PM["norm"]  # misma paleta que la P anual (escalas.py)
minx, miny, maxx, maxy = cuenca.total_bounds
fig, axs = plt.subplots(2, 6, figsize=(20, 14))
fig.subplots_adjust(left=0.03, right=0.86, top=0.93, bottom=0.03, wspace=0.12, hspace=0.12)
for m, ax in enumerate(axs.flat):
    im = ax.imshow(mapas[m], cmap=cmap, norm=norm, extent=ext, interpolation="nearest")
    rio.plot(ax=ax, color="#08306b", linewidth=0.7)
    cuenca.boundary.plot(ax=ax, color="black", linewidth=0.8)
    ax.set_xlim(minx - 8000, maxx + 8000); ax.set_ylim(miny - 8000, maxy + 8000); ax.set_aspect("equal")
    ax.set_title(f"{NOMBRES[m]}\n{ciclo['P media cuenca (mm)'].iloc[m]:.0f} mm", fontsize=11, fontweight="bold")
    ax.ticklabel_format(style="plain"); ax.tick_params(labelsize=5.5)
    ax.set_xticks([700000, 800000]); ax.set_yticks([800000, 900000, 1000000, 1100000, 1200000])
    plt.setp(ax.get_yticklabels(), rotation=90, va="center")
    ax.grid(color="0.6", lw=0.3, ls=":"); ax.set_xlabel(""); ax.set_ylabel("")
axs[0, 5].annotate("N", xy=(0.85, 0.975), xytext=(0.85, 0.9), xycoords="axes fraction", ha="center", fontsize=12,
                   fontweight="bold", arrowprops=dict(facecolor="black", width=3, headwidth=9))
ax = axs[1, 0]
for i, colr in enumerate(["black", "white"]):
    ax.add_patch(plt.Rectangle((minx + i * 25000, miny - 4000), 25000, 3500, fc=colr, ec="black", lw=0.5, zorder=9))
ax.text(minx, miny + 2500, "0", fontsize=6); ax.text(minx + 50000, miny + 2500, "50 km", fontsize=6, ha="center")
cb = E.barra(fig, im, E.PM, *mapas, cax=fig.add_axes([0.88, 0.25, 0.015, 0.5]))
cb.set_label("Precipitación media mensual 1981–2010 (mm)", fontsize=11)
fig.suptitle("Precipitación media mensual multianual 1981–2010 · kriging ordinario de estaciones IDEAM · "
             "MAGNA-SIRGAS / Colombia Bogotá (EPSG:3116), coordenadas en m", fontsize=13, fontweight="bold", y=0.985)
fig.savefig(OUT / "panel_P_mensual.png", dpi=170, bbox_inches="tight"); plt.close(fig)
print("listo")

# ----------------------------------------------------------------------------- gráfica del ciclo anual
fig, ax = plt.subplots(figsize=(10, 5.2))
x = np.arange(12)
ax.bar(x, ciclo["P media cuenca (mm)"], color="#9ecae1", edgecolor="#4a7fa8", width=0.65, label="Cuenca completa (P̄m)", zorder=2)
for xi, v in zip(x, ciclo["P media cuenca (mm)"]):
    ax.text(xi, v + 4, f"{v:.0f}", ha="center", fontsize=8, color="#244c6e")
for (n, c), mk in zip([(n, c) for n, c in zip(REG, ["#e6550d", "#31a354", "#3f007d"])], ["o", "s", "^"]):
    ax.plot(x, reg.loc[MESES, n], color=c, marker=mk, lw=1.8, ms=6, label=n, zorder=3)
ax.set_xticks(x, [n[:3] for n in NOMBRES]); ax.set_ylabel("Precipitación media mensual (mm)")
ax.set_ylim(0, 320); ax.grid(axis="y", alpha=0.3, zorder=0); ax.legend(fontsize=8.5, loc="upper left", ncol=2)
ax.set_title("Ciclo anual de la precipitación, cuenca del río Cauca hasta Hidroituango (IDEAM, 1981–2010)", fontsize=11)
fig.tight_layout(); fig.savefig(OUT / "ciclo_anual.png", dpi=200); plt.close(fig)
