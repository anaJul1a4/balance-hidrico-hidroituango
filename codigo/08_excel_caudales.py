"""
Punto 8 - Caracterización de los caudales observados en las estaciones IDEAM validadas
(≥ 15 años completos en 1981-2010, ver 07_caudales_ideam.py).

Para cada estación: ubicación, área de drenaje (delimitada con el DEM GLO-30 90 m), periodo de registro
y caudal medio anual multianual.
Salidas: trabajo1/resultados/06_caudales/
    Punto8_caudales_estaciones.xlsx  (fórmulas vivas de Excel)
    subcuencas_estaciones.gpkg        (puntos de estación ajustados y áreas de drenaje)
    mapa_estaciones_caudal_validadas.png
"""
import json
import sys
from pathlib import Path

import numpy as np
np.in1d = np.isin  # pysheds 0.5 usa np.in1d, eliminado en numpy 2.x

import geopandas as gpd
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import pandas as pd
import rasterio
from matplotlib.colors import LightSource
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from pyproj import Transformer
from pysheds.grid import Grid
from pysheds.view import Raster
from rasterio.features import shapes
from shapely.geometry import Point, shape
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).parent))
from priority_flood import condicionar  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DAT = ROOT / "trabajo1" / "datos"
DEL = ROOT / "trabajo1" / "resultados" / "01_delimitacion"
OUT = ROOT / "trabajo1" / "resultados" / "06_caudales"
OUT.mkdir(parents=True, exist_ok=True)
CRS = "EPSG:3116"
DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)
AREA_MIN_SNAP = 1000.0          # km²: el punto se ajusta a la celda más cercana del cauce principal
P0, P1 = 1981, 2010
SEG_ANO = 365.25 * 86400
# La Pintada: la coordenada cae junto a la desembocadura del río Arma. Los caudales indican que la estación está
# aguas ARRIBA de la confluencia (Irra→La Pintada sólo +26 m³/s, mientras el Arma aporta ~42 m³/s en Quitasueño),
# así que se ajusta al cauce principal con área acumulada < 27 500 km² (antes de recibir el Arma).
SNAP_RANGO = {"26187110": (24_600.0, 27_500.0)}

# ----------------------------------------------------------------------------- estaciones validadas
disp = pd.read_csv(DAT / "caudales_ideam" / "disponibilidad_caudales.csv", dtype={"codigo": str})
disp = disp[disp["apta (>=15 anos 1981-2010)"] == True].copy()
cat = pd.DataFrame(json.load(open(DAT / "catalogo_ideam_zona26_hidrometricas.json", encoding="utf-8")))
cat = cat.drop_duplicates("codigo").assign(codigo=lambda d: d.codigo.str[2:])
est = disp.merge(cat[["codigo", "nombre", "corriente", "categoria", "tecnologia", "estado", "departamento",
                      "municipio", "altitud", "latitud", "longitud", "fecha_instalacion"]], on="codigo", how="left")
est["lat"], est["lon"] = est.latitud.astype(float), est.longitud.astype(float)
est = est.rename(columns={"% dias con dato (registro)": "pct_dias", "anos validos 1981-2010": "anos_validos",
                          "Q medio registro (m3/s)": "Q_registro", "Q medio 1981-2010 (m3/s)": "Q_meses_validos"})
est = est.sort_values("Q_meses_validos").reset_index(drop=True)
to3116 = Transformer.from_crs(4326, CRS, always_xy=True)
est["X"], est["Y"] = to3116.transform(est.lon.to_numpy(), est.lat.to_numpy())

# ----------------------------------------------------------------------------- áreas de drenaje con el DEM
dem_tif = DEL / "dem_glo30_90m_3116.tif"
grid = Grid.from_raster(str(dem_tif))
dem = grid.read_raster(str(dem_tif))
fdir = grid.flowdir(Raster(condicionar(dem), viewfinder=dem.viewfinder), dirmap=DIRMAP)
acc = grid.accumulation(fdir, dirmap=DIRMAP)
aff, cell_km2 = grid.affine, abs(grid.affine.a * grid.affine.e) / 1e6
cuenca = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="cuenca")
A_CUENCA = float(cuenca.area_km2[0])

