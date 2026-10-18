"""
Corrección del sesgo de ERA5 y ERA5-Land por mapeo de cuantiles (quantile mapping, empírico, por celda y por mes calendario).

Referencia: CHIRPS v2.0 mensual, agregado (promedio) a la celda de cada reanálisis. Se usa CHIRPS porque está corregido con estaciones
y es la única serie mensual de referencia disponible en el trabajo (del IDEAM sólo se tienen las normales 1981–2010).

Para cada celda y cada mes m: y = F_ref,m⁻¹( F_mod,m(x) ), con las distribuciones empíricas de los años de calibración. Fuera del rango
de calibración se aplica el cociente de los extremos (constante). El método conserva el orden de los valores de ERA5 en cada mes,
así que corrige la distribución (media, varianza, extremos) pero no el momento de los eventos.

Evaluación:
  · muestra dividida: calibración 1981–1995, validación 1996–2010 (sesgo frente a CHIRPS en años no usados);
  · corrección completa 1981–2010: balance de largo plazo con la ETP de Hargreaves y Budyko celda a celda, frente al caudal observado
    (independiente del método); correlación de la P anual con el caudal anual; ciclo anual frente al IDEAM.

Salidas: resultados/17_quantile_mapping/
"""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import shapely
import xarray as xr
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject

sys.path.insert(0, str(Path(__file__).parent))
from productos import abrir  # noqa: E402

RES = Path(__file__).resolve().parents[1] / "resultados"
OUT = RES / "17_quantile_mapping"
OUT.mkdir(exist_ok=True)
SEG = 365.25 * 86400
CAL, VAL, TOD = slice("1981", "1995"), slice("1996", "2010"), slice("1981", "2010")


# ----------------------------------------------------------------------------- referencia CHIRPS en la grilla de cada producto
def referencia(ch, mod):
    """Promedio de los píxeles de CHIRPS (0.05°) cuyo centro cae en cada celda del producto."""
    dlat, dlon = float(abs(mod.lat[1] - mod.lat[0])), float(abs(mod.lon[1] - mod.lon[0]))
    la, lo = mod.lat.values, mod.lon.values
    il = np.array([np.argmin(np.abs(la - v)) if np.min(np.abs(la - v)) <= dlat / 2 else -1 for v in ch.lat.values])
    jl = np.array([np.argmin(np.abs(lo - v)) if np.min(np.abs(lo - v)) <= dlon / 2 else -1 for v in ch.lon.values])
    ref = np.full((ch.sizes["time"], len(la), len(lo)), np.nan)
    vals = ch.values
    for a in np.unique(il[il >= 0]):
        fa = il == a
        for b in np.unique(jl[jl >= 0]):
            fb = jl == b
            bloque = vals[:, fa][:, :, fb]
            if np.isfinite(bloque).any():
                ref[:, a, b] = np.nanmean(bloque.reshape(bloque.shape[0], -1), axis=1)
    return xr.DataArray(ref, dims=("time", "lat", "lon"), coords={"time": ch.time, "lat": la, "lon": lo})


def qm(mod_cal, ref_cal, mod_apl):
    """Mapeo de cuantiles empírico, por celda y mes calendario."""
    out = xr.full_like(mod_apl, np.nan)
    for m in range(1, 13):
        xc = mod_cal.sel(time=mod_cal.time.dt.month == m).values
        oc = ref_cal.sel(time=ref_cal.time.dt.month == m).values
        sel_a = mod_apl.time.dt.month == m
        xa = mod_apl.sel(time=sel_a).values
        ya = np.full_like(xa, np.nan)
        for a in range(xa.shape[1]):
            for b in range(xa.shape[2]):
                x, o = np.sort(xc[:, a, b]), np.sort(oc[:, a, b])
                if not (np.isfinite(x).all() and np.isfinite(o).all()):
                    continue
                pp = (np.arange(1, len(x) + 1) - 0.44) / (len(x) + 0.12)            # posiciones de Gringorten
                v = xa[:, a, b]
                q = np.interp(v, x, pp, left=np.nan, right=np.nan)
                y = np.interp(q, pp, o)
                y = np.where(v < x[0], v * (o[0] / x[0] if x[0] > 0 else 0), y)     # extrapolación por cociente de extremos
                y = np.where(v > x[-1], v * o[-1] / x[-1], y)
                ya[:, a, b] = y
        out.loc[dict(time=out.time[sel_a.values])] = ya
    return out


