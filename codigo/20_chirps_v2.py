"""
Sensibilidad a la versión de CHIRPS: v2.0 (Funk et al., 2015; IRI Data Library; producto principal de los puntos 10-14)
frente a v3.0 (Drive del curso). Mismos procedimientos de los puntos 11, 12 y 14:
  · P media anual 1981-2010 → vecino más cercano a la grilla de 90 m → media de la cuenca y correlación espacial con IDEAM.
  · Balance P − ETR (Budyko celda a celda con la ETP de Hargreaves) en las 10 áreas de drenaje y en el cierre.
  · Ciclo anual de la cuenca: sesgo, RMSE y r frente al IDEAM (n = 12).

Insumo: PRECIPITACION_COLOMBIA_CHIRPS_v2/CHIRPS_v2p0_mensual_cuenca_1981_2010.nc
  (iridl.ldeo.columbia.edu SOURCES/.UCSB/.CHIRPS/.v2p0/.monthly/.global/.precipitation, X −77.3…−75.0, Y 1.8…7.5, 1981-2010)
Salidas: trabajo1/resultados/12_balance_productos/chirps_v2/
"""
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import xarray as xr
from matplotlib.colors import BoundaryNorm, TwoSlopeNorm
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "trabajo1" / "resultados"
OUT = RES / "12_balance_productos" / "chirps_v2"
OUT.mkdir(parents=True, exist_ok=True)
NC = ROOT / "PRECIPITACION_COLOMBIA_CHIRPS_v2" / "CHIRPS_v2p0_mensual_cuenca_1981_2010.nc"
SEG = 365.25 * 86400
MES3 = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def leer(p, banda=None):
    with rasterio.open(p) as s:
        a = (s.read() if banda == "todas" else s.read(1)).astype("float64"); a[a == s.nodata] = np.nan
        return a, s.transform, s.profile


DEM, aff, prof = leer(RES / "01_delimitacion" / "dem_cuenca_90m_3116.tif")
mask = np.isfinite(DEM); shape = DEM.shape
ETP = leer(RES / "08_etp_etr" / "ETP_anual_hargreaves_90m_3116.tif")[0]
P_ide = leer(RES / "04_precipitacion_interpolada" / "P_anual_kriging_90m_3116.tif")[0]
ide_m = leer(RES / "13_climatologia" / "P_mensual_kriging_90m_3116.tif", "todas")[0]

# ----------------------------------------------------------------------------- climatología mensual en la grilla de 90 m
import sys  # noqa: E402
sys.path.insert(0, str(Path(__file__).parent))
from productos import abrir  # noqa: E402
import escalas as E  # noqa: E402


def clim_grilla(nombre):
    """Media 1981-2010 de cada mes del producto, llevada por vecino más cercano a la grilla de 90 m (12 × fila × col)."""
    p = abrir(nombre).precip.sel(time=slice("1981-01-01", "2010-12-31"))
    assert p.sizes["time"] == 360
    clim = p.groupby("time.month").mean("time")
    if clim.lat[0] < clim.lat[-1]:
        clim = clim.isel(lat=slice(None, None, -1))
    lats, lons = clim.lat.values, clim.lon.values
    dx, dy = abs(lons[1] - lons[0]), abs(lats[1] - lats[0])
    tr = from_origin(lons[0] - dx / 2, lats[0] + dy / 2, dx, dy)
    out = []
    for m in range(12):
        dst = np.full(shape, np.nan)
        reproject(clim.isel(month=m).values.astype("float64"), dst, src_transform=tr, src_crs="EPSG:4326", dst_transform=aff,
                  dst_crs="EPSG:3116", resampling=Resampling.nearest, src_nodata=np.nan, dst_nodata=np.nan)
        dst[~mask] = np.nan
        out.append(dst)
    return np.stack(out)


v2_m, v3_m = clim_grilla("CHIRPS"), clim_grilla("CHIRPS v3.0")
P_v2, P_v3 = v2_m.sum(0), v3_m.sum(0)
prof.update(dtype="float32", nodata=-9999, compress="deflate")
with rasterio.open(OUT / "P_CHIRPS_v2_1981_2010_90m_3116.tif", "w", **prof) as d:
    d.write(np.where(np.isnan(P_v2), -9999, P_v2).astype("float32"), 1)


