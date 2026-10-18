"""
Figuras del informe escrito, dibujadas al tamaño real de impresión (ancho de página 16 cm = 6.3 in) para que el texto se lea en
papel: títulos 8.5 pt, ejes y leyendas 7 pt, marcas 6.5 pt. Se dibujan desde los resultados guardados (rásteres y tablas), con las
mismas escalas de color por variable (escalas.py). Las figuras de la página web no se modifican.

Salida: resultados/informe_figs/*.png (300 ppp). Se insertan en el Word a su ancho nativo (escala 1:1).
"""
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import rasterio  # noqa: E402
from matplotlib.colors import BoundaryNorm, LightSource, ListedColormap, TwoSlopeNorm  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from scipy.optimize import curve_fit  # noqa: E402
from scipy.spatial.distance import pdist  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
import escalas as E  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "resultados"
OUT = RES / "informe_figs"
OUT.mkdir(exist_ok=True)
W = 6.3                                     # ancho útil de página (in)
D = 1                                       # resolución completa: celdas de 90 m, sin diezmar
plt.rcParams.update({"font.size": 7, "axes.titlesize": 8.5, "axes.titleweight": "bold", "axes.labelsize": 7,
                     "xtick.labelsize": 6.5, "ytick.labelsize": 6.5, "legend.fontsize": 6.5, "axes.linewidth": 0.6,
                     "xtick.major.width": 0.5, "ytick.major.width": 0.5, "savefig.dpi": 600, "figure.dpi": 100})
MILES = FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " "))
MES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
MES1 = ["E", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]


def leer(p, banda=1, todas=False):
    with rasterio.open(p) as s:
        a = (s.read() if todas else s.read(banda)).astype("float64"); a[a == s.nodata] = np.nan
        return a, s.transform


# ----------------------------------------------------------------------------- base cartográfica común
DEL = RES / "01_delimitacion"
cuenca = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="cuenca")
rio = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="rio_principal")
cierre = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="punto_cierre")
Z, aff = leer(DEL / "dem_cuenca_90m_3116.tif")
mask = np.isfinite(Z)
EXT = (aff.c, aff.c + aff.a * Z.shape[1], aff.f + aff.e * Z.shape[0], aff.f)
HS = LightSource(azdeg=315, altdeg=45).hillshade(np.nan_to_num(Z, nan=np.nanmin(Z)), vert_exag=3, dx=aff.a, dy=aff.a)
HS = np.where(mask, HS, np.nan)[::D, ::D]
minx, miny, maxx, maxy = cuenca.total_bounds


def d(a):
    return np.where(mask, a, np.nan)[::D, ::D]


XC = np.linspace(EXT[0], EXT[1], Z.shape[1]); YC = np.linspace(EXT[3], EXT[2], Z.shape[0])


def suave(a, s=6):
    """Campo suavizado (gaussiano, σ ≈ 0.5 km) sólo para trazar isolíneas legibles; los colores usan el campo original."""
    from scipy.ndimage import gaussian_filter
    v = np.where(mask & np.isfinite(a), a, 0.0); w = (mask & np.isfinite(a)).astype(float)
    with np.errstate(invalid="ignore"):
        return np.where(mask, gaussian_filter(v, s) / gaussian_filter(w, s), np.nan)


def mapa(ax, a, cmap, norm, titulo, sombra=0.18, lev=None, fmt="%g", caja=None, rotulos=True):
    """Mapa a resolución completa con sombreado; lev = isolíneas rotuladas; caja = texto de media y rango (abajo a la derecha)."""
    im = ax.imshow(d(a), cmap=cmap, norm=norm, extent=EXT, interpolation="nearest", zorder=1)
    ax.imshow(HS, cmap="gray", alpha=sombra, extent=EXT, zorder=2)
    if lev is not None:
        cs = ax.contour(XC, YC, suave(a), levels=lev, colors="0.15", linewidths=0.3, zorder=3)   # isolíneas sobre el campo suavizado
        if rotulos:
            ax.clabel(cs, levels=cs.levels[::2] if len(cs.levels) > 4 else cs.levels, fmt=fmt, fontsize=4.5, inline_spacing=1)
    if caja:
        ax.text(0.97, 0.015, caja, transform=ax.transAxes, ha="right", va="bottom", fontsize=5.3, zorder=10,
                bbox=dict(fc="white", ec="0.6", lw=0.3, pad=1.2, alpha=0.9))
    rio.plot(ax=ax, color="#08306b", lw=0.6, zorder=4)
    cuenca.boundary.plot(ax=ax, color="black", lw=0.6, zorder=5)
    cierre.plot(ax=ax, color="white", marker="^", markersize=14, edgecolor="black", linewidth=0.5, zorder=6)
    ax.set_xlim(minx - 8000, maxx + 8000); ax.set_ylim(miny - 8000, maxy + 8000); ax.set_aspect("equal")
    ax.set_xticks([700000, 800000]); ax.set_yticks([800000, 1000000, 1200000])
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:.0f}")); ax.yaxis.set_major_formatter(
        FuncFormatter(lambda v, _: f"{v / 1000:.0f}"))
    plt.setp(ax.get_yticklabels(), rotation=90, va="center")
    ax.tick_params(length=2, pad=1.5); ax.grid(color="0.6", lw=0.25, ls=":")
    ax.set_title(titulo, pad=3)
    ax.set_xlabel(""); ax.set_ylabel("")      # geopandas pone «Easting/Northing [metre]»
    return im


def norte(ax, x=0.86, y=0.94):
    ax.annotate("N", xy=(x, y), xytext=(x, y - 0.07), xycoords="axes fraction", ha="center", va="center", fontsize=7,
                fontweight="bold", arrowprops=dict(facecolor="black", width=1.2, headwidth=4, headlength=4))