# ----------------------------------------------------------------------------- base: grilla de 90 m, ETP, cuenca, áreas de drenaje
def leer(p):
    with rasterio.open(p) as s:
        a = s.read(1).astype("float64"); a[a == s.nodata] = np.nan
        return a, s.transform, s.crs


ETP, aff, crs = leer(RES / "08_etp_etr" / "ETP_anual_hargreaves_90m_3116.tif")
shape = ETP.shape
b9 = pd.read_csv(RES / "09_balance" / "balance_subcuencas.csv", dtype={"codigo": str})
sub = gpd.read_file(RES / "06_caudales" / "subcuencas_estaciones.gpkg", layer="areas_drenaje")
cuenca = gpd.read_file(RES / "01_delimitacion" / "cuenca_cauca_hidroituango.gpkg", layer="cuenca")
geoms = {r.codigo: r.geometry for r in sub.itertuples()}; geoms["HIDRO"] = cuenca.geometry[0]
mascaras = {c: ~geometry_mask([geoms[c]], out_shape=shape, transform=aff) for c in b9.codigo}
ca = abs(aff.a * aff.e) / 1e6
cu4326 = cuenca.to_crs(4326).geometry[0]
qa = pd.read_csv(RES / "15_complementarias" / "Q_anual_estaciones.csv", index_col=0)
cic_ide = pd.read_csv(RES / "13_climatologia" / "ciclo_anual.csv")["P media cuenca (mm)"].to_numpy()


def budyko(p, etp):
    f = etp / p
    return p * np.sqrt(f * np.tanh(1 / f) * (1 - np.exp(-f)))


def a_90m(da):
    a = da
    if a.lat[0] < a.lat[-1]:
        a = a.isel(lat=slice(None, None, -1))
    dx, dy = float(abs(a.lon[1] - a.lon[0])), float(abs(a.lat[1] - a.lat[0]))
    tr = from_origin(float(a.lon[0]) - dx / 2, float(a.lat[0]) + dy / 2, dx, dy)
    dst = np.full(shape, np.nan)
    reproject(a.values.astype("float64"), dst, src_transform=tr, src_crs="EPSG:4326", src_nodata=np.nan, dst_transform=aff,
              dst_crs=crs, dst_nodata=np.nan, resampling=Resampling.nearest)
    return dst


def anual(da):
    return da.groupby("time.year").sum("time", min_count=12).mean("year")


def serie_cuenca(da):
    m = shapely.contains_xy(cu4326, *np.meshgrid(da.lon.values, da.lat.values))
    s = da.where(m).mean(["lat", "lon"]).to_series()
    s.index = pd.DatetimeIndex(s.index)
    return s


def balance(p90, nombre):
    etr = budyko(p90, ETP)
    filas = []
    for r in b9.itertuples():
        m = mascaras[r.codigo] & np.isfinite(p90) & np.isfinite(ETP)
        A = m.sum() * ca
        P, E = np.nanmean(p90[m]), np.nanmean(etr[m])
        q = (P - E) / 1000 * A * 1e6 / SEG
        filas.append({"campo": nombre, "codigo": r.codigo, "estacion": r.estacion, "P": P, "ETR": E, "Q_est": q, "Q_obs": r._8,
                      "error_%": 100 * (q / r._8 - 1)})
    return filas


