"""
Punto 12 - Evaluación de los productos de precipitación mediante el balance hídrico de largo plazo (1981-2010).

Se repite el balance del punto 9 cambiando sólo la precipitación:
  P (IDEAM kriging | CHIRPS | ERA5-Land | ERA5)  →  φ = ETP/P  →  ETR Budyko celda a celda  →  Q_est = (P − ETR)·A
ETP (Hargreaves), áreas de drenaje y caudales observados son los mismos del punto 9.

Salidas: trabajo1/resultados/12_balance_productos/
    Punto12_balance_productos.xlsx (fórmulas vivas), balance_productos.csv, desempeno_productos.csv
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from rasterio.features import geometry_mask

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "trabajo1" / "resultados"
OUT = RES / "12_balance_productos"
OUT.mkdir(parents=True, exist_ok=True)
SEG = 365.25 * 86400


def leer(p):
    with rasterio.open(p) as s:
        a = s.read(1).astype("float64"); a[a == s.nodata] = np.nan
        return a, s.transform


ETP, aff = leer(RES / "08_etp_etr" / "ETP_anual_hargreaves_90m_3116.tif")
P = {"IDEAM": leer(RES / "04_precipitacion_interpolada" / "P_anual_kriging_90m_3116.tif")[0],
     "CHIRPS": leer(RES / "11_mapas_productos" / "P_CHIRPS_1981_2010_90m_3116.tif")[0],
     "ERA5-Land": leer(RES / "11_mapas_productos" / "P_ERA5_Land_1981_2010_90m_3116.tif")[0],
     "ERA5": leer(RES / "11_mapas_productos" / "P_ERA5_1981_2010_90m_3116.tif")[0]}


def budyko(p, etp):
    f = etp / p
    return p * np.sqrt(f * np.tanh(1 / f) * (1 - np.exp(-f)))


# unidades: las mismas del punto 9
b9 = pd.read_csv(RES / "09_balance" / "balance_subcuencas.csv", dtype={"codigo": str})
sub = gpd.read_file(RES / "06_caudales" / "subcuencas_estaciones.gpkg", layer="areas_drenaje")
cuenca = gpd.read_file(RES / "01_delimitacion" / "cuenca_cauca_hidroituango.gpkg", layer="cuenca")
geoms = {r.codigo: r.geometry for r in sub.itertuples()}
geoms["HIDRO"] = cuenca.geometry[0]
ca = abs(aff.a * aff.e) / 1e6

filas = []
for r in b9.itertuples():
    m = ~geometry_mask([geoms[r.codigo]], out_shape=ETP.shape, transform=aff)
    for prod, p in P.items():
        etr = budyko(p[m], ETP[m])
        filas.append({"codigo": r.codigo, "estacion": r.estacion, "producto": prod, "A": m.sum() * ca,
                      "P": np.nanmean(p[m]), "ETP": np.nanmean(ETP[m]), "ETR": np.nanmean(etr),
                      "Qobs": r._8, "Qrel": r._9})
bp = pd.DataFrame(filas)
bp["R"] = bp.P - bp.ETR
bp["Qest"] = bp.R / 1000 * bp.A * 1e6 / SEG
bp["err"] = 100 * (bp.Qest / bp.Qobs - 1)
bp.to_csv(OUT / "balance_productos.csv", index=False, encoding="utf-8-sig")
est = bp[bp.codigo != "HIDRO"]
des = est.groupby("producto", sort=False).agg(sesgo=("err", "mean"), MAE=("err", lambda e: e.abs().mean()),
                                              RMSE=("err", lambda e: np.sqrt((e ** 2).mean())),
                                              r=("Qest", lambda q: np.corrcoef(q, est.loc[q.index, "Qobs"])[0, 1]))
des.to_csv(OUT / "desempeno_productos.csv", encoding="utf-8-sig")
pd.set_option("display.width", 220)
print(bp[bp.codigo == "HIDRO"][["producto", "P", "ETP", "ETR", "R", "Qest", "Qobs", "Qrel", "err"]].round(1).to_string(index=False))
print(bp.pivot(index="estacion", columns="producto", values="err").loc[b9.estacion, list(P)].round(1).to_string())
print(des.round(2).to_string())

# ----------------------------------------------------------------------------- Excel
wb = Workbook()
H = Font(bold=True, color="FFFFFF"); HF = PatternFill("solid", fgColor="1F4E79"); BOLD = Font(bold=True)
thin = Side(style="thin", color="BBBBBB"); BOX = Border(top=thin, bottom=thin, left=thin, right=thin)
INP = PatternFill("solid", fgColor="FFF2CC")


def encabezado(ws, fila, cols, alto=40):
    for j, c in enumerate(cols, 1):
        x = ws.cell(fila, j, c); x.font = H; x.fill = HF; x.border = BOX
        x.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
    ws.row_dimensions[fila].height = alto


ws = wb.active; ws.title = "Metodologia"
for i, (t, f) in enumerate([
        ("PUNTO 12 — EVALUACIÓN DE LOS PRODUCTOS DE PRECIPITACIÓN MEDIANTE EL BALANCE HÍDRICO (1981–2010)", BOLD),
        ("Se repite el balance del punto 9 cambiando sólo la precipitación: IDEAM (kriging), CHIRPS v2.0 (IRI Data Library), ERA5-Land y ERA5. CHIRPS v3.0 (Drive del curso) se evalúa como sensibilidad en resultados/12_balance_productos/chirps_v2.", None),
        ("P de cada producto: promedio 1981–2010 llevado a la grilla de 90 m (vecino más cercano, punto 11).", None),
        ("ETP: Hargreaves (punto 6), la misma para todos.  ETR: Budyko celda a celda con la P de cada producto.", None),
        ("R = P − ETR ;  Q_est = R·A / 31 557 600 s.  Error = (Q_est − Q_obs) / Q_obs.", None),
        ("Q_obs: caudal medio anual 1981–2010 de años completos (punto 8). En el cierre, Pto. Valdivia transferido por áreas; "
         "con Pte. Pescadero rellenada el caudal sería 1020 m³/s.", None),
        ("P, ETP y ETR son promedios de las celdas de 90 m del área de drenaje (datos de entrada, amarillo); el resto son fórmulas.", None)], 1):
    c = ws.cell(i, 1, t)
    if f:
        c.font = f
ws.column_dimensions["A"].width = 140

# tabla del enunciado (cierre)
ws = wb.create_sheet("Tabla_punto12")
encabezado(ws, 1, ["Producto", "P anual (mm/año)", "ETR (mm/año)", "Q estimado (mm/año)", "Q observado (mm/año)", "Error (%)",
                   "Q estimado (m³/s)", "Q observado (m³/s)", "A (km²)"])
hid = bp[bp.codigo == "HIDRO"].reset_index(drop=True)
for i, r in enumerate(hid.itertuples(), 2):
    vals = [r.producto, round(r.P, 1), round(r.ETR, 1), f"=B{i}-C{i}", f"=H{i}*{SEG:.0f}/(I{i}*1000000)*1000", f"=(D{i}/E{i}-1)*100",
            f"=D{i}/1000*I{i}*1000000/{SEG:.0f}", round(r.Qobs, 2), round(r.A, 1)]
    for j, x in enumerate(vals, 1):
        c = ws.cell(i, j, x); c.border = BOX; c.number_format = "0.0" if j > 1 else "General"
        if j in (2, 3, 8, 9):
            c.fill = INP
ws.cell(7, 1, "Cuenca del río Cauca hasta la presa de Hidroituango (35 992 km²), 1981–2010. Q observado: Pto. Valdivia transferido "
        "por relación de áreas.").font = Font(italic=True)
for j, w in enumerate([12, 12, 12, 13, 13, 10, 12, 12, 10], 1):
    ws.column_dimensions[get_column_letter(j)].width = w

# balance por estación y producto
ws = wb.create_sheet("Balance_estaciones")
encabezado(ws, 1, ["Código", "Área de drenaje", "Producto", "A (km²)", "P (mm/año)", "ETP (mm/año)", "φ = ETP/P", "ETR (mm/año)",
                   "R = P − ETR (mm/año)", "Q estimado (m³/s)", "Q observado (m³/s)", "Error (%)"])
for i, r in enumerate(bp.itertuples(), 2):
    vals = [r.codigo, r.estacion, r.producto, round(r.A, 1), round(r.P, 1), round(r.ETP, 1), f"=F{i}/E{i}", round(r.ETR, 1),
            f"=E{i}-H{i}", f"=I{i}/1000*D{i}*1000000/{SEG:.0f}", round(r.Qobs, 2), f"=(J{i}/K{i}-1)*100"]
    for j, x in enumerate(vals, 1):
        c = ws.cell(i, j, x); c.border = BOX
        c.number_format = "0.00" if j == 7 else ("0.0" if j > 3 else "General")
        if j in (4, 5, 6, 8, 11):
            c.fill = INP
nf = len(bp) + 1
for j, w in enumerate([10, 22, 11, 9, 10, 10, 8, 10, 11, 11, 11, 9], 1):
    ws.column_dimensions[get_column_letter(j)].width = w
ws.freeze_panes = "D2"

ws = wb.create_sheet("Desempeno")
encabezado(ws, 1, ["Producto", "Sesgo medio (%)", "Error absoluto medio (%)", "RMSE relativo (%)", "Correlación Q est–Q obs"])
for i, prod in enumerate(P, 2):
    crit = f'Balance_estaciones!$C$2:$C${nf},"{prod}",Balance_estaciones!$A$2:$A${nf},"<>HIDRO"'
    rngE = f"Balance_estaciones!$L$2:$L${nf}"
    vals = [prod, f"=AVERAGEIFS({rngE},{crit})", round(des.loc[prod, "MAE"], 2), round(des.loc[prod, "RMSE"], 2), round(des.loc[prod, "r"], 4)]
    for j, x in enumerate(vals, 1):
        c = ws.cell(i, j, x); c.border = BOX; c.number_format = "0.0" if j in (2, 3, 4) else ("0.000" if j == 5 else "General")
ws.cell(7, 1, "Estadísticos sobre las 9 estaciones (sin el cierre). MAE, RMSE y r calculados en Python (los rangos condicionales no "
        "admiten ABS/SUMSQ sin fórmulas matriciales).").font = Font(italic=True)
for j, w in enumerate([12, 12, 14, 12, 14], 1):
    ws.column_dimensions[get_column_letter(j)].width = w
wb.save(OUT / "Punto12_balance_productos.xlsx")
print("Excel guardado")