def budyko(p, etp):
    f = etp / p
    return p * np.sqrt(f * np.tanh(1 / f) * (1 - np.exp(-f)))


# ----------------------------------------------------------------------------- comparación de P (punto 11)
ok = mask & np.isfinite(P_ide)
comp = {}
for nom, P in {"CHIRPS v3.0": P_v3, "CHIRPS v2.0": P_v2}.items():
    comp[nom] = {"P media cuenca (mm/año)": np.nanmean(P[ok]), "Diferencia con IDEAM (%)": 100 * (np.nanmean(P[ok]) / P_ide[ok].mean() - 1),
                 "Correlación espacial con IDEAM": np.corrcoef(P[ok], P_ide[ok])[0, 1]}

# ----------------------------------------------------------------------------- balance (punto 12)
b9 = pd.read_csv(RES / "09_balance" / "balance_subcuencas.csv", dtype={"codigo": str})
sub = gpd.read_file(RES / "06_caudales" / "subcuencas_estaciones.gpkg", layer="areas_drenaje")
geoms = {r.codigo: r.geometry for r in sub.itertuples()}
geoms["HIDRO"] = gpd.read_file(RES / "01_delimitacion" / "cuenca_cauca_hidroituango.gpkg", layer="cuenca").geometry[0]
ca = abs(aff.a * aff.e) / 1e6
filas = []
for r in b9.itertuples():
    m = ~geometry_mask([geoms[r.codigo]], out_shape=shape, transform=aff)
    for nom, P in {"IDEAM": P_ide, "CHIRPS v3.0": P_v3, "CHIRPS v2.0": P_v2}.items():
        etr = np.nanmean(budyko(P[m], ETP[m])); p = np.nanmean(P[m]); A = m.sum() * ca
        q = (p - etr) / 1000 * A * 1e6 / SEG
        filas.append({"codigo": r.codigo, "estacion": r.estacion, "producto": nom, "A": A, "P": p, "ETR": etr, "R": p - etr,
                      "Qest": q, "Qobs": r._8, "err": 100 * (q / r._8 - 1)})
bal = pd.DataFrame(filas)
bal.to_csv(OUT / "balance_chirps_v2_v3.csv", index=False, encoding="utf-8-sig")
est = bal[bal.codigo != "HIDRO"]
for nom in ["CHIRPS v3.0", "CHIRPS v2.0"]:
    e = est[est.producto == nom].err
    h = bal[(bal.codigo == "HIDRO") & (bal.producto == nom)].iloc[0]
    comp[nom].update({"ETR cuenca (mm/año)": h.ETR, "Q estimado cierre (mm/año)": h.R, "Error en el cierre (%)": h.err,
                      "Error abs. medio estaciones (%)": e.abs().mean(), "Sesgo medio estaciones (%)": e.mean(),
                      "Rango de error estaciones (%)": f"{e.min():+.0f} a {e.max():+.0f}"})

# ----------------------------------------------------------------------------- ciclo anual (punto 14)
cyc_ide = np.array([np.nanmean(ide_m[m][mask]) for m in range(12)])
cyc = {"IDEAM": cyc_ide, "CHIRPS v3.0": np.array([np.nanmean(v3_m[m][mask]) for m in range(12)]),
       "CHIRPS v2.0": np.array([np.nanmean(v2_m[m][mask]) for m in range(12)])}
for nom in ["CHIRPS v3.0", "CHIRPS v2.0"]:
    d = cyc[nom] - cyc_ide
    comp[nom].update({"Ciclo: sesgo (mm/mes)": d.mean(), "Ciclo: RMSE (mm/mes)": np.sqrt((d ** 2).mean()),
                      "Ciclo: r": np.corrcoef(cyc[nom], cyc_ide)[0, 1],
                      "Ciclo: meses de máximo": f"{MES3[1 + int(np.argmax(cyc[nom][1:7]))]}, {MES3[7 + int(np.argmax(cyc[nom][7:]))]}",
                      "Ciclo: mes más seco": MES3[int(np.argmin(cyc[nom]))]})
