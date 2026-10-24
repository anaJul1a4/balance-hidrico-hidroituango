"""
Extensión · pronóstico de caudales · paso 1: grafo de la red de estaciones de caudal.

Nodos: estaciones IDEAM dentro de la cuenca con ≥ 70 % de datos diarios en 1981–2010, más la presa (nodo de salida).
Aristas: cada estación se une a la primera estación (o la presa) que encuentra al recorrer la red de drenaje aguas abajo.
La red de drenaje es la del punto 2: DEM GLO-30 a 90 m, Priority-Flood + ε y direcciones D8.

Ubicación en el cauce: las estaciones del río Cauca se llevan a la celda del cauce principal (≥ 2000 km²) más cercana; las de
tributarios, a la celda de cauce (≥ 5 km²) más cercana que no sea del cauce principal. Se reporta el rendimiento q = Q/A como
control (valores fuera de 3–150 L/s/km² indican una ubicación dudosa).

Salidas: resultados/19_pronostico/nodos.csv, aristas.csv, grafo_estaciones.png
"""
import json
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

np.in1d = np.isin                                      # pysheds 0.5 con numpy 2
from pyproj import Transformer  # noqa: E402
from pysheds.grid import Grid  # noqa: E402
from pysheds.view import Raster  # noqa: E402

import sys  # noqa: E402
sys.path.insert(0, str(Path(__file__).parent))
from priority_flood import condicionar  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEL = ROOT / "resultados" / "01_delimitacion"
OUT = ROOT / "resultados" / "19_pronostico"
OUT.mkdir(parents=True, exist_ok=True)
DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)
OFFS = {64: (-1, 0), 128: (-1, 1), 1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1)}
PRESA = (-75.6680, 7.1360)

inv = pd.read_csv(ROOT / "resultados" / "18_pywr" / "inventario_estaciones_diarias.csv", dtype={"codigo": str})
sel = inv[inv.dentro & (inv["cobertura_1981_2010_%"] >= 70) & (inv.codigo != "26237040")].reset_index(drop=True)
cat = {d["codigo"][-8:]: d for d in json.load(open(ROOT / "datos" / "catalogo_ideam_zona26_hidrometricas.json", encoding="utf-8"))}

grid = Grid.from_raster(str(DEL / "dem_glo30_90m_3116.tif"))
dem = grid.read_raster(str(DEL / "dem_glo30_90m_3116.tif"))
fdir = grid.flowdir(Raster(condicionar(dem, nodata=-9999.0, eps=1e-3), viewfinder=dem.viewfinder), dirmap=DIRMAP)
acc = np.asarray(grid.accumulation(fdir, dirmap=DIRMAP)); fd = np.asarray(fdir)
aff = grid.affine; ckm2 = abs(aff.a * aff.e) / 1e6
A = acc * ckm2
to3116 = Transformer.from_crs(4326, 3116, always_xy=True)


def rc(lon, lat):
    x, y = to3116.transform(lon, lat)
    c, r = ~aff * (x, y)
    return int(r), int(c)


def ubicar(lon, lat, principal, q_medio=None):
    """Celda de cauce más cercana; si el rendimiento resultante es implausible (valle plano: el cauce del DEM se separa
    3–5 km del real), se busca en 6 km la celda cuya área sea más coherente con el caudal medio (q ≈ 30 L/s/km²)."""
    r0, c0 = rc(lon, lat)
    rad = 40 if principal else 15                                   # 3.6 km / 1.35 km
    sub = A[r0 - rad:r0 + rad + 1, c0 - rad:c0 + rad + 1]
    rr, cc = np.mgrid[-rad:rad + 1, -rad:rad + 1]
    ok = (sub >= 2000) if principal else ((sub >= 5) & (sub < 2000))
    if not ok.any():
        ok = sub >= 5
    d = np.where(ok, np.hypot(rr, cc), np.inf)
    i = np.unravel_index(np.argmin(d), d.shape)
    r, c = r0 + i[0] - rad, c0 + i[1] - rad
    if q_medio is not None and not (3 <= 1000 * q_medio / A[r, c] <= 150):
        rad = 67
        sub = A[r0 - rad:r0 + rad + 1, c0 - rad:c0 + rad + 1]
        rr, cc = np.mgrid[-rad:rad + 1, -rad:rad + 1]
        a_esp = 1000 * q_medio / 30.0
        costo = np.abs(np.log(np.maximum(sub, 1) / a_esp)) + 0.05 * np.hypot(rr, cc) / 11   # área coherente, luego cercanía
        costo = np.where(sub >= 5, costo, np.inf)
        i = np.unravel_index(np.argmin(costo), costo.shape)
        r, c = r0 + i[0] - rad, c0 + i[1] - rad
    return r, c


