"""
Punto 2 - Delimitación de la cuenca del río Cauca hasta la presa de Hidroituango.

Insumo : Copernicus DEM GLO-30 (teselas 1x1° descargadas de AWS, CARTOGRAFIA/GLO30/tiles)
Salidas: trabajo1/resultados/01_delimitacion/
    dem_glo30_90m_3116.tif   DEM (90 m, EPSG:3116) del área de trabajo
    dem_cuenca_90m_3116.tif  DEM recortado a la cuenca
    cuenca_cauca_hidroituango.gpkg  capas: cuenca, drenajes, rio_principal, punto_cierre
    parametros_morfometricos.csv
"""
import json
from pathlib import Path

import numpy as np
np.in1d = np.isin  # pysheds 0.5 usa np.in1d, eliminado en numpy 2.x

import geopandas as gpd
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.features import shapes
from rasterio.merge import merge
from rasterio.warp import calculate_default_transform, reproject
from pyproj import Transformer
from pysheds.grid import Grid
from pysheds.view import Raster
from shapely.geometry import LineString, Point, shape
from shapely.ops import unary_union

from priority_flood import condicionar

ROOT = Path(__file__).resolve().parents[2]
TILES = ROOT / "CARTOGRAFIA" / "GLO30" / "tiles"
OUT = ROOT / "trabajo1" / "resultados" / "01_delimitacion"
OUT.mkdir(parents=True, exist_ok=True)

CRS = "EPSG:3116"              # MAGNA-SIRGAS / Colombia Bogotá (mismo de mdt900 y red de drenaje)
RES = 90.0                     # m
BOUNDS = (-77.10, 1.90, -75.05, 7.30)   # lon/lat del área de trabajo
OUTLET = (-75.6680, 7.1360)    # presa Hidroituango (lon, lat), aprox.
UMBRAL_KM2 = 25.0              # área mínima para iniciar un cauce
DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)  # N NE E SE S SW W NW (ESRI)
OFFS = {64: (-1, 0), 128: (-1, 1), 1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1)}

# ----------------------------------------------------------------------------- 1. mosaico y reproyección
dem_tif = OUT / "dem_glo30_90m_3116.tif"
if not dem_tif.exists():
    srcs = [rasterio.open(p) for p in sorted(TILES.glob("*.tif"))]
    mos, mtr = merge(srcs, bounds=BOUNDS)
    src_crs = srcs[0].crs
    for s in srcs:
        s.close()
    h, w = mos.shape[1:]
    left, top = mtr.c, mtr.f
    right, bottom = left + w * mtr.a, top + h * mtr.e
    dtr, dw, dh = calculate_default_transform(src_crs, CRS, w, h, left, bottom, right, top, resolution=RES)
    dst = np.full((dh, dw), -9999, dtype="float32")
    reproject(mos[0], dst, src_transform=mtr, src_crs=src_crs, dst_transform=dtr, dst_crs=CRS,
              resampling=Resampling.average, dst_nodata=-9999)
    del mos
    with rasterio.open(dem_tif, "w", driver="GTiff", height=dh, width=dw, count=1, dtype="float32",
                       crs=CRS, transform=dtr, nodata=-9999, compress="deflate", tiled=True) as d:
        d.write(dst, 1)
    print("DEM 90 m:", dst.shape)

# ----------------------------------------------------------------------------- 2. condicionamiento hidrológico
grid = Grid.from_raster(str(dem_tif))
dem = grid.read_raster(str(dem_tif))
# Priority-Flood + épsilon: pysheds.resolve_flats no resuelve la planicie del Valle del Cauca
inflated = Raster(condicionar(dem, nodata=-9999.0, eps=1e-3), viewfinder=dem.viewfinder)
fdir = grid.flowdir(inflated, dirmap=DIRMAP)
acc = grid.accumulation(fdir, dirmap=DIRMAP)
cell_km2 = RES * RES / 1e6

# ----------------------------------------------------------------------------- 3. punto de cierre y cuenca
to3116 = Transformer.from_crs(4326, CRS, always_xy=True)
to4326 = Transformer.from_crs(CRS, 4326, always_xy=True)
x0, y0 = to3116.transform(*OUTLET)
xs, ys = grid.snap_to_mask(acc > 20000 / cell_km2, (x0, y0))
catch = grid.catchment(x=xs, y=ys, fdir=fdir, dirmap=DIRMAP, xytype="coordinate")
area_km2 = np.asarray(catch).sum() * cell_km2
print(f"cierre ajustado: {to4326.transform(xs, ys)}  desplazamiento {np.hypot(xs-x0, ys-y0):.0f} m  área {area_km2:.0f} km2")

aff = grid.affine
mask = np.asarray(catch).astype("uint8")
cuenca = unary_union([shape(g) for g, v in shapes(mask, mask=mask == 1, transform=aff)])
cuenca = max(cuenca.geoms, key=lambda g: g.area) if cuenca.geom_type == "MultiPolygon" else cuenca