polys, puntos, areas, desp, borde = [], [], [], [], []
for r in est.itertuples():
    lo, hi = SNAP_RANGO.get(r.codigo, (AREA_MIN_SNAP, np.inf))
    A = np.asarray(acc) * cell_km2
    xs, ys = grid.snap_to_mask(Raster((A > lo) & (A < hi), viewfinder=acc.viewfinder), (r.X, r.Y))
    c = np.asarray(grid.catchment(x=xs, y=ys, fdir=fdir, dirmap=DIRMAP, xytype="coordinate")).astype("uint8")
    toca = bool(c[0].any() or c[-1].any() or c[:, 0].any() or c[:, -1].any())
    p = unary_union([shape(g) for g, v in shapes(c, mask=c == 1, transform=aff)])
    polys.append(max(p.geoms, key=lambda g: g.area) if p.geom_type == "MultiPolygon" else p)
    puntos.append(Point(xs, ys)); areas.append(c.sum() * cell_km2)
    desp.append(np.hypot(xs - r.X, ys - r.Y)); borde.append(toca)
est["area_km2_DEM"], est["ajuste_m"], est["toca_borde_DEM"] = areas, desp, borde
est["pct_cuenca"] = 100 * est.area_km2_DEM / A_CUENCA
print(est[["codigo", "estacion", "area_km2_DEM", "ajuste_m", "toca_borde_DEM"]].round(0).to_string(index=False))
assert not est.toca_borde_DEM.any(), "alguna subcuenca toca el borde del DEM: ampliar BOUNDS en 01_delimitacion"

gpd.GeoDataFrame(est[["codigo", "estacion", "area_km2_DEM"]], geometry=polys, crs=CRS).to_file(
    OUT / "subcuencas_estaciones.gpkg", layer="areas_drenaje")
gpd.GeoDataFrame(est[["codigo", "estacion", "corriente", "area_km2_DEM", "Q_meses_validos"]],
                 geometry=puntos, crs=CRS).to_file(OUT / "subcuencas_estaciones.gpkg", layer="estaciones")

# ----------------------------------------------------------------------------- series
Q = pd.read_csv(DAT / "caudales_ideam" / "Q_mensual_completa.csv", index_col=0, parse_dates=True)
cods = list(est.codigo)
Qp = Q.loc[f"{P0}":f"{P1}", cods]
anual = Qp.groupby(Qp.index.year).apply(lambda d: d.mean().where(d.count() == 12))
est["Q_anual_medio"] = anual.mean().reindex(cods).to_numpy()   # mismo cálculo que la hoja Resumen_Q

# ----------------------------------------------------------------------------- mapa
with rasterio.open(DEL / "dem_cuenca_90m_3116.tif") as src:
    z = src.read(1, masked=True).filled(np.nan).astype(float)
    ext = (src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top)
rio = gpd.read_file(DEL / "cuenca_cauca_hidroituango.gpkg", layer="rio_principal")
fig, ax = plt.subplots(figsize=(10, 15))
hs = LightSource(azdeg=315, altdeg=45).hillshade(np.nan_to_num(z, nan=np.nanmin(z)), vert_exag=3, dx=90, dy=90)
ax.imshow(np.where(np.isnan(z), np.nan, hs), cmap="gray", vmin=0, vmax=1.3, extent=ext, zorder=1)
cmap = plt.get_cmap("viridis_r", len(est))
for i, p in reversed(list(enumerate(polys))):
    gpd.GeoSeries([p], crs=CRS).plot(ax=ax, color=cmap(i), alpha=0.28, edgecolor=cmap(i), linewidth=1.2, zorder=2)
rio.plot(ax=ax, color="#08306b", linewidth=1.8, zorder=3)
cuenca.boundary.plot(ax=ax, color="black", linewidth=1.3, zorder=4)
for i, (r, pt) in enumerate(zip(est.itertuples(), puntos)):
    ax.scatter(pt.x, pt.y, s=110, color=cmap(i), edgecolors="black", linewidths=0.9, zorder=6)
    ax.annotate(f"{r.estacion.title()}\nA = {r.area_km2_DEM:,.0f} km² · Q = {r.Q_anual_medio:,.0f} m³/s".replace(",", " "),
                (pt.x, pt.y), xytext=(9, 0), textcoords="offset points", va="center", fontsize=7.5, zorder=7,
                path_effects=[pe.withStroke(linewidth=2.5, foreground="white")])