comp = pd.DataFrame(comp)
comp.to_csv(OUT / "comparacion_chirps_v2_v3.csv", encoding="utf-8-sig")
pd.DataFrame(cyc, index=MES3).round(1).to_csv(OUT / "ciclo_chirps_v2_v3.csv", encoding="utf-8-sig")
pd.set_option("display.width", 200)
print(comp.to_string())
print(bal.pivot(index="estacion", columns="producto", values="err").loc[b9.estacion].round(1).to_string())
print(pd.DataFrame(cyc, index=MES3).round(0).T.to_string())

# ----------------------------------------------------------------------------- figura: v3.0, v2.0 y su diferencia
cuenca = gpd.read_file(RES / "01_delimitacion" / "cuenca_cauca_hidroituango.gpkg", layer="cuenca")
rio = gpd.read_file(RES / "01_delimitacion" / "cuenca_cauca_hidroituango.gpkg", layer="rio_principal")
ext = (aff.c, aff.c + aff.a * shape[1], aff.f + aff.e * shape[0], aff.f)
minx, miny, maxx, maxy = cuenca.total_bounds
cm, nm = E.P["cmap"], E.P["norm"]  # escala común de P anual (escalas.py)
fig, axs = plt.subplots(1, 3, figsize=(16, 11.5))
for ax, (tit, a, cmap, norm) in zip(axs, [
        (f"CHIRPS v3.0 (archivos del curso)\nmedia {comp.loc['P media cuenca (mm/año)', 'CHIRPS v3.0']:,.0f} mm/año".replace(",", " "), P_v3, cm, nm),
        (f"CHIRPS v2.0 (IRI Data Library)\nmedia {comp.loc['P media cuenca (mm/año)', 'CHIRPS v2.0']:,.0f} mm/año".replace(",", " "), P_v2, cm, nm),
        ("Diferencia relativa v3.0 − v2.0 (%)", 100 * (P_v3 / P_v2 - 1), "RdBu_r", TwoSlopeNorm(vmin=-40, vcenter=0, vmax=40))]):
    im = ax.imshow(a, cmap=cmap, norm=norm, extent=ext, interpolation="nearest")
    rio.plot(ax=ax, color="#08306b", lw=0.9); cuenca.boundary.plot(ax=ax, color="black", lw=1)
    ax.set_xlim(minx - 10000, maxx + 10000); ax.set_ylim(miny - 10000, maxy + 10000); ax.set_aspect("equal")
    ax.ticklabel_format(style="plain"); ax.set_xticks([700000, 800000]); ax.tick_params(labelsize=6); ax.set_title(tit, fontsize=10, fontweight="bold")
    ax.set_xlabel("Este (m)", fontsize=8); ax.set_ylabel("Norte (m)", fontsize=8); plt.setp(ax.get_yticklabels(), rotation=90, va="center")
    ax.grid(color="0.7", lw=0.3, ls=":")
    kw = dict(ax=ax, shrink=0.55, pad=0.03)
    cb = E.barra(fig, im, E.P, a, **kw) if norm is nm else fig.colorbar(im, **kw)
    cb.set_label("mm/año" if norm is nm else "%", fontsize=8); cb.ax.tick_params(labelsize=7.5)
axs[2].annotate("N", xy=(0.92, 0.975), xytext=(0.92, 0.92), xycoords="axes fraction", ha="center", fontsize=12, fontweight="bold",
                arrowprops=dict(facecolor="black", width=3, headwidth=9))
fig.suptitle("Precipitación media anual 1981–2010: CHIRPS v3.0 frente a v2.0 · MAGNA-SIRGAS / Colombia Bogotá (EPSG:3116)",
             fontsize=12, fontweight="bold")
fig.savefig(OUT / "panel_chirps_v2_v3.png", dpi=190, bbox_inches="tight"); plt.close(fig)
print("listo")