# DEM recortado a la cuenca
dem_np = np.asarray(dem)
with rasterio.open(OUT / "dem_cuenca_90m_3116.tif", "w", driver="GTiff", height=mask.shape[0], width=mask.shape[1],
                   count=1, dtype="float32", crs=CRS, transform=aff, nodata=-9999, compress="deflate", tiled=True) as d:
    d.write(np.where(mask == 1, dem_np, -9999).astype("float32"), 1)

# ----------------------------------------------------------------------------- 4. red de drenaje (Strahler)
streams = Raster((np.asarray(acc) >= UMBRAL_KM2 / cell_km2) & (mask == 1), viewfinder=acc.viewfinder)
order = np.asarray(grid.stream_order(fdir, streams, dirmap=DIRMAP))
branches = grid.extract_river_network(fdir, streams, dirmap=DIRMAP)
rows = []
for f in branches["features"]:
    ln = LineString(f["geometry"]["coordinates"])
    if ln.length == 0:
        continue
    c, r = ~aff * ln.interpolate(0.5, normalized=True).coords[0]
    rows.append({"orden": int(order[int(r), int(c)]), "long_km": ln.length / 1000, "geometry": ln})
drenajes = gpd.GeoDataFrame(rows, crs=CRS)

# ----------------------------------------------------------------------------- 5. río principal (máxima acumulación aguas arriba)
fd = np.asarray(fdir); ac = np.asarray(acc)
c, r = map(int, ~aff * (xs, ys))
path = [(r, c)]
while True:
    best = None
    for code, (dr, dc) in OFFS.items():
        rr, cc = r - dr, c - dc               # vecino que, con dirección `code`, drena hacia (r, c)
        if 0 <= rr < fd.shape[0] and 0 <= cc < fd.shape[1] and fd[rr, cc] == code:
            if best is None or ac[rr, cc] > ac[best]:
                best = (rr, cc)
    if best is None:
        break
    r, c = best
    path.append(best)
path = path[::-1]   # nacimiento -> cierre
xy = [aff * (cc + 0.5, rr + 0.5) for rr, cc in path]
rio = LineString(xy)
z_rio = np.array([dem_np[rr, cc] for rr, cc in path])

# ----------------------------------------------------------------------------- 6. parámetros morfométricos
ev = dem_np[mask == 1]
perim_km = cuenca.simplify(RES).length / 1000   # sin el escalonado de los píxeles
L_km = rio.length / 1000
param = {
    "Área (km²)": area_km2,
    "Perímetro (km)": perim_km,
    "Coef. compacidad Gravelius Kc": 0.282 * perim_km / np.sqrt(area_km2),
    "Long. río principal (km)": L_km,
    "Factor de forma Kf = A/L²": area_km2 / L_km**2,
    "Cota nacimiento río principal (m)": float(z_rio[0]),
    "Cota punto de cierre (m)": float(z_rio[-1]),
    "Pendiente media río principal (%)": 100 * (z_rio[0] - z_rio[-1]) / (L_km * 1000),
    "Elevación mínima cuenca (m)": float(ev.min()),
    "Elevación media cuenca (m)": float(ev.mean()),
    "Elevación máxima cuenca (m)": float(ev.max()),
    "Long. total de drenajes (km)": drenajes.long_km.sum(),
    "Densidad de drenaje (km/km²)": drenajes.long_km.sum() / area_km2,
    "Orden de Strahler máximo": int(drenajes.orden.max()),
    "Umbral de iniciación de cauces (km²)": UMBRAL_KM2,
    "Punto de cierre lon": to4326.transform(xs, ys)[0],
    "Punto de cierre lat": to4326.transform(xs, ys)[1],
}
pd.Series(param, name="valor").to_csv(OUT / "parametros_morfometricos.csv", encoding="utf-8-sig")
print(pd.Series(param).round(3).to_string())

# ----------------------------------------------------------------------------- 7. exportar GeoPackage
gpkg = OUT / "cuenca_cauca_hidroituango.gpkg"
gpd.GeoDataFrame({"nombre": ["Río Cauca hasta Hidroituango"], "area_km2": [area_km2], "perim_km": [perim_km]},
                 geometry=[cuenca], crs=CRS).to_file(gpkg, layer="cuenca")
drenajes.to_file(gpkg, layer="drenajes")
gpd.GeoDataFrame({"nombre": ["Río Cauca"], "long_km": [L_km]}, geometry=[rio], crs=CRS).to_file(gpkg, layer="rio_principal")
gpd.GeoDataFrame({"nombre": ["Presa Hidroituango"]}, geometry=[Point(xs, ys)], crs=CRS).to_file(gpkg, layer="punto_cierre")
np.save(OUT / "perfil_rio_principal.npy", np.c_[np.r_[0, np.cumsum(np.hypot(*np.diff(np.array(xy), axis=0).T))] / 1000, z_rio])
print("listo:", gpkg)