minx, miny, maxx, maxy = cuenca.total_bounds
ax.set_xlim(minx - 20000, maxx + 70000); ax.set_ylim(miny - 15000, maxy + 30000)
ax.set_aspect("equal"); ax.ticklabel_format(style="plain"); ax.tick_params(labelsize=7)
ax.set_xlabel("Este (m)", fontsize=8); ax.set_ylabel("Norte (m)", fontsize=8)
plt.setp(ax.get_yticklabels(), rotation=90, va="center"); ax.grid(color="0.7", lw=0.3, ls=":")
ax.annotate("N", xy=(0.93, 0.62), xytext=(0.93, 0.565), xycoords="axes fraction", ha="center", fontsize=14,
            fontweight="bold", arrowprops=dict(facecolor="black", width=4, headwidth=12))
ax.set_title("Estaciones de caudal IDEAM validadas y sus áreas de drenaje\n"
             "Q = caudal medio anual multianual 1981–2010", fontsize=11, fontweight="bold")
ax.text(0.99, 0.005, "Áreas de drenaje: DEM Copernicus GLO-30 (90 m), D8\nMAGNA-SIRGAS / Colombia Bogotá (EPSG:3116)",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=6.5)
fig.tight_layout(); fig.savefig(OUT / "mapa_estaciones_caudal_validadas.png", dpi=250); plt.close(fig)

# ----------------------------------------------------------------------------- Excel
wb = Workbook()
H = Font(bold=True, color="FFFFFF"); HF = PatternFill("solid", fgColor="1F4E79"); BOLD = Font(bold=True)
thin = Side(style="thin", color="BBBBBB"); BOX = Border(top=thin, bottom=thin, left=thin, right=thin)
INP = PatternFill("solid", fgColor="FFF2CC")


def encabezado(ws, fila, cols, alto=45):
    for j, c in enumerate(cols, 1):
        cell = ws.cell(fila, j, c); cell.font = H; cell.fill = HF; cell.border = BOX
        cell.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
    ws.row_dimensions[fila].height = alto


def anchos(ws, w):
    for j, x in enumerate(w, 1):
        ws.column_dimensions[get_column_letter(j)].width = x


N = len(est)
# 1. Metodología
ws = wb.active; ws.title = "Metodologia"
txt = [("PUNTO 8 — CARACTERIZACIÓN DE LOS CAUDALES OBSERVADOS", BOLD),
       ("Cuenca del río Cauca hasta la presa de Hidroituango (área 35 992 km², DEM GLO-30 90 m).", None),
       ("", None),
       ("Fuente de caudales: IDEAM, archivo nacional HidrologiaNacionalDiaria.zip (actualizado 12/08/2026), "
        "variable Q_MEDIA_D (caudal medio diario, m³/s).", None),
       ("Ubicación: Catálogo Nacional de Estaciones del IDEAM (datos.gov.co, dataset hp9r-jxuu).", None),
       ("", None),
       ("Criterio de validación (≥ 15 años de información):", BOLD),
       ("  · Mes válido: ≥ 80 % de los días con dato; el caudal mensual es el promedio de los días.", None),
       ("  · Año válido: 12 meses válidos.", None),
       (f"  · Estación validada: ≥ 15 años válidos en el periodo común {P0}–{P1} (periodo de la climatología IDEAM).", None),
       ("  · No cumplieron: Pte. Pescadero y Olaya (10 años), Mediacanoa (7), La Salvajina (termina en 1980); "
        "Anacaro no tiene serie de caudal.", None),
       ("", None),
       ("Área de drenaje: delimitada con el DEM Copernicus GLO-30 remuestreado a 90 m (EPSG:3116), relleno de "
        "depresiones Priority-Flood + ε y direcciones de flujo D8.", None),
       (f"  El punto de cada estación se ajusta a la celda más cercana del cauce con área acumulada ≥ {AREA_MIN_SNAP:.0f} km² "
        "(columna 'Ajuste al cauce').", None),
       ("  La Pintada se ajusta al cauce aguas arriba de la desembocadura del río Arma: entre Irra y La Pintada el "
        "caudal sólo aumenta 26 m³/s, mientras el Arma aporta ~42 m³/s (Quitasueño).", None),
       ("  En el Valle del Cauca (Juanchito, La Victoria) el cauce del DEM se separa 3–5 km del río real por lo plano "
        "del valle; el área de drenaje de esas estaciones tiene una incertidumbre del orden de ±5 %.", None),
       ("", None),
       ("Caudal medio anual multianual = promedio de los caudales medios anuales de los años válidos "
        f"{P0}–{P1} (hoja Q_anual).", None),
       ("Rendimiento q = Q / A  (L/s/km²);  lámina de escorrentía R = Q · 31 557 600 s / A  (mm/año).", None),
       ("", None),
       ("Pto. Valdivia es el punto de cierre de referencia: está ~35 km aguas abajo de la presa y drena un área "
        "algo mayor que la cuenca; la hoja Resumen_Q incluye su transferencia por relación de áreas al cierre.", None),
       ("Celdas amarillas = datos de entrada; el resto son fórmulas de Excel.", None)]