# presa
rp, cp = ubicar(*PRESA, True)
celdas = {"PRESA": (rp, cp)}
filas = []
for s in sel.itertuples():
    princ = str(s.corriente).upper().startswith("CAUCA")
    r, c = ubicar(s.lon, s.lat, princ, s.Q_medio)
    celdas[s.codigo] = (r, c)
    filas.append({"codigo": s.codigo, "nombre": s.nombre.title(), "corriente": str(s.corriente).title(), "lat": s.lat, "lon": s.lon,
                  "cauce_principal": princ, "area_km2": A[r, c], "Q_medio": s.Q_medio,
                  "q_L_s_km2": 1000 * s.Q_medio / A[r, c], "cobertura_%": s._7})
nodos = pd.DataFrame(filas)

# aristas: recorrido aguas abajo hasta la siguiente estación o la presa
pos = {v: k for k, v in celdas.items()}
aristas = []
for k, (r, c) in celdas.items():
    if k == "PRESA":
        continue
    rr, cc, n = r, c, 0
    while True:
        dr, dc = OFFS.get(int(fd[rr, cc]), (0, 0))
        if dr == dc == 0:
            break
        rr, cc, n = rr + dr, cc + dc, n + 1
        if (rr, cc) in pos and pos[(rr, cc)] != k:
            aristas.append({"origen": k, "destino": pos[(rr, cc)], "pasos_90m": n, "dist_km": n * 0.09 * 1.2})
            break
        if n > 40000:
            break
ar = pd.DataFrame(aristas)
nodos["destino"] = nodos.codigo.map(dict(zip(ar.origen, ar.destino)))
nodos.round(3).to_csv(OUT / "nodos.csv", index=False, encoding="utf-8-sig")
ar.round(1).to_csv(OUT / "aristas.csv", index=False, encoding="utf-8-sig")
print(f"nodos: {len(nodos)} + presa | aristas: {len(ar)} | sin conexión: {nodos.destino.isna().sum()}")
print("llegan a la presa:", (ar.destino == "PRESA").sum())
mal = nodos[(nodos.q_L_s_km2 < 3) | (nodos.q_L_s_km2 > 150)]
print("rendimiento dudoso:\n", mal[["codigo", "nombre", "corriente", "area_km2", "Q_medio", "q_L_s_km2"]].round(1).to_string(index=False))

# figura del grafo sobre la cuenca
cuenca = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="cuenca")
rio = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="rio_principal")
xy = {k: aff * (c + 0.5, r + 0.5) for k, (r, c) in celdas.items()}
fig, ax = plt.subplots(figsize=(9, 14))
cuenca.boundary.plot(ax=ax, color="black", lw=1); rio.plot(ax=ax, color="#9ecae1", lw=1.5)
for a in ar.itertuples():
    (x0, y0), (x1, y1) = xy[a.origen], xy[a.destino]
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="->", color="0.35", lw=0.8))
for n in nodos.itertuples():
    x, y = xy[n.codigo]
    ax.scatter(x, y, s=18 + 60 * np.log10(max(n.area_km2, 10)) / 4.6, color="#2a78d6" if n.cauce_principal else "#eb6834",
               edgecolors="black", linewidths=0.4, zorder=5)
x, y = xy["PRESA"]; ax.scatter(x, y, marker="^", s=160, color="red", edgecolors="black", zorder=6)
ax.set_aspect("equal"); ax.ticklabel_format(style="plain"); ax.tick_params(labelsize=7)
ax.set_xticks([700000, 800000]); plt.setp(ax.get_yticklabels(), rotation=90, va="center"); ax.grid(color="0.85", lw=0.4)
ax.set_xlabel("Este (m)", fontsize=8); ax.set_ylabel("Norte (m)", fontsize=8)
ax.set_title(f"Grafo de estaciones de caudal ({len(nodos)} nodos + presa, {len(ar)} aristas)\nazul: río Cauca · naranja: tributarios · "
             "triángulo: presa", fontsize=10, fontweight="bold")
fig.savefig(OUT / "grafo_estaciones.png", dpi=170, bbox_inches="tight"); plt.close(fig)