def escala_km(ax):
    sx, sy = minx - 6000, miny - 4000          # abajo a la izquierda, al lado de la punta sur de la cuenca
    for i, c in enumerate(["black", "white"]):
        ax.add_patch(plt.Rectangle((sx + i * 12500, sy), 12500, 3500, fc=c, ec="black", lw=0.4, zorder=9))
    ax.text(sx + 12500, sy + 9000, "25 km", fontsize=5.5, ha="center", va="center")


def barra(fig, esc, datos, ax, etiqueta, **kw):
    cb = E.barra(fig, None, esc, datos, ax=ax, **({"shrink": 0.62, "pad": 0.04, "aspect": 28} | kw))
    cb.ax.tick_params(labelsize=6, length=2, pad=1.5); cb.set_label(etiqueta, fontsize=6.5, labelpad=2)
    return cb


def pie_crs(fig, y=0.005):
    fig.text(0.5, y, "Coordenadas en km · MAGNA-SIRGAS / Colombia Bogotá (EPSG:3116)", ha="center", fontsize=6, color="0.25")


def guardar(fig, nombre, dpi=None):
    fig.savefig(OUT / nombre, bbox_inches="tight", pad_inches=0.03, **({"dpi": dpi} if dpi else {}))
    plt.close(fig); print("ok", nombre, flush=True)


def budyko(p, etp):
    f = etp / p
    return p * np.sqrt(f * np.tanh(1 / f) * (1 - np.exp(-f)))


# ============================================================================= paneles de mapas
P = {"IDEAM (kriging)": leer(RES / "04_precipitacion_interpolada" / "P_anual_kriging_90m_3116.tif")[0],
     "CHIRPS v2.0": leer(RES / "11_mapas_productos" / "P_CHIRPS_1981_2010_90m_3116.tif")[0],
     "ERA5-Land": leer(RES / "11_mapas_productos" / "P_ERA5_Land_1981_2010_90m_3116.tif")[0],
     "ERA5": leer(RES / "11_mapas_productos" / "P_ERA5_1981_2010_90m_3116.tif")[0]}
ETP = leer(RES / "08_etp_etr" / "ETP_anual_hargreaves_90m_3116.tif")[0]


def panel4(campos, esc_de, etiqueta_de, nombre, sub=None, lev_de=lambda t: None, caja_de=lambda t, a: None):
    fig, axs = plt.subplots(1, 4, figsize=(W, 3.05), gridspec_kw=dict(wspace=0.75))
    for i, (ax, (tit, a)) in enumerate(zip(axs, campos.items())):
        esc = esc_de(tit)
        mapa(ax, a, esc["cmap"], esc["norm"], tit + (f"\n{sub(tit, a)}" if sub else ""), lev=lev_de(tit), caja=caja_de(tit, a), rotulos=False)
        if "ticks" in esc and esc.get("barra", True):
            barra(fig, esc, a[mask], ax, etiqueta_de(tit))
        else:
            cb = fig.colorbar(plt.cm.ScalarMappable(norm=esc["norm"], cmap=esc["cmap"]), ax=ax, shrink=0.62, pad=0.04, aspect=28,
                              ticks=esc.get("marcas"))
            cb.ax.tick_params(labelsize=6, length=2, pad=1.5); cb.set_label(etiqueta_de(tit), fontsize=6.5, labelpad=2)
        ax.title.set_fontsize(7.5); ax.set_xlabel("Este (km)", fontsize=6.5, labelpad=1)
        if i:
            ax.set_yticklabels([])
    axs[0].set_ylabel("Norte (km)", fontsize=6.5, labelpad=1)
    norte(axs[-1]); pie_crs(fig, -0.02)
    guardar(fig, nombre)


media = lambda a: np.nanmean(a[mask])  # noqa: E731
panel4(P, lambda t: E.P, lambda t: "P (mm/año)", "panel_P_productos.png",
       sub=lambda t, a: f"{media(a):,.0f} mm/año".replace(",", " "),
       caja_de=lambda t, a: f"{np.nanmin(a[mask]):,.0f}–{np.nanmax(a[mask]):,.0f} mm".replace(",", " "))

G = {k: leer(RES / "08_etp_etr" / f"{k}_90m_3116.tif")[0] for k in ["ETP_anual_hargreaves", "indice_aridez_phi", "ETR_anual_budyko",
                                                                     "R_P_menos_ETR"]}
PHI_B = [0.2, 0.4, 0.5, 0.6, 0.75, 1.0, 1.25, 1.5, 2.0]
_cphi = plt.get_cmap("RdYlBu_r", len(PHI_B) - 1)
ESC4 = {"ETP (Hargreaves)": E.ETP, "Índice de aridez φ": dict(cmap=_cphi, norm=BoundaryNorm(PHI_B, _cphi.N), marcas=[0.2, 0.5, 0.75, 1, 1.5, 2]),
        "ETR (Budyko)": E.ETR, "R = P − ETR": E.R}
UN4 = {"ETP (Hargreaves)": "ETP (mm/año)", "Índice de aridez φ": "φ = ETP / P", "ETR (Budyko)": "ETR (mm/año)", "R = P − ETR": "R (mm/año)"}
campos4 = dict(zip(ESC4, G.values()))
LEV4 = {"ETP (Hargreaves)": [1000, 1400, 1800], "Índice de aridez φ": [0.5, 1.0], "ETR (Budyko)": [800, 1100, 1400],
        "R = P − ETR": [500, 1000, 2000]}
panel4(campos4, lambda t: ESC4[t], lambda t: UN4[t], "panel_ETP_phi_ETR_R.png",
       sub=lambda t, a: f"media {media(a):.2f}" if "φ" in t else f"media {media(a):,.0f} mm/año".replace(",", " "),
       lev_de=lambda t: LEV4[t],
       caja_de=lambda t, a: (f"{np.nanmin(a[mask]):.2f}–{np.nanmax(a[mask]):.2f}" if "φ" in t
                             else f"{np.nanmin(a[mask]):,.0f}–{np.nanmax(a[mask]):,.0f} mm".replace(",", " ")))