for i, (s, f) in enumerate(txt, 1):
    c = ws.cell(i, 1, s)
    if f:
        c.font = f
ws.column_dimensions["A"].width = 150

# 2. Estaciones (ubicación, área, periodo)
ws = wb.create_sheet("Estaciones")
cols = ["Código", "Estación", "Corriente", "Rol", "Categoría", "Estado actual", "Departamento", "Municipio",
        "Latitud (°)", "Longitud (°)", "Este 3116 (m)", "Norte 3116 (m)", "Altitud (m s.n.m.)",
        "Área de drenaje (km²)", "% de la cuenca", "Ajuste al cauce (m)", "Inicio registro", "Fin registro",
        "Años de registro", "% días con dato", f"Años válidos {P0}–{P1}", "¿>15 años?"]
encabezado(ws, 1, cols, 48)
for i, r in enumerate(est.itertuples(), 2):
    vals = [r.codigo, r.estacion.title(), r.corriente, r.rol, r.categoria, r.estado, r.departamento, r.municipio,
            round(r.lat, 6), round(r.lon, 6), round(r.X, 1), round(r.Y, 1), float(r.altitud),
            round(r.area_km2_DEM, 1), f"=N{i}/{A_CUENCA}*100", round(r.ajuste_m, 0),
            pd.Timestamp(r.inicio).to_pydatetime(), pd.Timestamp(r.fin).to_pydatetime(),
            f"=YEARFRAC(Q{i},R{i})", round(r.pct_dias, 1), int(r.anos_validos), f'=IF(U{i}>15,"Sí","No")']
    for j, x in enumerate(vals, 1):
        c = ws.cell(i, j, x); c.border = BOX
        if j in (17, 18):
            c.number_format = "yyyy-mm-dd"
        if j in (15, 19):
            c.number_format = "0.0"
        if j in (9, 10, 11, 12, 13, 14, 17, 18, 20, 21):
            c.fill = INP
anchos(ws, [10, 16, 10, 9, 13, 14, 15, 18, 10, 11, 12, 12, 10, 12, 9, 10, 11, 11, 9, 9, 10, 8])
ws.freeze_panes = "C2"

# 3. Serie mensual 1981-2010
ws = wb.create_sheet("Q_mensual")
encabezado(ws, 1, ["Fecha", "Año", "Mes"] + [f"{r.estacion.title()} ({r.codigo})" for r in est.itertuples()], 40)
for i, (t, row) in enumerate(Qp.iterrows(), 2):
    ws.cell(i, 1, t.to_pydatetime()).number_format = "yyyy-mm"
    ws.cell(i, 2, f"=YEAR(A{i})"); ws.cell(i, 3, f"=MONTH(A{i})")
    for j, cod in enumerate(cods, 4):
        v = row[cod]
        c = ws.cell(i, j, None if pd.isna(v) else round(float(v), 3)); c.fill = INP
mf = len(Qp) + 1
anchos(ws, [9, 6, 5] + [14] * N); ws.freeze_panes = "D2"

# 4. Caudal anual (fórmulas): sólo años con 12 meses válidos
ws = wb.create_sheet("Q_anual")
encabezado(ws, 1, ["Año"] + [f"{r.estacion.title()} ({r.codigo})" for r in est.itertuples()], 40)
for k, ano in enumerate(range(P0, P1 + 1)):
    i = k + 2
    ws.cell(i, 1, ano)
    f0, f1 = 2 + 12 * k, 13 + 12 * k
    for j in range(N):
        L = get_column_letter(4 + j)
        rng = f"Q_mensual!{L}{f0}:{L}{f1}"
        c = ws.cell(i, 2 + j, f'=IF(COUNT({rng})=12,AVERAGE({rng}),"")'); c.number_format = "0.0"
af = P1 - P0 + 2
anchos(ws, [6] + [14] * N); ws.freeze_panes = "B2"