# ----------------------------------------------------------------------------- corrección y evaluación
chirps = abrir("CHIRPS").precip.sel(time=TOD)
bal, met, mapas = [], [], {}
for nombre in ["ERA5", "ERA5-Land"]:
    mod_all = abrir(nombre).precip.sel(time=TOD)
    # recorte a la caja de la cuenca (con un margen de una celda)
    d = float(abs(mod_all.lat[1] - mod_all.lat[0]))
    mod = mod_all.sel(lat=slice(7.6, 1.7) if mod_all.lat[0] > mod_all.lat[-1] else slice(1.7, 7.6), lon=slice(-77.4 - d, -74.9 + d))
    ref = referencia(chirps, mod)

    # 1) muestra dividida
    corr_val = qm(mod.sel(time=CAL), ref.sel(time=CAL), mod.sel(time=VAL))
    s_ref_v, s_mod_v, s_cor_v = (serie_cuenca(x.sel(time=VAL)) for x in (ref, mod, corr_val))
    a_ref, a_mod, a_cor = (s.groupby(s.index.year).sum() for s in (s_ref_v, s_mod_v, s_cor_v))
    met.append({"producto": nombre, "prueba": "validación 1996–2010 (calibrado 1981–1995)",
                "P cruda (mm/año)": a_mod.mean(), "P corregida (mm/año)": a_cor.mean(), "P CHIRPS (mm/año)": a_ref.mean(),
                "sesgo crudo vs CHIRPS (%)": 100 * (a_mod.mean() / a_ref.mean() - 1),
                "sesgo corregido vs CHIRPS (%)": 100 * (a_cor.mean() / a_ref.mean() - 1),
                "r mensual crudo vs CHIRPS": np.corrcoef(s_mod_v, s_ref_v)[0, 1],
                "r mensual corregido vs CHIRPS": np.corrcoef(s_cor_v, s_ref_v)[0, 1]})

    # 2) corrección completa 1981–2010
    corr = qm(mod, ref, mod)
    corr.to_dataset(name="precip").to_netcdf(OUT / f"{nombre.replace('-', '_')}_QM_1981_2010.nc")
    for etiqueta, da in [(f"{nombre} sin corregir", mod), (f"{nombre} con mapeo de cuantiles", corr)]:
        p90 = a_90m(anual(da))
        mapas[etiqueta] = p90
        bal += balance(p90, etiqueta)
        s = serie_cuenca(da); a = s.groupby(s.index.year).sum()
        cic = s.groupby(s.index.month).mean().to_numpy()
        fila = {"producto": nombre, "prueba": etiqueta, "P media cuenca (mm/año)": a.mean(), "CV interanual (%)": 100 * a.std() / a.mean(),
                "r ciclo vs IDEAM": np.corrcoef(cic, cic_ide)[0, 1], "mes máximo": int(np.argmax(cic)) + 1}
        for e in ["Bolombolo", "La Pintada", "Puerto Valdivia"]:
            c = pd.concat([a, qa[e]], axis=1).loc[1981:2010].dropna()
            fila[f"r anual P–Q {e}"] = np.corrcoef(c.iloc[:, 0], c.iloc[:, 1])[0, 1]
        met.append(fila)

# referencia CHIRPS en las mismas métricas
s = serie_cuenca(chirps); a = s.groupby(s.index.year).sum(); cic = s.groupby(s.index.month).mean().to_numpy()
fila = {"producto": "CHIRPS v2.0", "prueba": "referencia", "P media cuenca (mm/año)": a.mean(), "CV interanual (%)": 100 * a.std() / a.mean(),
        "r ciclo vs IDEAM": np.corrcoef(cic, cic_ide)[0, 1], "mes máximo": int(np.argmax(cic)) + 1}
for e in ["Bolombolo", "La Pintada", "Puerto Valdivia"]:
    c = pd.concat([a, qa[e]], axis=1).loc[1981:2010].dropna()
    fila[f"r anual P–Q {e}"] = np.corrcoef(c.iloc[:, 0], c.iloc[:, 1])[0, 1]
met.append(fila)

bal = pd.DataFrame(bal); met = pd.DataFrame(met)
bal.to_csv(OUT / "balance_qm.csv", index=False, encoding="utf-8-sig")
met.to_csv(OUT / "metricas_qm.csv", index=False, encoding="utf-8-sig")
for k, v in mapas.items():
    with rasterio.open(OUT / f"P_{k.replace(' ', '_').replace('-', '_')}_90m_3116.tif", "w", driver="GTiff", height=shape[0], width=shape[1],
                       count=1, dtype="float32", crs=crs, transform=aff, nodata=-9999, compress="deflate") as dst:
        dst.write(np.where(np.isfinite(v), v, -9999).astype("float32"), 1)

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 20)
cie = bal[bal.codigo == "HIDRO"].set_index("campo")[["P", "ETR", "Q_est", "error_%"]]
mae = bal[bal.codigo != "HIDRO"].groupby("campo", sort=False)["error_%"].agg(MAE=lambda e: e.abs().mean())
print(cie.join(mae).round(1).to_string()); print()
print(met.round(2).to_string())