R = {k: p - budyko(p, ETP) for k, p in P.items()}
panel4(R, lambda t: E.R, lambda t: "R (mm/año)", "panel_R_productos.png",
       sub=lambda t, a: f"R {media(a):,.0f} mm/año".replace(",", " "))

# razón producto / IDEAM
fig, axs = plt.subplots(1, 3, figsize=(W * 0.82, 3.6), gridspec_kw=dict(wspace=0.12))
nr = TwoSlopeNorm(vmin=0.5, vcenter=1.0, vmax=5.0)
for i, (ax, k) in enumerate(zip(axs, list(P)[1:])):
    a = P[k] / P["IDEAM (kriging)"]
    im = mapa(ax, a, "RdBu_r", nr, f"{k} / IDEAM\nrazón {media(a):.2f}")
    ax.set_xlabel("Este (km)", fontsize=6.5, labelpad=1)
    if i:
        ax.set_yticklabels([])
axs[0].set_ylabel("Norte (km)", fontsize=6.5, labelpad=1)
cb = fig.colorbar(im, ax=axs, shrink=0.62, pad=0.02, aspect=28, ticks=[0.5, 0.75, 1, 1.5, 2, 3, 4, 5])
cb.ax.tick_params(labelsize=6, length=2); cb.set_label("P producto / P IDEAM", fontsize=6.5)
norte(axs[-1]); escala_km(axs[0]); pie_crs(fig, -0.01)
guardar(fig, "panel_razon_IDEAM.png")

# temperatura (misma escala en los tres)
T = {k: leer(RES / "07_mapas_temperatura" / f"{k}_90m_3116.tif")[0] for k in ["Tmin", "Tmed", "Tmax"]}
tz = pd.read_csv(RES / "05_temperatura_elevacion" / "coeficientes_T_Z.csv", index_col=0)
fig, axs = plt.subplots(1, 3, figsize=(W, 4.3), gridspec_kw=dict(wspace=0.1))
NOMT = {"Tmin": "Temperatura mínima media", "Tmed": "Temperatura media", "Tmax": "Temperatura máxima media"}
for i, (ax, (k, a)) in enumerate(zip(axs, T.items())):
    mapa(ax, a, E.T_CMAP, plt.Normalize(E.T_VMIN, E.T_VMAX),
         f"{NOMT[k]}\n{k} = {tz.loc[k, 'T0']:.2f} − {tz.loc[k, 'alfa']:.5f}·Z\nR² = {tz.loc[k, 'R2']:.3f}", sombra=0.15,
         lev=np.arange(-4, 37, 4), fmt="%d",
         caja=f"Media de la cuenca: {media(a):.1f} °C\nRango: {np.nanmin(a[mask]):.1f} a {np.nanmax(a[mask]):.1f} °C".replace("-", "−"))
    if np.nanmin(a[mask]) < 0:
        ax.contour(XC, YC, np.where(mask, a, np.nan), levels=[0], colors="#08306b", linewidths=0.7, zorder=3)
    ax.title.set_fontsize(6); ax.set_xlabel("Este (km)", fontsize=6.5, labelpad=1)
    if i:
        ax.set_yticklabels([])
axs[0].set_ylabel("Norte (km)", fontsize=6.5, labelpad=1)
cb = fig.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(E.T_VMIN, E.T_VMAX), cmap=E.T_CMAP), ax=axs, shrink=0.62, pad=0.02,
                  aspect=28, extend="both")
cb.ax.tick_params(labelsize=6, length=2); cb.set_label("Temperatura (°C)", fontsize=6.5)
norte(axs[-1]); escala_km(axs[0]); pie_crs(fig, -0.01)
guardar(fig, "panel_temperatura.png")

# 12 meses
PM = leer(RES / "13_climatologia" / "P_mensual_kriging_90m_3116.tif", todas=True)[0]
fig, axs = plt.subplots(2, 6, figsize=(W, 5.6), gridspec_kw=dict(wspace=0.06, hspace=0.18))
for m, ax in enumerate(axs.flat):
    a = PM[m]
    mapa(ax, a, E.PM["cmap"], E.PM["norm"], f"{MES[m]}\n{media(a):.0f} mm", sombra=0.12); ax.title.set_fontsize(7.5)
    ax.set_xticks([]); ax.set_yticks([])
norte(axs[0, 5]); escala_km(axs[1, 0])
barra(fig, E.PM, [PM[k][mask] for k in range(12)], list(axs.flat), "Precipitación media mensual (mm)", shrink=0.55, pad=0.015, aspect=35)
fig.text(0.45, 0.09, "MAGNA-SIRGAS / Colombia Bogotá (EPSG:3116)", ha="center", fontsize=6, color="0.25")
guardar(fig, "panel_P_mensual.png", dpi=450)