# 5. Resumen
ws = wb.create_sheet("Resumen_Q")
cols = ["Código", "Estación", "Área (km²)", f"Años válidos {P0}–{P1}",
        "Q medio anual multianual (m³/s)", "Desv. estándar Q anual (m³/s)", "Coef. de variación (%)",
        "Q anual mínimo (m³/s)", "Q anual máximo (m³/s)", "Rendimiento q (L/s/km²)", "Lámina de escorrentía R (mm/año)",
        "Q medio registro completo (m³/s)"]
encabezado(ws, 1, cols, 48)
for j, r in enumerate(est.itertuples()):
    i = j + 2
    L = get_column_letter(2 + j)
    rng = f"Q_anual!{L}2:{L}{af}"
    vals = [r.codigo, r.estacion.title(), f"=Estaciones!N{i}", f"=COUNT({rng})", f"=AVERAGE({rng})",
            f"=STDEV({rng})", f"=F{i}/E{i}*100", f"=MIN({rng})", f"=MAX({rng})", f"=E{i}/C{i}*1000",
            f"=E{i}*{SEG_ANO:.0f}/(C{i}*1000000)*1000", round(r.Q_registro, 1)]
    for k, x in enumerate(vals, 1):
        c = ws.cell(i, k, x); c.border = BOX
        c.number_format = {3: "#,##0", 5: "0.0", 6: "0.0", 7: "0.0", 8: "0.0", 9: "0.0", 10: "0.0", 11: "0", 12: "0.0"}.get(k, "General")
        if k == 12:
            c.fill = INP
iv = int(est.index[est.codigo == "26237040"][0]) + 2
fila = N + 3
ws.cell(fila, 1, "Transferencia al punto de cierre (presa Hidroituango) por relación de áreas").font = BOLD
for k, (lab, f) in enumerate([
        ("Área cuenca hasta Hidroituango (km²)", A_CUENCA),
        ("Área Pto. Valdivia (km²)", f"=C{iv}"),
        ("Q medio Pto. Valdivia (m³/s)", f"=E{iv}"),
        ("Q medio estimado en Hidroituango (m³/s)", f"=B{fila + 3}*B{fila + 1}/B{fila + 2}"),
        ("Lámina de escorrentía en Hidroituango (mm/año)", f"=B{fila + 4}*{SEG_ANO:.0f}/(B{fila + 1}*1000000)*1000")], 1):
    ws.cell(fila + k, 1, lab).border = BOX
    c = ws.cell(fila + k, 2, f); c.border = BOX; c.number_format = "#,##0.0"
anchos(ws, [42, 16, 11, 10, 14, 13, 11, 11, 11, 12, 13, 14])

# 6. Ciclo anual (promedio mensual multianual)
ws = wb.create_sheet("Ciclo_anual")
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
encabezado(ws, 1, ["Mes", "N.º mes"] + [f"{r.estacion.title()}" for r in est.itertuples()], 32)
for m in range(12):
    i = m + 2
    ws.cell(i, 1, MESES[m]); ws.cell(i, 2, m + 1)
    for j in range(N):
        L = get_column_letter(4 + j)
        c = ws.cell(i, 3 + j, f"=AVERAGEIFS(Q_mensual!{L}2:{L}{mf},Q_mensual!$C$2:$C${mf},B{i})")
        c.number_format = "0.0"
anchos(ws, [6, 7] + [13] * N)

# 7. Figuras
ws = wb.create_sheet("Mapa")
img = XLImage(str(OUT / "mapa_estaciones_caudal_validadas.png")); img.width, img.height = 620, 930
ws.add_image(img, "A1")
img = XLImage(str(OUT / "disponibilidad_caudales.png")); img.width, img.height = 900, 585
ws.add_image(img, "M1")

wb.save(OUT / "Punto8_caudales_estaciones.xlsx")

# verificación en Python
ver = pd.DataFrame({"estacion": est.estacion.values, "area_km2": est.area_km2_DEM.values,
                    "anos": anual.count().values, "Q_medio": anual.mean().values}, index=cods)
ver["R_mm"] = ver.Q_medio * SEG_ANO / (ver.area_km2 * 1e6) * 1000
print(ver.round(1).to_string())
qv = ver.loc["26237040"]
print(f"Q Hidroituango por áreas: {qv.Q_medio * A_CUENCA / qv.area_km2:.1f} m3/s")