# estacionalidad
F = 10
h, w = Z.shape[0] // F * F, Z.shape[1] // F * F
with np.errstate(all="ignore"):
    B = np.nanmean(PM[:, :h, :w].reshape(12, h // F, F, w // F, F), axis=(2, 4))
tot = B.sum(0); med = tot / 12
mes_max = np.where(np.isfinite(tot), np.argmax(np.nan_to_num(B, nan=-1), axis=0) + 1, np.nan)
SI = np.nansum(np.abs(B - med), axis=0) / tot
picos = ((B > np.roll(B, 1, 0)) & (B >= np.roll(B, -1, 0)) & (B > 1.1 * med)).sum(0).astype(float)
picos[~np.isfinite(tot)] = np.nan; SI[~np.isfinite(tot)] = np.nan
ext2 = (aff.c, aff.c + aff.a * w, aff.f + aff.e * h, aff.f)
fig, axs = plt.subplots(1, 3, figsize=(W, 3.6), gridspec_kw=dict(wspace=0.7))
specs = [(mes_max, ListedColormap(plt.get_cmap("twilight_shifted")(np.linspace(0, 1, 12))), plt.Normalize(0.5, 12.5), "Mes de máxima lluvia",
          dict(ticks=range(1, 13), lab=MES, et="")),
         (picos, ListedColormap(["#fdae6b", "#3182bd", "#08306b"]), plt.Normalize(0.5, 3.5), "Número de picos del ciclo",
          dict(ticks=[1, 2, 3], lab=["1 unimodal", "2 bimodal", "3"], et="")),
         (SI, plt.get_cmap("YlOrBr"), plt.Normalize(0.1, 0.45), "Índice de estacionalidad SI", dict(ticks=None, lab=None, et="SI"))]
for i, (ax, (a, cm, nm, tit, cbk)) in enumerate(zip(axs, specs)):
    im = ax.imshow(a, cmap=cm, norm=nm, extent=ext2, interpolation="nearest")
    rio.plot(ax=ax, color="#08306b", lw=0.6); cuenca.boundary.plot(ax=ax, color="black", lw=0.6)
    ax.set_xlim(minx - 8000, maxx + 8000); ax.set_ylim(miny - 8000, maxy + 8000); ax.set_aspect("equal")
    ax.set_xticks([700000, 800000]); ax.set_yticks([800000, 1000000, 1200000])
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:.0f}")); ax.yaxis.set_major_formatter(
        FuncFormatter(lambda v, _: f"{v / 1000:.0f}"))
    plt.setp(ax.get_yticklabels(), rotation=90, va="center"); ax.tick_params(length=2, pad=1.5); ax.grid(color="0.6", lw=0.25, ls=":")
    ax.set_title(tit, pad=3, fontsize=7.5); ax.set_xlabel("Este (km)", fontsize=6.5, labelpad=1)
    if i:
        ax.set_yticklabels([])
    else:
        ax.set_ylabel("Norte (km)", fontsize=6.5, labelpad=1)
    cb = fig.colorbar(im, ax=ax, shrink=0.62, pad=0.04, aspect=28, ticks=cbk["ticks"])
    if cbk["lab"]:
        cb.ax.set_yticklabels(cbk["lab"])
    cb.ax.tick_params(labelsize=6, length=2); cb.set_label(cbk["et"], fontsize=6.5)
norte(axs[-1]); pie_crs(fig, -0.01)
guardar(fig, "estacionalidad.png")

# ============================================================================= mapas individuales (8 cm de ancho)
cv = pd.read_csv(RES / "04_precipitacion_interpolada" / "validacion_cruzada_estaciones.csv")
Pk = P["IDEAM (kriging)"]
fig, ax = plt.subplots(figsize=(3.6, 7.0))
mapa(ax, Pk, E.P["cmap"], E.P["norm"], "Precipitación media anual 1981–2010\nkriging ordinario · media 1985 mm/año")
cs = ax.contour(XC, YC, d(Pk), levels=np.arange(1000, 3501, 500), colors="0.15", linewidths=0.35, zorder=3)
ax.clabel(cs, fmt="%d", fontsize=5)
for dentro, mk in [(True, "o"), (False, "^")]:
    s = cv[cv.dentro == dentro]
    ax.scatter(s.x, s.y, s=4, marker=mk, c="white", edgecolors="black", linewidths=0.3, zorder=7)
barra(fig, E.P, Pk[mask], ax, "P (mm/año)", shrink=0.45, pad=0.03)
ax.set_xlabel("Este (km)", fontsize=6.5); ax.set_ylabel("Norte (km)", fontsize=6.5)
ax.legend(handles=[Line2D([], [], ls="", marker="o", ms=3, mfc="white", mec="black", mew=0.4, label="Estación IDEAM (259)"),
                   Line2D([], [], ls="", marker="^", ms=3, mfc="white", mec="black", mew=0.4, label="Vecindario, zona 26 (7)"),
                   Line2D([], [], color="0.15", lw=0.4, label="Isoyetas cada 500 mm"),
                   Line2D([], [], color="#08306b", lw=0.8, label="Río Cauca"),
                   Line2D([], [], ls="", marker="^", ms=4, mfc="white", mec="black", label="Punto de cierre")],
          loc="upper left", fontsize=5.5, framealpha=0.9, borderpad=0.4, handlelength=1.4)
norte(ax, 0.88, 0.62); escala_km(ax); pie_crs(fig, 0.0)
guardar(fig, "mapa_P_anual.png")

ep = gpd.read_file(RES / "03_estaciones_precipitacion" / "estaciones_precipitacion.gpkg")
fig, ax = plt.subplots(figsize=(3.6, 7.0))
ax.imshow(HS, cmap="gray", vmin=0, vmax=1.3, extent=EXT, zorder=1)
gpd.GeoSeries([cuenca.geometry[0].buffer(20000)], crs=cuenca.crs).boundary.plot(ax=ax, color="0.4", lw=0.5, ls="--", zorder=2)
rio.plot(ax=ax, color="#08306b", lw=0.6, zorder=3); cuenca.boundary.plot(ax=ax, color="black", lw=0.6, zorder=4)
ok = ep[ep.completa]
for dentro, mk in [(False, "^"), (True, "o")]:
    s = ok[ok.dentro == dentro]
    ax.scatter(s.geometry.x, s.geometry.y, c=s.ANUAL, cmap=E.P["cmap"], norm=E.P["norm"], marker=mk, s=7, edgecolors="black",
               linewidths=0.25, zorder=6)
inc = ep[~ep.completa]
ax.scatter(inc.geometry.x, inc.geometry.y, marker="x", c="red", s=6, linewidths=0.5, zorder=6)
ax.set_xlim(minx - 25000, maxx + 25000); ax.set_ylim(miny - 25000, maxy + 25000); ax.set_aspect("equal")
ax.set_xticks([700000, 800000]); ax.set_yticks([800000, 1000000, 1200000])
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:.0f}")); ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:.0f}"))
plt.setp(ax.get_yticklabels(), rotation=90, va="center"); ax.tick_params(length=2, pad=1.5); ax.grid(color="0.6", lw=0.25, ls=":")
ax.set_title("Estaciones de precipitación IDEAM\n(promedios 1981–2010)", pad=3)
barra(fig, E.P, ok.ANUAL, ax, "P media anual (mm/año)", shrink=0.45, pad=0.03)
ax.set_xlabel("Este (km)", fontsize=6.5); ax.set_ylabel("Norte (km)", fontsize=6.5)
ax.legend(handles=[Line2D([], [], ls="", marker="o", ms=3, mfc="0.8", mec="black", mew=0.3, label=f"Dentro de la cuenca ({int((ok.dentro).sum())})"),
                   Line2D([], [], ls="", marker="^", ms=3, mfc="0.8", mec="black", mew=0.3, label=f"Vecindario ≤ 20 km ({int((~ok.dentro).sum())})"),
                   Line2D([], [], ls="", marker="x", ms=3, color="red", label=f"Serie incompleta ({len(inc)})"),
                   Line2D([], [], color="0.4", lw=0.5, ls="--", label="Límite del vecindario"),
                   Line2D([], [], color="black", lw=0.6, label="Límite de la cuenca")],
          loc="upper left", fontsize=5.5, framealpha=0.9, borderpad=0.4, handlelength=1.4)
norte(ax, 0.88, 0.62); pie_crs(fig, 0.0)
guardar(fig, "mapa_estaciones_P.png")

# estaciones de caudal y áreas de drenaje
ar = gpd.read_file(RES / "06_caudales" / "subcuencas_estaciones.gpkg", layer="areas_drenaje")
es = gpd.read_file(RES / "06_caudales" / "subcuencas_estaciones.gpkg", layer="estaciones")
est = pd.ExcelFile(RES / "06_caudales" / "Punto8_caudales_estaciones.xlsx").parse("Estaciones")
est = est.sort_values("Área de drenaje (km²)").reset_index(drop=True)
fig, ax = plt.subplots(figsize=(4.6, 7.0))
ax.imshow(HS, cmap="gray", vmin=0, vmax=1.3, extent=EXT, zorder=1)
cm = plt.get_cmap("viridis_r", len(est))
codcol = next(c for c in ar.columns if "cod" in c.lower())
for i, r in est.iloc[::-1].iterrows():                 # de la mayor a la menor: las pequeñas quedan visibles encima
    gg = ar[ar[codcol].astype(str) == str(r["Código"])]
    if len(gg):
        gg.plot(ax=ax, color=cm(i), alpha=0.35, edgecolor="white", linewidth=0.5, zorder=2)
rio.plot(ax=ax, color="#08306b", lw=0.7, zorder=3); cuenca.boundary.plot(ax=ax, color="black", lw=0.6, zorder=4)
for i, r in est.iterrows():
    ax.scatter(r["Este 3116 (m)"], r["Norte 3116 (m)"], s=26, color=cm(i), edgecolors="black", linewidths=0.4, zorder=6)
    ax.text(r["Este 3116 (m)"] + 9000, r["Norte 3116 (m)"], str(i + 1), fontsize=6, fontweight="bold", va="center", zorder=7,
            bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85))
cierre.plot(ax=ax, color="red", marker="^", markersize=20, edgecolor="black", linewidth=0.4, zorder=8)
ax.set_xlim(minx - 12000, maxx + 60000); ax.set_ylim(miny - 10000, maxy + 30000); ax.set_aspect("equal")
ax.set_xticks([700000, 800000, 900000]); ax.set_yticks([800000, 1000000, 1200000])
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:.0f}")); ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:.0f}"))
plt.setp(ax.get_yticklabels(), rotation=90, va="center"); ax.tick_params(length=2, pad=1.5); ax.grid(color="0.6", lw=0.25, ls=":")
ax.set_title("Estaciones de caudal validadas y áreas de drenaje", pad=3)
ax.set_xlabel("Este (km)", fontsize=6.5); ax.set_ylabel("Norte (km)", fontsize=6.5)
ax.legend(handles=[Line2D([], [], ls="", marker="o", ms=4, mfc=cm(i), mec="black", mew=0.3,
                          label=f"{i + 1}. {r['Estación']} ({r['Área de drenaje (km²)']:,.0f} km²)".replace(",", " "))
                   for i, r in est.iterrows()] + [Line2D([], [], ls="", marker="^", ms=4, mfc="red", mec="black", label="Presa Hidroituango")],
          loc="lower right", fontsize=5.5, framealpha=0.92, borderpad=0.4, handlelength=1)
norte(ax, 0.9, 0.95); escala_km(ax); pie_crs(fig, 0.0)
guardar(fig, "mapa_estaciones_Q.png")

# ============================================================================= gráficas
# variograma y validación cruzada
xy, z = cv[["x", "y"]].to_numpy(), cv["P observada"].to_numpy()
hh, sv = pdist(xy), 0.5 * pdist(z[:, None], "sqeuclidean")
edges = np.linspace(0, 100_000, 21); idx = np.digitize(hh, edges) - 1; okb = (idx >= 0) & (idx < 20)
hb = np.array([hh[okb & (idx == k)].mean() for k in range(20)]); gb = np.array([sv[okb & (idx == k)].mean() for k in range(20)])
nb = np.array([(okb & (idx == k)).sum() for k in range(20)])
MOD = {"esférico": lambda h, c0, c, a: np.where(h < a, c0 + c * (1.5 * h / a - 0.5 * (h / a) ** 3), c0 + c),
       "exponencial": lambda h, c0, c, a: c0 + c * (1 - np.exp(-3 * h / a)),
       "gaussiano (elegido)": lambda h, c0, c, a: c0 + c * (1 - np.exp(-3 * (h / a) ** 2))}
fig, (a1, a2) = plt.subplots(1, 2, figsize=(W, 2.7), gridspec_kw=dict(wspace=0.32))
a1.scatter(hb / 1000, gb / 1000, s=10, color="black", zorder=3, label="Experimental")
hx = np.linspace(0, 100_000, 300)
for (nom, f), col in zip(MOD.items(), ["#2a78d6", "#eb6834", "#1baf7a"]):
    p, _ = curve_fit(f, hb, gb, p0=[0.1 * z.var(), z.var(), 60_000], sigma=gb / np.sqrt(nb),
                     bounds=([0, 0, 5_000], [2 * z.var(), 3 * z.var(), 400_000]), maxfev=20_000)
    a1.plot(hx / 1000, f(hx, *p) / 1000, color=col, lw=1.6 if "elegido" in nom else 0.9, label=nom)
a1.set_xlabel("Distancia (km)"); a1.set_ylabel("γ(h) (× 1000 mm²)"); a1.set_title("a) Variograma de la P media anual")
a1.legend(loc="lower right", frameon=False); a1.grid(alpha=0.3, lw=0.4); a1.set_xlim(0, 100); a1.set_ylim(0)
m = 4600
a2.plot([0, m], [0, m], color="0.3", lw=0.6, ls="--")
a2.scatter(cv["P observada"], cv["P estimada IDW p=1.5"], s=5, color="#2a78d6", alpha=0.6, label="IDW p = 1.5 (RMSE 364 mm)")
a2.scatter(cv["P observada"], cv["P estimada Kriging ordinario (gaussiano)"], s=5, color="#eb6834", alpha=0.6,
           label="Kriging gaussiano (RMSE 363 mm)")
a2.set_xlim(0, m); a2.set_ylim(0, m); a2.set_aspect("equal")
a2.xaxis.set_major_formatter(MILES); a2.yaxis.set_major_formatter(MILES)
a2.set_xlabel("P observada (mm/año)"); a2.set_ylabel("P estimada sin la estación (mm/año)"); a2.set_title("b) Validación cruzada")
a2.legend(loc="upper left", frameon=False, markerscale=1.5); a2.grid(alpha=0.3, lw=0.4)
guardar(fig, "variograma_validacion.png")

# T–Z
dat = pd.ExcelFile(RES / "05_temperatura_elevacion" / "Punto4_temperatura_elevacion.xlsx").parse("Datos_anuales")
fig, axs = plt.subplots(1, 3, figsize=(W, 2.5), sharey=True, gridspec_kw=dict(wspace=0.08))
for ax, (k, col, nom) in zip(axs, [("Tmax", "#d7301f", "Temperatura máxima"), ("Tmed", "#1a9850", "Temperatura media"),
                                    ("Tmin", "#2c7bb6", "Temperatura mínima")]):
    zz, tt = dat["Z (m)"], dat[f"{k} (°C)"]
    # residuos estudentizados internos de la regresión (el Excel los tiene como fórmulas sin valor guardado)
    zv, tv = zz.to_numpy(float), tt.to_numpy(float)
    b1, b0 = np.polyfit(zv, tv, 1); e = tv - (b0 + b1 * zv)
    hlev = 1 / len(zv) + (zv - zv.mean()) ** 2 / ((zv - zv.mean()) ** 2).sum()
    rst = e / (np.sqrt((e ** 2).sum() / (len(zv) - 2)) * np.sqrt(1 - hlev))
    at = pd.Series(np.abs(rst) > 2.5, index=zz.index)
    ax.scatter(zz[~at], tt[~at], s=8, color=col, edgecolors="white", linewidths=0.3, zorder=3, label="Estaciones")
    ax.scatter(zz[at], tt[at], s=16, facecolors="white", edgecolors="black", linewidths=0.9, zorder=4, label="Atípica (|r*| > 2.5)")
    for zi, ti, ni in zip(zz[at], tt[at], dat["Nombre"][at]):
        ax.annotate(str(ni).title(), (zi, ti), xytext=(3, 4), textcoords="offset points", fontsize=5.5, ha="right" if zi > 3800 else "left")
    zx = np.array([0, 4500]); r = tz.loc[k]
    ax.plot(zx, r["T0"] - r["alfa"] * zx, color="black", lw=0.8)
    ax.text(0.97, 0.96, f"{k} = {r['T0']:.2f} − {r['alfa']:.5f}·Z\nα = {r['alfa_km']:.2f} °C/km\nR² = {r['R2']:.3f} · n = {r['n']:.0f}",
            transform=ax.transAxes, ha="right", va="top", fontsize=6, bbox=dict(fc="white", ec="0.7", lw=0.4, pad=2))
    ax.set_title(nom); ax.set_xlabel("Elevación Z (m)"); ax.grid(alpha=0.3, lw=0.4); ax.set_xlim(0, 4500); ax.set_ylim(0, 37)
    ax.xaxis.set_major_formatter(MILES)
axs[0].set_ylabel("Temperatura (°C)"); axs[0].legend(loc="lower left", frameon=False)
guardar(fig, "diagramas_T_Z.png")

# ETP mensual y Ra
em = pd.read_csv(RES / "08_etp_etr" / "ETP_mensual_cuenca.csv")
fig, ax = plt.subplots(figsize=(W * 0.8, 2.4))
ax.bar(MES, em["ETP_m media cuenca (mm)"], color="#fd8d3c", width=0.7, label="ETP mensual (mm)")
for i, v in enumerate(em["ETP_m media cuenca (mm)"]):
    ax.text(i, v + 1.5, f"{v:.0f}", ha="center", fontsize=5.5)
ax.set_ylabel("ETP media de la cuenca (mm/mes)"); ax.set_ylim(0, 145); ax.grid(axis="y", alpha=0.3, lw=0.4)
a2 = ax.twinx()
a2.plot(MES, em["Ra media (MJ/m²/d)"], color="black", marker="o", ms=3, lw=1, label="Ra")
a2.set_ylabel("Ra (MJ m⁻² día⁻¹)"); a2.set_ylim(33, 38)
ax.legend(handles=[Patch(color="#fd8d3c", label="ETP Hargreaves-Samani"), Line2D([], [], color="black", marker="o", ms=3, label="Radiación extraterrestre Ra")],
          loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2, frameon=False)
ax.set_title("ETP mensual y radiación extraterrestre, media de la cuenca")
guardar(fig, "ETP_mensual.png")

# espacio de Budyko (muestra de celdas)
rng = np.random.default_rng(1)
phi, etr = G["indice_aridez_phi"][mask], G["ETR_anual_budyko"][mask] / P["IDEAM (kriging)"][mask]
zc = Z[mask]; sel = rng.choice(len(phi), 20000, replace=False)
fig, ax = plt.subplots(figsize=(3.9, 3.0))
sc = ax.scatter(phi[sel], etr[sel], s=1.5, c=zc[sel], cmap="terrain", alpha=0.5, rasterized=True)
fx = np.linspace(0.05, 2, 300)
ax.plot(fx, np.sqrt(fx * np.tanh(1 / fx) * (1 - np.exp(-fx))), color="black", lw=1.1, label="Budyko (1974)")
ax.plot([0, 1, 2], [0, 1, 1], color="0.4", lw=0.7, ls="--", label="Límites de energía y de agua")
ax.scatter([0.71], [0.547], marker="*", s=70, color="#d7301f", edgecolors="black", linewidths=0.4, zorder=5, label="Cuenca (φ = 0.71)")
ax.set_xlim(0, 2); ax.set_ylim(0, 1.05); ax.set_xlabel("Índice de aridez φ = ETP / P"); ax.set_ylabel("ETR / P")
ax.grid(alpha=0.3, lw=0.4); ax.legend(loc="lower right", frameon=True, framealpha=0.9)
cb = fig.colorbar(sc, ax=ax, pad=0.02, aspect=25); cb.set_label("Elevación (m)", fontsize=6.5); cb.ax.tick_params(labelsize=6)
cb.solids.set(alpha=1)
ax.set_title("Celdas de la cuenca en el espacio de Budyko")
guardar(fig, "curva_budyko.png")

# disponibilidad de caudales
qm = pd.read_csv(ROOT / "datos" / "caudales_ideam" / "Q_mensual_completa.csv", index_col=0, parse_dates=True)
dsp = pd.read_csv(ROOT / "datos" / "caudales_ideam" / "disponibilidad_caudales.csv", dtype={"codigo": str})
dsp = dsp[dsp.codigo.isin(qm.columns)].copy()
dsp["orden"] = dsp.area_km2.rank(); dsp = dsp.sort_values("area_km2")
anos = np.arange(1960, 2026)
M = np.array([[qm.loc[str(a), c].notna().sum() if str(a) in qm.index.year.astype(str) else 0 for a in anos] for c in dsp.codigo])
fig, ax = plt.subplots(figsize=(W, 2.9))
cmg = ListedColormap(["#f0f0f0"] + list(plt.get_cmap("Greens")(np.linspace(0.3, 0.6, 11))) + ["#1b7837"])
ax.imshow(M, aspect="auto", cmap=cmg, vmin=-0.5, vmax=12.5, extent=(anos[0] - 0.5, anos[-1] + 0.5, len(dsp) - 0.5, -0.5), interpolation="nearest")
ax.axvspan(1980.5, 2010.5, fc="none", ec="#d7301f", lw=1)
ax.text(1995.5, -0.9, "1981–2010", color="#d7301f", ha="center", fontsize=6.5, fontweight="bold")
ax.set_yticks(range(len(dsp)))
ax.set_yticklabels([f"{r.estacion.title()} · {r._10:.0f} años" + ("" if r._14 else " (no cumple)") for r in dsp.itertuples()], fontsize=6)
for t, r in zip(ax.get_yticklabels(), dsp.itertuples()):
    t.set_color("black" if r._14 else "#d7301f")
ax.set_xlabel("Año"); ax.set_xlim(anos[0] - 0.5, anos[-1] + 0.5)
ax.set_title("Meses válidos (≥ 80 % de días con dato) por año; años completos en 1981–2010", pad=12)
cb = fig.colorbar(plt.cm.ScalarMappable(cmap=cmg, norm=plt.Normalize(-0.5, 12.5)), ax=ax, pad=0.01, aspect=20, ticks=[0, 3, 6, 9, 12])
cb.ax.tick_params(labelsize=6); cb.set_label("Meses válidos", fontsize=6.5)
guardar(fig, "disponibilidad_caudales.png")

# balance: Q estimado frente a observado
bal = pd.read_csv(RES / "09_balance" / "balance_subcuencas.csv", dtype={"codigo": str})
fig, ax = plt.subplots(figsize=(3.9, 3.6))
mx = 1250
ax.fill_between([0, mx], [0, 0.9 * mx], [0, 1.1 * mx], color="0.88", label="±10 %")
ax.plot([0, mx], [0, mx], color="black", lw=0.6)
ax.scatter(bal["Q obs (m³/s)"], bal["Q est"], s=16, color="#2a78d6", edgecolors="black", linewidths=0.4, zorder=3,
           label="Q observado (años completos)")
ax.scatter(bal["Q obs rellenado (m³/s)"], bal["Q est"], s=12, marker="s", facecolors="none", edgecolors="#d7301f", linewidths=0.6,
           zorder=3, label="Q observado (serie rellenada)")
for r in bal.itertuples():
    nm = "Hidroituango" if r.codigo == "HIDRO" else r.estacion
    izq = nm in ("Bolombolo", "Irra", "Hidroituango", "Puente Iglesias")
    x = (min(r._8, r._9) - 35) if izq else (max(r._8, r._9) + 35)
    ax.text(x, r._11, f"{nm} ({r._12:+.0f} %)".replace("-", "−"), fontsize=5.5, ha="right" if izq else "left", va="center")
ax.set_xlim(0, mx); ax.set_ylim(0, mx); ax.set_aspect("equal")
ax.set_xlabel("Q observado (m³/s)"); ax.set_ylabel("Q estimado = (P − ETR)·A (m³/s)")
ax.xaxis.set_major_formatter(MILES); ax.yaxis.set_major_formatter(MILES)
ax.legend(loc="upper left", frameon=False); ax.grid(alpha=0.3, lw=0.4)
ax.set_title("Balance de largo plazo 1981–2010")
guardar(fig, "balance_Q.png")

# ciclo anual de la cuenca
cic = pd.read_csv(RES / "13_climatologia" / "ciclo_anual.csv")
pm = cic["P media cuenca (mm)"].to_numpy(); mu = pm.mean()
fig, ax = plt.subplots(figsize=(W * 0.8, 2.4))
cols = ["#2c7bb6" if v > mu + 1 else ("#bdbdbd" if abs(v - mu) <= 1 else "#fdae61") for v in pm]
ax.bar(MES, pm, color=cols, width=0.7)
for i, v in enumerate(pm):
    ax.text(i, v + 3, f"{v:.0f}", ha="center", fontsize=5.5)
ax.plot(MES, cic["P media estaciones dentro (mm)"], color="black", marker="o", ms=2.5, lw=0.8, label="Media de las estaciones")
ax.axhline(mu, color="0.3", ls="--", lw=0.7)
ax.text(11.45, mu + 4, f"media {mu:.0f} mm", ha="right", fontsize=5.5, color="0.3")
ax.set_ylabel("Precipitación media (mm/mes)"); ax.set_ylim(0, 270); ax.grid(axis="y", alpha=0.3, lw=0.4)
ax.legend(handles=[Patch(color="#2c7bb6", label="Mes húmedo"), Patch(color="#fdae61", label="Mes seco"), Patch(color="#bdbdbd", label="Límite"),
                   Line2D([], [], color="black", marker="o", ms=2.5, lw=0.8, label="Media de las estaciones")],
          loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=4, frameon=False)
ax.set_title("Ciclo anual de la precipitación media de la cuenca (kriging mensual)", pad=4)
guardar(fig, "ciclo_anual.png")

# ciclos por producto
cp = pd.read_csv(RES / "14_ciclo_productos" / "ciclos_productos.csv"); cp = cp[cp["región"] == "Cuenca"]
COL = {"IDEAM": "black", "CHIRPS": "#2a78d6", "ERA5-Land": "#eb6834", "ERA5": "#1baf7a"}
fig, (a1, a2) = plt.subplots(1, 2, figsize=(W, 2.5), gridspec_kw=dict(wspace=0.28))
for k, c in COL.items():
    v = cp[k].to_numpy()
    a1.plot(range(12), v, color=c, marker="o", ms=2.5, lw=1, label=k)
    a2.plot(range(12), 100 * v / v.sum(), color=c, marker="o", ms=2.5, lw=1, label=k)
for a, t, yl in [(a1, "a) Ciclo anual", "Precipitación (mm/mes)"), (a2, "b) Ciclo normalizado", "% del total anual")]:
    a.set_xticks(range(12)); a.set_xticklabels(MES1); a.set_title(t); a.set_ylabel(yl); a.grid(alpha=0.3, lw=0.4)
a1.set_ylim(0); a1.legend(loc="center right", frameon=False, ncol=1)
guardar(fig, "ciclos_productos.png")

# diagrama de Taylor
mc = pd.read_csv(RES / "14_ciclo_productos" / "metricas_ciclo.csv", index_col=0)
fig = plt.figure(figsize=(3.4, 3.5))
ax = fig.add_subplot(111, projection="polar")
ax.set_thetamin(0); ax.set_thetamax(90); ax.set_rlim(0, 2.0)
for rr in [0.5, 1.0, 1.5]:                                       # RMSE centrado normalizado respecto a la referencia (1, 0)
    t = np.linspace(0, np.pi, 200); x, y = 1 + rr * np.cos(t), rr * np.sin(t)
    ax.plot(np.arctan2(y, x), np.hypot(x, y), color="0.6", lw=0.5, ls=":")
ax.plot(np.linspace(0, np.pi / 2, 100), np.ones(100), color="0.3", lw=0.6, ls="--")
ax.scatter([0], [1], marker="*", s=60, color="black", zorder=5, label="IDEAM (referencia)")
for k, c in COL.items():
    if k == "IDEAM":
        continue
    r = mc.loc[k]
    ax.scatter(np.arccos(r["r"]), r["σ normalizada"], s=28, color=c, edgecolors="black", linewidths=0.4, zorder=5,
               label=f"{k} (r = {r['r']:.2f})")
cc = [0.2, 0.4, 0.6, 0.8, 0.9, 0.95, 0.99]
ax.set_thetagrids(np.degrees(np.arccos(cc)), [str(x) for x in cc], fontsize=6)
ax.tick_params(axis="y", labelsize=6)
ax.text(np.radians(52), 2.28, "Correlación r", ha="center", va="center", fontsize=6.5, rotation=-38)
ax.text(0.5, -0.1, "Desviación estándar normalizada σ", transform=ax.transAxes, ha="center", fontsize=6.5)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=2, fontsize=6, frameon=False)
guardar(fig, "taylor.png")
print("listo:", OUT)
