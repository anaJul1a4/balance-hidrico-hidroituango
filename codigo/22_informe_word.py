"""
Informe escrito (Word) del Trabajo 1 — balance hídrico de largo plazo de la cuenca aportante a Hidroituango (1981–2010).

Por cada punto de la rúbrica: datos y metodología, resultados, interpretación y decisiones propias. Incluye una sección con
todos los análisis adicionales (aplicados y no aplicados) y las conclusiones. Las tablas se leen de resultados/ y las figuras
son los PNG de los scripts 01–21.

Salida: trabajo1/informe_word/Informe_Trabajo1_Hidroituango.docx
"""
import io
import re
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from docx import Document
from docx.enum.section import WD_ORIENT  # noqa: F401
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "resultados"
OUT = ROOT / "informe_word"
OUT.mkdir(exist_ok=True)

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.59), Cm(27.94)
sec.left_margin = sec.right_margin = Cm(2.5); sec.top_margin = sec.bottom_margin = Cm(2.2)
ANCHO = 16.5

st = doc.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(11)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
st.paragraph_format.space_after = Pt(6); st.paragraph_format.line_spacing = 1.15
for n, s, c in [("Heading 1", 15, "1F4E79"), ("Heading 2", 12.5, "1F4E79"), ("Heading 3", 11, "2E5C8A")]:
    h = doc.styles[n]; h.font.name = "Calibri"; h.font.size = Pt(s); h.font.color.rgb = RGBColor.from_string(c)
    h.paragraph_format.space_before = Pt(14 if n == "Heading 1" else 10); h.paragraph_format.space_after = Pt(4)
cap = doc.styles["Caption"]; cap.font.size = Pt(9); cap.font.italic = False; cap.font.color.rgb = RGBColor(0x40, 0x40, 0x40)

NF, NT = [0], [0]


def runs(p, texto):
    """**negrita**, *cursiva*, x_{sub}, x^{sup}."""
    for parte in re.split(r"(\*\*.+?\*\*|\*.+?\*|_\{.+?\}|\^\{.+?\})", texto):
        if not parte:
            continue
        if parte.startswith("**"):
            p.add_run(parte[2:-2]).bold = True
        elif parte.startswith("*"):
            p.add_run(parte[1:-1]).italic = True
        elif parte.startswith("_{"):
            p.add_run(parte[2:-1]).font.subscript = True
        elif parte.startswith("^{"):
            p.add_run(parte[2:-1]).font.superscript = True
        else:
            p.add_run(parte)
    return p


def P(texto, estilo=None, just=True):
    p = runs(doc.add_paragraph(style=estilo), texto)
    if just and estilo is None:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return p


def B(items, num=False):
    for t in items:
        runs(doc.add_paragraph(style="List Number" if num else "List Bullet"), t)


def H(t, n=1):
    doc.add_heading(t, n)


def EC(texto):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(texto); r.font.name = "Cambria Math"; r.italic = True; r.font.size = Pt(11.5)


def sombrear(celda, color):
    tc = celda._tc.get_or_add_tcPr(); s = OxmlElement("w:shd")
    s.set(qn("w:val"), "clear"); s.set(qn("w:color"), "auto"); s.set(qn("w:fill"), color); tc.append(s)


def T(titulo, filas, encabezado, anchos=None, nota=None, fs=9):
    NT[0] += 1
    c = doc.add_paragraph(style="Caption"); c.add_run(f"Tabla {NT[0]}. ").bold = True; runs(c, titulo)
    c.paragraph_format.keep_with_next = True
    t = doc.add_table(rows=1, cols=len(encabezado)); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, e in enumerate(encabezado):
        cel = t.rows[0].cells[j]; cel.text = ""; r = cel.paragraphs[0].add_run(e); r.bold = True; r.font.size = Pt(fs)
        r.font.color.rgb = RGBColor(255, 255, 255); sombrear(cel, "1F4E79")
    for i, f in enumerate(filas):
        cs = t.add_row().cells
        for j, v in enumerate(f):
            cs[j].text = ""; par = cs[j].paragraphs[0]; runs(par, str(v))
            for r in par.runs:
                r.font.size = Pt(fs)
            if j > 0 and re.fullmatch(r"[−\-+]?[\d\s.,]+%?", str(v).strip() or "x"):
                par.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            if i % 2:
                sombrear(cs[j], "EEF3F8")
    if anchos:
        for row in t.rows:
            for j, w in enumerate(anchos):
                row.cells[j].width = Cm(w)
    if nota:
        n = doc.add_paragraph(style="Caption"); runs(n, nota)
    else:
        doc.add_paragraph().paragraph_format.space_after = Pt(2)


def F(ruta, titulo, ancho=ANCHO):
    NF[0] += 1
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.keep_with_next = True
    im = Image.open(RES / ruta).convert("RGB")
    if max(im.size) > 2000:  # 2000 px bastan a 16 cm (≈ 300 ppp) y mantienen el .docx liviano
        im.thumbnail((2000, 2000), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=88); buf.seek(0)
    p.add_run().add_picture(buf, width=Cm(ancho))
    c = doc.add_paragraph(style="Caption"); c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    c.add_run(f"Figura {NF[0]}. ").bold = True; runs(c, titulo)
    return NF[0]


def campo(p, instr):
    r = p.add_run()
    for tipo, txt in [("begin", None), (None, instr), ("separate", None), (None, None), ("end", None)]:
        if tipo:
            e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), tipo); r._r.append(e)
        elif txt:
            e = OxmlElement("w:instrText"); e.set(qn("xml:space"), "preserve"); e.text = txt; r._r.append(e)
    return r


def DEC(filas):
    T("Decisiones metodológicas de este punto", [[a, b] for a, b in filas], ["Decisión", "Justificación"], [4.5, 12])


def num(x, d=0):
    return f"{x:,.{d}f}".replace(",", " ").replace("-", "−")


# ----------------------------------------------------------------------------- datos
morf = pd.read_csv(RES / "01_delimitacion" / "parametros_morfometricos.csv", index_col=0).iloc[:, 0]
cv = pd.read_csv(RES / "04_precipitacion_interpolada" / "validacion_cruzada.csv", index_col=0)
tz = pd.read_csv(RES / "05_temperatura_elevacion" / "coeficientes_T_Z.csv", index_col=0)
tres = pd.read_csv(RES / "07_mapas_temperatura" / "resumen_temperatura.csv", index_col=0)
pis = pd.read_csv(RES / "15_complementarias" / "pisos_termicos.csv")
bal = pd.read_csv(RES / "09_balance" / "balance_subcuencas.csv", dtype={"codigo": str})
bp = pd.read_csv(RES / "12_balance_productos" / "balance_productos.csv", dtype={"codigo": str})
des = pd.read_csv(RES / "12_balance_productos" / "desempeno_productos.csv", index_col=0)
rp = pd.read_csv(RES / "11_mapas_productos" / "resumen_productos.csv", index_col=0)
mc = pd.read_csv(RES / "14_ciclo_productos" / "metricas_ciclo.csv", index_col=0)
cic = pd.read_csv(RES / "13_climatologia" / "ciclo_anual.csv")
pp = pd.read_csv(RES / "15_complementarias" / "punto_a_pixel_metricas.csv", index_col=0)
bud = pd.read_csv(RES / "15_complementarias" / "budyko_estaciones_productos.csv", dtype={"codigo": str})
v23 = pd.read_csv(RES / "12_balance_productos" / "chirps_v2" / "balance_chirps_v2_v3.csv", dtype={"codigo": str})
qa = pd.read_csv(RES / "15_complementarias" / "Q_anual_estaciones.csv", index_col=0)
A = morf["Área (km²)"]

# compuestos ENSO: anomalía anual de Q (estaciones) y de P (CHIRPS v2.0, cuenca) respecto a 1981–2010
sys.path.insert(0, str(Path(__file__).parent))
from productos import abrir  # noqa: E402
_cu = gpd.read_file(RES / "01_delimitacion" / "cuenca_cauca_hidroituango.gpkg", layer="cuenca").to_crs(4326).geometry[0]
_p = abrir("CHIRPS").precip
_m = shapely.contains_xy(_cu, *np.meshgrid(_p.lon.values, _p.lat.values))
p_anual = _p.groupby("time.year").sum("time", min_count=12).where(_m).mean(["lat", "lon"]).to_series()
NINO, NINA = [1983, 1987, 1992, 1998, 2003, 2010], [1989, 1999, 2000, 2008, 2011]


def compuesto(c):
    m = c.loc[1981:2010].mean()
    a = lambda ys: np.array([100 * (c.get(y, np.nan) / m - 1) for y in ys])  # noqa: E731
    n, l = a(NINO), a(NINA)
    return np.nanmean(n), (~np.isnan(n)).sum(), np.nanmean(l), (~np.isnan(l)).sum(), 100 * c.loc[1981:2010].std() / m


enso = {"P cuenca (CHIRPS v2.0)": compuesto(p_anual)}
enso.update({k: compuesto(qa[k]) for k in ["La Balsa", "Juanchito", "La Victoria", "La Virginia", "Irra", "La Pintada",
                                          "Puente Iglesias", "Bolombolo", "Cañafisto", "Puerto Valdivia"]})
sg = lambda x: f"{x:+.0f}".replace("-", "−")  # noqa: E731
enso_filas = [[("Q " if not k.startswith("P ") else "") + k, f"{sg(v[0])} (n = {v[1]})", f"{sg(v[2])} (n = {v[3]})", f"{v[4]:.0f}"]
              for k, v in enso.items()]
_cvq = [v[4] for k, v in enso.items() if not k.startswith("P ")]
cv_p, cv_q_min, cv_q_max, cv_q_med = enso["P cuenca (CHIRPS v2.0)"][4], min(_cvq), max(_cvq), float(np.median(_cvq))
_F = lambda f: np.sqrt(f * np.tanh(1 / f) * (1 - np.exp(-f)))  # noqa: E731
eps_b = 1 + 0.71 * (_F(0.71 + 1e-5) - _F(0.71 - 1e-5)) / 2e-5 / (1 - _F(0.71))
amp = cv_q_med / cv_p
_qn = [v[0] for k, v in enso.items() if not k.startswith("P ")]; _ql = [v[2] for k, v in enso.items() if not k.startswith("P ")]
rango_nino = f"{sg(max(_qn))} a {sg(min(_qn))} %"; rango_nina = f"{sg(min(_ql))} a {sg(max(_ql))} %"
_pv = qa["Puerto Valdivia"].dropna(); q2011, n_pv = _pv[2011], len(_pv); rk2011 = int(_pv.rank(ascending=False)[2011])

# ============================================================================= portada
for _ in range(5):
    doc.add_paragraph()
for t, s, b in [("Universidad Nacional de Colombia", 13, False), ("Hidroclimatología · Trabajo 1", 13, False), ("", 10, False),
                ("Balance hídrico de largo plazo de la cuenca aportante a Hidroituango", 22, True),
                ("Río Cauca hasta la presa de Hidroituango · 1981–2010", 14, False), ("", 30, False),
                ("Juliana Aguirre", 12, True), ("Octubre de 2026", 11, False)]:
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(t); r.font.size = Pt(s); r.bold = b
    if s == 22:
        r.font.color.rgb = RGBColor.from_string("1F4E79")
p = doc.add_paragraph(); p.add_run().add_break(WD_BREAK.PAGE)

doc.add_heading("Contenido", 1)
campo(doc.add_paragraph(), 'TOC \\o "1-2" \\h \\z \\u')
doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

# ============================================================================= resumen
H("Resumen")
P(f"Se estimó el balance hídrico de largo plazo (1981–2010) de la cuenca del río Cauca hasta la presa de Hidroituango "
  f"({num(A)} km²) como Q = P − ETR, con ΔS ≈ 0. Con la precipitación de 266 estaciones del IDEAM interpolada por kriging "
  f"(P = 1985 mm/año), la ETP de Hargreaves-Samani (1409 mm/año) y la ETR de Budyko celda a celda (1085 mm/año), la escorrentía es "
  f"R = 900 mm/año (1026 m³/s). En el cierre, este valor queda a −5.3 % del caudal observado (1084 m³/s, Puerto Valdivia transferido "
  f"por áreas). En las 9 estaciones de caudal del río Cauca el error va de −7 % a +7 % (error absoluto medio 4.5 %).")
P("Se repitió el balance con tres productos de precipitación. CHIRPS v2.0 reproduce la lluvia del IDEAM:")
B(["P = 2026 mm/año (+2 %) y correlación espacial 0.89.",
   "Error de cierre −2.2 % y correlación del ciclo anual 0.998."])
P("ERA5 y ERA5-Land triplican la lluvia de la cuenca (≈ 5970 mm/año). Su balance sobrestima el caudal en ≈ +390 %, y "
  "cerrarlo exigiría reducir su P entre 47 % y 74 %.")
P("El régimen de lluvias es bimodal en el 99.8 % del área:")
B(["Máximos: octubre (240 mm) y abril (218 mm).",
   "Mínimos: agosto (114 mm) y febrero (120 mm)."])
P("**CHIRPS v2.0 es el único producto apto para balances en esta cuenca. ERA5 y ERA5-Land no deben usarse sin corrección "
  "de sesgo.**")
P("**Palabras clave:** balance hídrico, Budyko, Hargreaves-Samani, kriging, CHIRPS, ERA5, río Cauca, Hidroituango.")

# ============================================================================= 1. selección
H("1. Selección de la cuenca (punto 1)")
P(f"Se eligió la **cuenca aportante a Hidroituango**: el río Cauca desde su nacimiento en el Macizo Colombiano (≈ 3400 m) hasta "
  f"la presa (7.136° N, 75.663° W, ≈ 244 m). Tiene {num(A)} km² entre las cordilleras Occidental y Central, en siete departamentos. "
  "No es la cuenca completa del Cauca, que sigue hasta el Magdalena y la estudia otro equipo. El punto de cierre es la presa, y el "
  "nombre «cuenca aportante a Hidroituango» evita confundirlas.")
P("**Importancia para el sector hidroeléctrico.** Cerca de dos tercios de la electricidad de Colombia es de origen hidráulico. "
  "Hidroituango es la central más grande del país: 2400 MW en ocho unidades de 300 MW, con energía para cerca del 17 % de la "
  "población (Alcaldía de Medellín, s. f.). Su generación depende del caudal que llega a la presa, que el proyecto reporta en "
  "1010–1100 m³/s. El balance de largo plazo dice "
  "cuánta agua aporta la cuenca en un año medio, qué zonas la producen y cuáles la consumen, y qué tan confiables son los datos "
  "con que se estima la energía firme.")
P("Otros usos compiten por el agua: el embalse de Salvajina en el alto Cauca, el acueducto de Cali y el riego de caña en el Valle. "
  "Además, la cuenca es un caso exigente para el método. Combina un valle plano y seco a la sombra de lluvia, laderas muy húmedas y "
  "páramos, con gradientes fuertes de lluvia y temperatura en pocas decenas de kilómetros.")

# ============================================================================= 2. datos
H("2. Datos utilizados")
T("Fuentes de información", [
    ["Elevación", "Copernicus GLO-30 (ESA, 2021), 14 teselas", "30 m → 90 m", "—", "Delimitación, drenajes, mapas de T"],
    ["Precipitación", "IDEAM, promedios climatológicos 1981–2010", "266 estaciones", "1981–2010", "Mapa de P (punto 3)"],
    ["Temperatura", "IDEAM, promedios climatológicos 1981–2010", "47 estaciones", "1981–2010", "Regresiones T–Z (punto 4)"],
    ["ETP de referencia", "IDEAM, promedios climatológicos", "244 estaciones", "1981–2010", "Contraste de Hargreaves"],
    ["Caudal", "IDEAM, HidrologiaNacionalDiaria (Q medio diario)", "12 estaciones del Cauca", "1960–2025", "Validación (puntos 8–9)"],
    ["Catálogo", "IDEAM, Catálogo Nacional de Estaciones (datos.gov.co)", "—", "—", "Coordenadas y elevación"],
    ["CHIRPS v2.0", "Funk et al. (2015), IRI Data Library", "0.05°", "1981–2025", "Producto principal (puntos 10–14)"],
    ["CHIRPS v3.0", "Climate Hazards Center, Drive del curso", "0.05°", "1981–2025", "Sensibilidad"],
    ["ERA5-Land", "Muñoz-Sabater et al. (2021), Drive del curso", "0.1°", "1981–2025", "Puntos 10–14"],
    ["ERA5", "Hersbach et al. (2020), Drive del curso", "0.25°", "1981–2025", "Puntos 10–14"]],
  ["Variable", "Fuente", "Resolución / n", "Periodo", "Uso"], [2.6, 5.6, 2.6, 2, 3.7])
P("**Periodo común 1981–2010.** Es el periodo de la climatología oficial del IDEAM, de la que salen P y T. Lo comparten los cuatro "
  "productos de precipitación, y es anterior al llenado del embalse (2019), así que los caudales no están afectados por Hidroituango. "
  "Todos los mapas están en MAGNA-SIRGAS / Colombia Bogotá (EPSG:3116), en una grilla común de 90 m.")
P("El procesamiento se hizo en Python 3.13: pysheds, rasterio, geopandas, xarray, scipy, numba y matplotlib. Los cálculos de los "
  "puntos 4, 8, 9 y 12 están además en libros de Excel con fórmulas vivas.")

# ============================================================================= 3. delimitación
H("3. Delimitación de la cuenca (punto 2)")
H("Metodología", 2)
B(["El DEM GLO-30 se reproyectó a EPSG:3116 y se promedió a 90 m (≈ 4.4 millones de celdas en la cuenca).",
   "Se rellenaron las depresiones con **Priority-Flood + ε** (Barnes et al., 2014), implementado en numba. Las direcciones de "
   "flujo se calcularon con D8 y luego el área acumulada.",
   "La cuenca se delimitó aguas arriba de la celda del cauce más cercana a la presa.",
   "La red de drenaje son las celdas con más de 25 km² acumulados, clasificadas por orden de Strahler.",
   "El río principal se trazó desde el cierre hacia arriba, siguiendo en cada confluencia el tributario de mayor área."])
H("Resultados", 2)
T("Parámetros morfométricos", [
    ["Área", f"{num(A)} km²"], ["Perímetro", f"{num(morf['Perímetro (km)'])} km"],
    ["Coeficiente de compacidad de Gravelius Kc", f"{morf['Coef. compacidad Gravelius Kc']:.2f}"],
    ["Factor de forma Kf = A/L²", f"{morf['Factor de forma Kf = A/L²']:.3f}"],
    ["Longitud del río principal", f"{num(morf['Long. río principal (km)'])} km"],
    ["Pendiente media del río principal", f"{morf['Pendiente media río principal (%)']:.2f} %"],
    ["Elevación mínima / media / máxima", f"{num(morf['Elevación mínima cuenca (m)'])} / {num(morf['Elevación media cuenca (m)'])} / "
                                          f"{num(morf['Elevación máxima cuenca (m)'])} m"],
    ["Longitud total de drenajes / densidad", f"{num(morf['Long. total de drenajes (km)'])} km / {morf['Densidad de drenaje (km/km²)']:.2f} km/km²"],
    ["Orden de Strahler máximo (umbral 25 km²)", "5"]], ["Parámetro", "Valor"], [9, 7.5])
F("01_delimitacion/mapa_cuenca_cauca_hidroituango.png", "Cuenca aportante a Hidroituango: DEM GLO-30, límite, red de drenaje "
  "(Strahler), río principal, punto de cierre, norte, escala y sistema de coordenadas (EPSG:3116).", 12)
P("El punto de cierre quedó a 178 m de la coordenada publicada de la presa. Incluye el río San Andrés, que desemboca 7 km aguas "
  "arriba, y excluye el río Ituango, que entra 0.5 km aguas abajo. El área difiere en 0.4 % de la de HydroSHEDS (Lehner et al., "
  "2008; 35 841 km²).")
H("Interpretación", 2)
P(f"Kc = {morf['Coef. compacidad Gravelius Kc']:.2f} y Kf = {morf['Factor de forma Kf = A/L²']:.2f} describen una cuenca muy "
  "alargada (855 km de río por unos 40 km de ancho medio). Las crecientes de la cabecera tardan días en llegar a la presa y se "
  "atenúan en el recorrido.")
P("El perfil tiene tres tramos:")
B(["Una caída fuerte en el Macizo.",
   "Un tramo casi plano en el Valle del Cauca, de ≈ 950 m de altura a lo largo de 400 km.",
   "El descenso continuo del cañón antioqueño hasta la presa."])
DEC([("GLO-30 y no el DEM de 900 m del curso", "una celda de 932 m suaviza el relieve y escalona el límite; GLO-30 es el DEM global más exacto."),
     ("Celda de 90 m", "a 30 m serían ≈ 40 millones de celdas sin cambio apreciable en el límite; 90 m es la grilla común de todos los mapas."),
     ("Priority-Flood + ε propio", "el relleno de planos de pysheds cortaba el flujo en la planicie del Valle y dejaba la cuenca en ≈ 20 000 km²."),
     ("Umbral de 25 km²", "da una red legible a escala de cuenca (orden 5) sin cauces espurios en las laderas.")])

# ============================================================================= 4. precipitación
H("4. Precipitación media anual con estaciones IDEAM (punto 3)")
H("Datos y metodología", 2)
P("Se usaron 266 estaciones IDEAM con promedio climatológico 1981–2010:")
B(["259 dentro de la cuenca o en su vecindario de 20 km.",
   "7 de la zona hidrográfica 26 (Cauca) que cubren los bordes."])
P("Se excluyó Briceño (6455 mm/año). Es un valor atípico, el doble de cualquier vecina, y crearía un núcleo de lluvia irreal en el "
  "cañón.")
P("Se compararon dos interpoladores con **validación cruzada dejando una estación fuera** (LOO), cada uno con varias configuraciones:")
B(["IDW con potencias 1 a 3.",
   "Kriging ordinario con variogramas esférico, exponencial y gaussiano."])
P("El variograma se ajustó por mínimos cuadrados ponderados con los **pesos de Cressie** (1985), que dan más peso a los pares "
  "cercanos y a las clases con más pares. Con el ajuste sin ponderar, la pepita salía en cero.")
T("Validación cruzada (dejando una estación fuera, n = 266)",
  [[k, num(r["RMSE (mm)"]), num(r["MAE (mm)"]), num(r["Sesgo (mm)"], 1), f"{r['R2']:.3f}", f"{r['r']:.3f}"] for k, r in cv.iterrows()],
  ["Método", "RMSE (mm)", "MAE (mm)", "Sesgo (mm)", "R²", "r"], [5.5, 2.2, 2.2, 2.2, 2.2, 2.2])
F("03_estaciones_precipitacion/mapa_estaciones_precipitacion.png", "Estaciones de precipitación IDEAM consideradas, coloreadas por "
  "su P media anual 1981–2010.", 12)
F("04_precipitacion_interpolada/variograma_validacion_cruzada.png", "Variograma experimental y modelo gaussiano ajustado (pesos de "
  "Cressie); validación cruzada de los métodos.", 16)
H("Resultados", 2)
P("Se eligió el **kriging ordinario con variograma gaussiano**: pepita 71 849 mm², meseta parcial 266 389 mm² y rango 66.3 km. Es el "
  "de menor RMSE (363 mm), aunque IDW p = 1.5 queda muy cerca (364 mm). La P media de la cuenca es **1985 mm/año**, entre 872 mm "
  "(fondo del Valle) y 3441 mm (vertientes húmedas). Equivale a un volumen de 71.5 km³/año, o 2264 m³/s.")
F("04_precipitacion_interpolada/mapa_precipitacion_media_anual.png", "Precipitación media anual 1981–2010 por kriging ordinario "
  "(estaciones IDEAM). Escala de color común a todos los mapas de precipitación anual del informe.", 12)
H("Interpretación", 2)
P("La lluvia la organiza la orografía. El fondo del Valle del Cauca, entre Cali y Cartago, recibe menos de 1200 mm porque está a la "
  "sombra de lluvia de la cordillera Occidental. Las laderas que miran al valle superan 2500 mm. En el cañón antioqueño, aguas "
  "abajo de La Pintada, la lluvia vuelve a subir hacia la presa.")
P("La elevación no sirve como predictor directo de P: r = 0.18 (Pearson) y ρ = 0.30 (Spearman). Por eso se interpoló sin deriva "
  "externa.")
P("La pepita es el 21 % de la meseta. Indica variabilidad a escalas menores que la separación entre estaciones (núcleos "
  "convectivos y efectos de ladera), que ninguna interpolación puede resolver. Con un RMSE de 363 mm (≈ 18 % de la media), P es la "
  "mayor fuente de incertidumbre del balance.")
P("**Contraste con estudios previos.** El método coincide con el de los mapas nacionales de la Universidad Nacional:")
B(["Mejía et al. (1999) interpolaron la lluvia de Colombia con kriging ordinario para los meses y kriging con deriva externa para "
   "la media anual.",
   "Poveda et al. (2007) usaron kriging universal, con mapas de expertos como tendencia."])
P("Aquí la elevación no aportaba como deriva, así que el kriging ordinario es la opción coherente. El patrón obtenido también "
  "concuerda con los mecanismos que describen Hoyos et al. (2018): la humedad del Pacífico, traída por el chorro del occidente, "
  "converge sobre el occidente colombiano. Esa convergencia, junto con el ascenso orográfico, explica las laderas húmedas que "
  "rodean el Valle seco.")
DEC([("Kriging gaussiano", "menor RMSE en validación cruzada; da además la varianza de estimación (σ media 300 mm)."),
     ("Pesos de Cressie", "el ajuste sin ponderar daba pepita 0, un variograma que no representa la escala local."),
     ("Excluir Briceño", "6455 mm/año, el doble de sus vecinas; con ella la media de la cuenca sube 7 mm y aparece un núcleo irreal."),
     ("Vecindario de 20 km + zona 26", "evita bordes extrapolados sin traer estaciones de otras vertientes (Pacífico, Magdalena)."),
     ("Sensibilidad: 358 estaciones", "con todas las estaciones del mapa de estaciones, P = 1994 mm (+0.4 %), pero el RMSE sube a 560 mm.")])

# ============================================================================= 5. T–Z
H("5. Regresiones temperatura–elevación (punto 4)")
H("Datos y metodología", 2)
P("Se usaron las **47 estaciones** IDEAM de la cuenca con normales 1981–2010 de Tmax, Tmin y Tmed a la vez. Usar el mismo conjunto "
  "en las tres variables hace las ecuaciones comparables. Cada variable se ajustó por mínimos cuadrados ordinarios con el modelo:")
EC("T = T₀ − α·Z")
P("Para cada ajuste se reportan el intervalo de confianza del 95 % de la pendiente y los residuos estudentizados. Las estaciones con "
  "|residuo| > 2.5 se marcaron como atípicas, pero no se eliminaron. También se ajustaron las 12 regresiones mensuales, que se usan "
  "en la ETP del punto 6.")
H("Resultados", 2)
ic = {"Tmax": 0.29, "Tmin": 0.33, "Tmed": 0.23}
T("Regresiones lineales T = T₀ − α·Z (Z en m, T en °C)",
  [[k, f"T = {r['T0']:.2f} − {r['alfa']:.5f}·Z", f"{r['alfa_km']:.2f} ± {ic[k]:.2f}", f"{r['R2']:.3f}", f"{r['s']:.2f}", f"{r['n']:.0f}"]
   for k, r in tz.loc[["Tmax", "Tmed", "Tmin"]].iterrows()],
  ["Variable", "Ecuación", "α (°C/km, IC 95 %)", "R²", "Error típico (°C)", "n"], [2, 5.6, 3.2, 1.6, 2.4, 1.2])
F("05_temperatura_elevacion/diagramas_T_Z.png", "Diagramas de dispersión T–Z con la recta ajustada, la ecuación, α, R² y n.", 16)
H("Interpretación", 2)
P("La elevación explica más del 96 % de la varianza espacial de la temperatura. Es el comportamiento esperado en los Andes "
  "tropicales, donde la variación latitudinal es pequeña.")
P("**Tmed.** El gradiente es de 6.4 °C/km, prácticamente el de la atmósfera estándar (6.5 °C/km).")
P("**Tmax y Tmin.** Tmax baja más rápido que Tmin: 7.3 frente a 5.7 °C/km. Por eso la amplitud diaria se reduce con la altura: es "
  "de 12.6 °C a nivel del mar y de 7.7 °C a 3000 m. Esa amplitud entra en Hargreaves como (Tmax − Tmin)^{0.5}, así que la ETP "
  "disminuye con la altura por dos vías: menos temperatura y menos amplitud.")
P("Los residuos mayores corresponden sobre todo a estaciones cuya elevación de catálogo difiere de la del DEM en su coordenada.")
P("**Contraste con estudios previos.** Para Colombia, Eslava (1992) y Chaves y Jaramillo (1999) ajustaron ecuaciones de temperatura "
  "con la altitud por regiones. Ambos encontraron que la temperatura a nivel del mar y el gradiente cambian de una región a otra. "
  "Por eso aquí se ajustó una ecuación propia de la cuenca en vez de usar valores nacionales. El gradiente de Tmed (6.4 °C/km) está "
  "en el rango típico de la región andina.")
DEC([("Mismas 47 estaciones en las tres variables", "ecuaciones comparables entre sí y amplitud Tmax − Tmin coherente."),
     ("Atípicos marcados, no eliminados", "con 47 estaciones, quitar puntos cambia el gradiente sin una razón física clara para hacerlo."),
     ("Una regresión para toda la cuenca", "con 47 estaciones no hay soporte para regresiones por subregión; R² > 0.96 lo justifica.")])

# ============================================================================= 6. mapas T
H("6. Mapas de temperatura (punto 5)")
P("Cada mapa resulta de aplicar su ecuación T–Z a cada celda de 90 m del DEM. Los tres mapas usan la misma escala de color, de −6 a "
  "36 °C, para poder compararlos.")
F("07_mapas_temperatura/mapas_temperatura_panel.png", "Temperatura máxima, media y mínima anual a partir del DEM y las regresiones "
  "T–Z (misma escala de color en los tres paneles).", 16.5)
T("Temperatura de la cuenca (°C)", [[k, f"{r['media cuenca (°C)']:.1f}", f"{r['mínimo (°C)']:.1f}", f"{r['máximo (°C)']:.1f}",
                                        f"{r['percentil 5 (°C)']:.1f}–{r['percentil 95 (°C)']:.1f}", num(r["área < 0 °C (km²)"], 1)]
                                       for k, r in tres.loc[["Tmax", "Tmed", "Tmin"]].iterrows()],
  ["Variable", "Media", "Mínimo", "Máximo", "Percentil 5–95", "Área < 0 °C (km²)"], [2.2, 2, 2, 2, 3, 3.3])
P("Los límites de los pisos térmicos de Caldas salen de la ecuación de Tmed de esta cuenca, Z = (T₀ − T)/α, y no de valores "
  "genéricos.")
T("Pisos térmicos de la cuenca", [[r.piso, r._2, r._3, num(r._5), f"{r._4:.1f}"] for r in pis.iloc[::-1].itertuples()],
  ["Piso", "Tmed (°C)", "Elevación (m)", "Área (km²)", "% del área"], [3.5, 2.5, 3.5, 3, 2.5])
P("**Interpretación.** La mitad de la cuenca es templada (944–1882 m), y en ella están el Eje Cafetero y las laderas del Valle. El "
  "piso cálido (8.9 %) ocupa el cañón antioqueño y el fondo del Valle bajo 944 m. Los pisos de páramo y nival (12.7 %) forman la "
  "franja alta de la cordillera Central y el Macizo.")
P("En las 47 estaciones, el valor del mapa reproduce la temperatura medida con un sesgo de −0.4 a −0.5 °C y un RMSE de 1.3 a "
  "1.6 °C según la variable. Las desviaciones "
  "mayores se explican por la diferencia entre la cota del DEM y la del catálogo.")

# ============================================================================= 7. ETP
H("7. Evapotranspiración potencial — Hargreaves-Samani (punto 6)")
H("Metodología", 2)
P("La ETP se calculó mes a mes y celda a celda con Hargreaves y Samani (1985):")
EC("ETP = 0.0023 · Ra · (Tmed + 17.8) · (Tmax − Tmin)^0.5   [mm/día]")
B(["Ra es la radiación extraterrestre en mm/día equivalentes (Anexo 3). Se calculó con la latitud de cada celda y el día juliano "
   "representativo de cada mes (Allen et al., 1998).",
   "Las temperaturas mensuales salen de las 12 regresiones T–Z mensuales.",
   "La ETP anual es la suma de las 12 ETP mensuales, cada una multiplicada por los días del mes."])
F("08_etp_etr/ETP_mensual.png", "ETP mensual de la cuenca y radiación extraterrestre Ra por mes y latitud.", 16)
H("Resultados", 2)
P("La ETP media de la cuenca es **1409 mm/año**, entre 348 mm en los nevados y 2003 mm en el cañón cálido. Equivale a 1606 m³/s. El "
  "mapa se presenta junto con φ, ETR y R en el panel de la sección 8.")
P("**Contraste con el IDEAM.** En las 244 estaciones con ETP del IDEAM:")
B(["Hargreaves sobrestima la ETP en un 22 % (+263 mm).",
   "Reproduce bien el patrón espacial (r = 0.92)."])
H("Interpretación", 2)
P("La ETP sigue a la temperatura y por lo tanto a la elevación. La relación ETP–Tmed es casi lineal. Ra cambia menos de 1 mm/día "
  "entre el sur (2° N) y el norte (7° N) de la cuenca, y sus máximos están cerca de los equinoccios. Por eso el ciclo anual de la "
  "ETP es suave.")
P("La sobrestimación frente al IDEAM es conocida en climas húmedos. Hargreaves no ve la nubosidad, que reduce la radiación que llega "
  "a la superficie. Se probó escalar la ETP al IDEAM (×0.822): el error del balance pasa a +9 % en el cierre y a +9 % a +23 % en las "
  "estaciones, peor que sin escalar. Por eso se conservó la ETP de Hargreaves sin corrección, como pide el enunciado.")
P("**Contraste con estudios previos.** Ramírez et al. (2011) encontraron que Hargreaves, en la forma de la FAO, sobrestima la "
  "evapotranspiración de referencia medida con lisímetro en la zona cafetera colombiana. Es el mismo sentido del sesgo encontrado "
  "aquí frente al IDEAM. En la evaluación nacional de Barco et al. (2000), los métodos más confiables frente a balances en cuencas "
  "fueron Turc y Penman. Turc, que solo requiere P y T, sería la alternativa natural para una sensibilidad adicional.")

# ============================================================================= 8. ETR
H("8. Evapotranspiración real — Budyko (punto 7)")
P("La ETR se calculó **celda a celda** con la ecuación de Budyko (1974), donde φ = ETP/P es el índice de aridez:")
EC("ETR = P · [ φ · tanh(1/φ) · (1 − e^(−φ)) ]^0.5")
P("En la cuenca, φ = 0.71 con las medias de P y ETP (0.76 como promedio de las celdas). Resultados:")
B(["**ETR = 1085 mm/año** (ETR/P = 0.55).",
   "**R = P − ETR = 900 mm/año**, es decir, 1026 m³/s."])
F("08_etp_etr/mapas_ETP_phi_ETR_R_panel.png", "ETP de Hargreaves, índice de aridez φ, ETR de Budyko y escorrentía R = P − ETR. ETP y "
  "ETR tienen las mismas clases (cada una con su paleta), así que se comparan valor a valor.", 16.5)
F("08_etp_etr/curva_budyko.png", "Celdas de la cuenca en el espacio de Budyko, con los límites de energía (ETR = ETP) y de agua "
  "(ETR = P).", 12)
H("Interpretación", 2)
P("La mayor parte de la cuenca tiene φ < 1. Allí el clima es húmedo y la evaporación está limitada por la energía, no por el agua: "
  "la ETR se acerca a la ETP. Solo el fondo del Valle del Cauca tiene φ > 1. Allí la ETR está limitada por el agua y evapora entre "
  "el 80 % y el 88 % de su lluvia, así que casi no produce escorrentía.")
P("La escorrentía se concentra en las vertientes húmedas y en la cuenca media antioqueña, donde R supera 1500 mm/año.")
P("**Celda a celda frente a agregado.** Aplicar Budyko con el φ medio de la cuenca da ETR = 1123 mm/año y R = 862 mm/año, un 4 % "
  "menos. La curva no es lineal, y promediar φ antes de aplicarla sobrestima la ETR. Por eso se trabajó celda a celda.")

# ============================================================================= 9. caudales
H("9. Caudales observados (punto 8)")
H("Datos y criterios", 2)
P("Los caudales medios diarios (Q_MEDIA_D) salen del archivo nacional del IDEAM, actualizado en agosto de 2026. Se descargaron 12 "
  "estaciones del cauce principal y se aplicaron los criterios de validez siguientes:")
B(["**Mes válido:** al menos el 80 % de los días con dato.",
   "**Año válido:** los 12 meses válidos.",
   "**Estación validada:** al menos 15 años válidos dentro de 1981–2010."])
P("Diez estaciones cumplen. Puente Pescadero y Olaya tienen solo 10 años completos y quedaron fuera. En los archivos del IDEAM, el "
  "dato faltante es la ausencia de la fecha. Se verificó que no hay ceros ni negativos usados como código de faltante.")
P("Las áreas de drenaje se delimitaron con el mismo DEM. Cada estación se llevó a la celda del cauce más cercana con al menos "
  "1000 km² acumulados.")
qrows = []
est = pd.ExcelFile(RES / "06_caudales" / "Punto8_caudales_estaciones.xlsx").parse("Estaciones")
for _, r in est.iterrows():
    n = r["Estación"]; c = qa[n]; w = c.loc[1981:2010]
    qrows.append([r["Código"], n, f"{r['Latitud (°)']:.3f} / {r['Longitud (°)']:.3f}", num(r["Área de drenaje (km²)"]),
                  f"{int(c.first_valid_index())}–{int(c.last_valid_index())}", f"{int(w.notna().sum())}", num(w.mean(), 1)])
T("Estaciones de caudal validadas: ubicación, área de drenaje, periodo de registro y caudal medio anual multianual (1981–2010)", qrows,
  ["Código", "Estación", "Lat / Lon (°)", "Área (km²)", "Registro (años completos)", "Años válidos 1981–2010", "Q medio (m³/s)"],
  [1.9, 2.6, 3.2, 1.8, 2.4, 2.2, 2.2], nota="Q medio = promedio de los caudales medios de los años completos de 1981–2010. Todas cumplen "
  "más de 15 años de información.")
F("06_caudales/mapa_estaciones_caudal_validadas.png", "Estaciones de caudal validadas y sus áreas de drenaje.", 12)
F("06_caudales/disponibilidad_caudales.png", "Disponibilidad de datos (meses con al menos 80 % de días) de las estaciones descargadas.", 16)
H("Relleno de faltantes (análisis adicional, libro aparte)", 2)
P("El balance usa solo años completos observados. Como análisis adicional, guardado en un libro de Excel aparte "
  "(Punto8_caudales_relleno.xlsx) por si hay que descartarlo, se rellenaron los meses faltantes con **regresión log-lineal entre "
  "estaciones**:")
EC("ln Q_obj = a + b · ln Q_pred ;   Q = exp(a + b · ln Q_pred) · factor de Duan")
B(["El **factor de Duan** (1983) corrige el sesgo de volver de logaritmos a caudales.",
   "Las predictoras posibles fueron 102 estaciones de la cuenca. Cada una debía tener al menos 60 meses de traslape y r(ln Q) ≥ 0.8.",
   "Cada mes faltante se rellenó en cascada con la predictora elegible de mayor r que tuviera dato ese mes.",
   "Se validó con **validación cruzada dejando un año fuera**: NSE entre 0.80 (La Balsa) y 0.98 (Bolombolo), con sesgo inferior "
   "al 3 %.",
   "El relleno no usa P − ETR, para no condicionar la validación del balance."])
P("Con las series rellenadas, las medias cambian 2 % o menos. Dos estaciones se apartan más:")
B(["Puente Iglesias: +2 %.",
   "Puente Pescadero: +7 %, por sus 148 meses rellenados."])
H("Interpretación", 2)
P("El caudal crece aguas abajo de forma regular:")
B(["179 m³/s en La Balsa, regulada por Salvajina desde 1985.",
   "1122 m³/s en Puerto Valdivia."])
P("El rendimiento aumenta en el cañón antioqueño, que es la zona más lluviosa. Entre Irra y La Pintada el caudal solo sube 26 m³/s, "
  "menos de lo que aporta el río Arma. Por eso La Pintada se ubicó aguas arriba de esa desembocadura.")
P("No hay estación validada en la presa. El caudal del cierre se obtuvo transfiriendo el de Puerto Valdivia, ≈ 35 km aguas abajo, "
  "por relación de áreas (37 267 km² → 35 992 km²). Resultan **1084 m³/s (950 mm/año)**. Con las series rellenadas da 1020–1040 "
  "m³/s. El proyecto reporta un caudal medio de 1010–1100 m³/s en el sitio de presa (Alcaldía de Medellín, s. f.), así que la "
  "estimación es consistente.")
H("Variabilidad interanual y ENSO (análisis adicional)", 2)
P("Para comprobar la coherencia de las series, se compararon las anomalías anuales del caudal y de la lluvia de la cuenca (CHIRPS "
  "v2.0) en años El Niño (1983, 1987, 1992, 1998, 2003, 2010) y La Niña (1989, 1999, 2000, 2008, 2011). Los años son los de la "
  "fase madura o el año siguiente a ella. Las anomalías se expresan respecto a la media 1981–2010.")
T("Anomalía media anual en años El Niño y La Niña, y coeficiente de variación interanual (1981–2010)", enso_filas,
  ["Serie", "El Niño (%)", "La Niña (%)", "CV interanual (%)"], [5, 3.5, 3.5, 4],
  nota="n = años con dato en cada compuesto. P: promedio de las celdas CHIRPS v2.0 dentro de la cuenca.")
P(f"Todas las estaciones muestran juntas la misma señal: caudales menores en El Niño y mayores en La Niña. No hay saltos aislados "
  f"que sugieran errores de una sola estación. La señal es mucho más fuerte en el caudal que en la lluvia:")
B([f"El CV interanual del caudal es de {cv_q_min:.0f}–{cv_q_max:.0f} %, frente a {cv_p:.0f} % de la lluvia.",
   f"La razón entre ambos, ≈ {cv_q_med / cv_p:.1f}, mide la amplificación de la lluvia al caudal."])
P(f"La elasticidad del caudal a la lluvia que predice Budyko para φ = 0.71 es de solo {eps_b:.1f}. Es la variación relativa de "
  f"R por cada 1 % de variación de P, y se obtiene derivando la curva:")
EC("ε = 1 + φ · F′(φ) / (1 − F(φ))")
P(f"La amplificación observada ({cv_q_med / cv_p:.1f}) es mayor que esa elasticidad. Poveda et al. (2001) encontraron lo mismo a "
  "escala nacional: el efecto del ENSO es mayor sobre los caudales que sobre la lluvia, por los cambios simultáneos en la humedad "
  "del suelo y la evapotranspiración. En El Niño, más temperatura y radiación elevan la ETR justo cuando llueve menos. Poveda et "
  "al. (2011) muestran además que esta señal es más fuerte y temprana en los Andes occidentales, donde está la cuenca.")
P("La Niña 2010–2011, un evento extremo, causó inundaciones y deslizamientos con daños de gran magnitud en el país "
  f"(Hoyos et al., 2013). En Puerto Valdivia, 2011 fue el {rk2011}.º año más caudaloso de {n_pv} con registro completo "
  f"({num(q2011)} m³/s, {q2011 / qa['Puerto Valdivia'].loc[1981:2010].mean() * 100 - 100:+.0f} % sobre la media 1981–2010).")

# ============================================================================= 10. balance
H("10. Validación del balance hídrico (punto 9)")
P("Para cada área de drenaje con caudal observado se calcularon P, ETP y ETR como promedios de sus celdas. Con ellos:")
EC("R = P − ETR ;   Q_est = R · A / 31 557 600 s ;   Error = (Q_est − Q_obs) / Q_obs")
T("Balance hídrico de largo plazo por área de drenaje (1981–2010)",
  [[r.estacion.replace(" (cierre)", ""), num(r._3), num(r._4), num(r._6), num(r._10), num(r._11, 1), num(r._8, 1), f"{r._12:+.1f}".replace("-", "−")]
   for r in bal.itertuples()],
  ["Área de drenaje", "A (km²)", "P (mm)", "ETR (mm)", "P − ETR (mm)", "Q est (m³/s)", "Q obs (m³/s)", "Error (%)"],
  [3.4, 1.8, 1.6, 1.6, 1.9, 2, 2, 1.7])
F("09_balance/balance_Q_est_vs_obs.png", "Caudal estimado por el balance frente al observado.", 14)
H("Resultados e interpretación", 2)
P("El balance reproduce el caudal observado en todas las estaciones con errores entre −7 % y +7 %, con un error absoluto medio de "
  "4.5 % y r = 0.995. En el cierre, el error es de **−5.3 %**. Si el caudal observado se toma de la serie rellenada de Puente "
  "Pescadero (1020 m³/s), el error pasa a +0.6 %.")
P("El signo del error tiene un patrón espacial claro:")
B(["**Alto Cauca y Valle** (La Balsa, Juanchito, La Victoria): el balance sobrestima entre 5 % y 7 %. Es lo esperado, porque el "
   "caudal observado no es natural: hay regulación de Salvajina, riego de caña y acueductos.",
   "**La Virginia e Irra:** subestima, posiblemente por lluvia orográfica sobre 3000 m que las estaciones no captan.",
   "**Cañón antioqueño:** errores de 1–7 %."])
T("Sensibilidad del error de cierre a las decisiones metodológicas", [
    ["Base: kriging, Hargreaves, Budyko celda a celda", "−5.3 %"], ["P por IDW (p = 1.5)", "−5.6 %"],
    ["P con las 358 estaciones del mapa de estaciones", "−4.1 %"], ["ETP escalada al IDEAM (×0.822)", "+9.3 %"],
    ["Budyko agregado (φ medio)", "−9.2 %"], ["Q observado de la serie rellenada (Pte. Pescadero)", "+0.6 %"]],
  ["Variante", "Error en el cierre"], [11, 5.5])
P("**Fuentes de incertidumbre:**")
B(["**Precipitación:** pocas estaciones sobre 3000 m y un RMSE de interpolación de 363 mm.",
   "**ETP:** Hargreaves sobrestima en un 22 % frente al IDEAM.",
   "**Budyko:** curva empírica sin calibrar, que no considera vegetación, suelos ni estacionalidad.",
   "**Caudal:** las curvas de calibración nivel–caudal tienen errores del 5 al 15 %; el cierre es un caudal transferido; y el "
   "caudal está regulado y con extracciones.",
   "**Áreas de drenaje:** en el Valle el cauce del DEM se separa 3–5 km del real, lo que da ±5 % de área.",
   "**Almacenamiento:** el supuesto ΔS ≈ 0 es razonable a 30 años."])
P("Un error de ±5 % está dentro de la incertidumbre de la medición de caudal. El balance de largo plazo cierra.")
P("**Contraste con estudios previos.** Poveda et al. (2007) aplicaron el mismo esquema, Q = P − ETR de largo plazo, a toda la "
  "red de drenaje de Colombia. Lo validaron con unas 200 estaciones de caudal y concluyeron dos cosas:")
B(["Ningún método de evapotranspiración superó claramente a los demás.",
   "El error proviene sobre todo de la escasez de datos, no del esquema del balance."])
P("Los resultados de esta cuenca apuntan en la misma dirección:")
B(["Cambiar la ETP o la forma de aplicar Budyko mueve el cierre entre −9 % y +9 %.",
   "La sensibilidad mayor está en la lluvia de alta montaña, donde casi no hay estaciones."])
P("El cierre de −5.3 % es comparable con los errores típicos de esos balances nacionales.")

# ============================================================================= 11. productos
H("11. Productos de precipitación (punto 10)")
P("Antes de descargar, se verificó que los tres productos cubren la cuenca y tienen un periodo común. Ese periodo es 1981–2025, de "
  "540 meses, completo en todas las celdas. Para el balance se usa 1981–2010, el mismo de P, T y Q. Así las diferencias entre "
  "fuentes se deben al producto y no al periodo.")
T("Productos de precipitación", [
    ["CHIRPS v2.0", "Satélite (infrarrojo) + estaciones, Climate Hazards Center (Funk et al., 2015)", "0.05° (≈ 5.5 km)", "1171", "IRI Data Library"],
    ["ERA5-Land", "Reanálisis de superficie terrestre forzado por ERA5, ECMWF / C3S (Muñoz-Sabater et al., 2021)", "0.1° (≈ 11 km)", "294", "Drive del curso"],
    ["ERA5", "Reanálisis atmosférico global, ECMWF / C3S (Hersbach et al., 2020)", "0.25° (≈ 28 km)", "46", "Drive del curso"],
    ["CHIRPS v3.0", "Nueva versión de CHIRPS (sensibilidad)", "0.05°", "1171", "Drive del curso"]],
  ["Producto", "Tipo y referencia", "Resolución", "Celdas en la cuenca", "Fuente"], [2.4, 7.2, 2.6, 1.9, 2.5])
P("Cada producto se convirtió a mm/mes y se recortó a la cuenca. Los valores de relleno negativos sobre el mar (CHIRPS v3.0) se "
  "filtraron. Las sumas anuales se promediaron en 1981–2010 y se llevaron a la grilla de 90 m por vecino más cercano, sin suavizar "
  "la resolución nativa.")
P("La lectura se verificó con la lluvia de lugares de referencia en Colombia. En Quibdó, ERA5 da 8081 mm/año y CHIRPS 8195 mm/año, "
  "valores razonables. En Manizales, en cambio, ERA5 da 15 164 mm/año y CHIRPS 2361 mm/año. Que ERA5 acierte en el Chocó y falle "
  "en los Andes descarta un error de unidades: es un sesgo del producto sobre la cordillera.")
P("**Decisión: CHIRPS v2.0 como producto principal.** Es la versión publicada y más citada. Se descargó directamente de la IRI Data "
  "Library porque el archivo del curso es la v3.0. Esta última se evaluó como sensibilidad: +11 % de P y +14 % de error en el "
  "cierre.")

# ============================================================================= 12. mapas productos
H("12. Mapas de precipitación por producto (punto 11)")
F("11_mapas_productos/panel_P_productos.png", "Precipitación media anual 1981–2010 de IDEAM (kriging), CHIRPS v2.0, ERA5-Land y ERA5, "
  "con la misma escala de color.", 16.5)
T("Precipitación media anual de la cuenca por producto (1981–2010)",
  [[k, num(r["P media cuenca (mm/año)"]), f"{num(r['mínimo (mm/año)'])}–{num(r['máximo (mm/año)'])}", f"{r['sesgo vs IDEAM (%)']:+.0f} %".replace("-", "−"),
    f"{r['correlación espacial con IDEAM']:.2f}".replace("-", "−")] for k, r in rp.iterrows()],
  ["Producto", "P media (mm/año)", "Rango (mm/año)", "Sesgo frente a IDEAM", "r espacial con IDEAM"], [3.5, 3, 3.5, 3.2, 3.3])
F("11_mapas_productos/panel_razon_IDEAM.png", "Razón entre cada producto y la precipitación interpolada IDEAM.", 15)
H("Interpretación", 2)
P("CHIRPS v2.0 reproduce el patrón y la magnitud del IDEAM: +2 % de sesgo y r espacial 0.89. Esto es esperable en parte, porque "
  "CHIRPS incorpora estaciones en su construcción.")
P("ERA5 y ERA5-Land triplican la lluvia de la cuenca, con medias de unos 5970 mm/año y máximos de 18 000–20 000 mm/año sobre la "
  "cordillera. Además, su patrón espacial no se parece al observado (r ≈ −0.06):")
B(["Ponen la lluvia máxima en las crestas de la cordillera.",
   "No reproducen la sombra de lluvia del Valle."])
P("Es un sesgo conocido de los reanálisis en terreno complejo. La parametrización de la convección y la orografía suavizada a "
  "0.1–0.25° concentran la lluvia en las laderas de barlovento. ERA5-Land hereda la lluvia de ERA5, por eso los dos son casi "
  "idénticos.")
P("CHIRPS v3.0, la versión del Drive del curso, da 11 % más lluvia que la v2.0 sobre la cuenca, con un patrón espacial similar.")
P("**Contraste con estudios previos.** Hay evidencia independiente en ambos sentidos:")
B(["**CHIRPS:** López-Bermeo et al. (2022) lo validaron en Antioquia contra 75 pluviómetros que CHIRPS no usa (1981–2018). "
   "Representa bien la lluvia en la mayoría de condiciones, incluso en los ENSO más intensos, y funciona mejor en las subregiones "
   "andinas.",
   "**ERA5:** Vega-Durán et al. (2021) encontraron que sobrestima de forma consistente los promedios mensuales de 49 estaciones del "
   "IDEAM en la cuenca del Sinú, a todas las escalas."])
P("El sesgo de ERA5 en esta cuenca (×3) es mucho mayor que el del Sinú, que es una cuenca de llanura. Es coherente con que los "
  "reanálisis de baja resolución representan mal la topografía compleja y no resuelven el valle interandino del Cauca.")

# ============================================================================= 13. balance productos
H("13. Balance hídrico con cada producto (punto 12)")
P("Se repitió el balance del punto 9 cambiando solo la precipitación. La ETP de Hargreaves, las áreas de drenaje y los caudales "
  "observados son los mismos; la ETR de Budyko se recalculó celda a celda con la P de cada producto.")
hid = bp[bp.codigo == "HIDRO"].set_index("producto")
SEG = 365.25 * 86400
ro = hid.Qobs.iloc[0] * SEG / (A * 1e6) * 1000
T("Tabla del enunciado: balance en el cierre (Hidroituango, 1981–2010)",
  [[k, num(r.P), num(r.ETR), num(r.R), num(ro), f"{r.err:+.1f}".replace("-", "−")] for k, r in hid.iterrows()] +
  [["CHIRPS v3.0 (sensibilidad)", "2 202", "1 118", "1 084", num(ro), "+14.1"]],
  ["Producto", "P (mm/año)", "ETR (mm/año)", "Q est (mm/año)", "Q obs (mm/año)", "Error (%)"], [4.4, 2.4, 2.4, 2.4, 2.4, 2.4],
  nota="Q observado: Puerto Valdivia transferido por relación de áreas (1084 m³/s).")
T("Desempeño del balance en las 9 estaciones de caudal (sin el cierre)",
  [[k, f"{r.sesgo:+.1f}", f"{r.MAE:.1f}", f"{r.RMSE:.1f}", f"{r.r:.3f}"] for k, r in des.iterrows()],
  ["Producto", "Sesgo medio (%)", "Error absoluto medio (%)", "RMSE relativo (%)", "r (Q est – Q obs)"], [3.5, 3, 3.5, 3.2, 3.3])
F("15_complementarias/R_por_producto.png", "Escorrentía de largo plazo R = P − ETR con cada fuente de precipitación (misma escala de "
  "color).", 16.5)
H("Evaluación más allá de la precipitación", 2)
P("El error del balance mezcla los errores de P, de la ETP y de Budyko. Para separarlos se calculó la **P necesaria** en cada área "
  "de drenaje: la que, con la misma ETP y la curva de Budyko, reproduciría exactamente el caudal observado. Se resolvió con el "
  "método de Brent sobre la ecuación P − ETR(P) = R_obs.")
B(["**IDEAM y CHIRPS v2.0:** la corrección necesaria va de −5 % a +4 %. Está dentro del error de interpolación, así que la "
   "combinación Hargreaves + Budyko es consistente con los caudales.",
   "**ERA5 y ERA5-Land:** habría que reducir la P entre 47 % y 74 %. En las 9 estaciones y en el cierre ningún ajuste razonable "
   "de la ETP compensa ese exceso: la ETR «observada» (P − Q_obs) sería el 72–88 % de su P, con φ de 0.20–0.32, fuera de la curva de "
   "Budyko. El balance con estos productos es físicamente imposible."])
P("Que el r entre Q estimado y observado sea alto también con ERA5 (0.97) no es mérito del producto. Refleja que el caudal crece "
  "con el área en cualquier fuente. Lo que discrimina a los productos es el sesgo.")
P("La comparación punto a píxel en las 259 estaciones lo confirma:")
B(["CHIRPS: RMSE 369 mm, igual al error del kriging en validación cruzada (366 mm).",
   "ERA5: RMSE ≈ 6300 mm y r ≈ 0.06."])

# ============================================================================= 14. climatología
H("14. Ciclo anual y régimen de precipitación (punto 13)")
P("Para cada mes se interpoló la normal mensual 1981–2010 de las estaciones con kriging ordinario, con un variograma ajustado a ese "
  "mes. Los 12 mapas usan la misma escala de color (mm/mes) y la misma paleta que los mapas de lluvia anual.")
F("13_climatologia/panel_P_mensual.png", "Precipitación media mensual 1981–2010 (kriging de estaciones IDEAM), con la misma escala "
  "de color en los 12 meses.", 16.5)
F("13_climatologia/ciclo_anual.png", "Ciclo anual de la precipitación media de la cuenca.", 14)
mm = cic["P media cuenca (mm)"].mean()
T("Precipitación media mensual de la cuenca (mm)", [[r.mes.capitalize(), num(r._2), f"{r._4:.1f}", "húmedo" if r._2 > mm + 1 else
                                                     ("límite" if abs(r._2 - mm) <= 1 else "seco")] for r in cic.itertuples()],
  ["Mes", "P (mm)", "% del total anual", "Clasificación"], [3, 3, 4, 4],
  nota=f"Mes húmedo: P mensual sobre la media mensual de la cuenca ({mm:.0f} mm); seco: por debajo.")
F("15_complementarias/estacionalidad.png", "Mes de máxima lluvia, número de picos del ciclo e índice de estacionalidad de Walsh y "
  "Lawler en cada celda.", 16.5)
H("Interpretación", 2)
P("**Régimen bimodal.** El ciclo tiene dos temporadas de lluvia y dos secas. Mejía et al. (1999) y Poveda (2004) lo explican por "
  "la migración meridional de la Zona de Convergencia Intertropical, que pasa dos veces al año sobre los Andes colombianos, "
  "modulada por la topografía:")
B(["**Húmedos:** marzo, abril y mayo (máximo en abril, 218 mm) y octubre y noviembre (máximo en octubre, 240 mm). La segunda "
   "temporada es la más intensa.",
   "**Secos:** diciembre a febrero (mínimo en febrero, 120 mm) y junio a agosto (mínimo en agosto, 114 mm). Septiembre está en el "
   "límite, porque es la transición hacia la temporada de octubre."])
P("**Variación espacial.** El 99.8 % del área es bimodal. El máximo anual cae en octubre o noviembre en el 63 % del área y en abril "
  "o mayo en el 37 %.")
P("El **índice de estacionalidad** de Walsh y Lawler (1981) se define como:")
EC("SI = (1/R) · Σ |P_m − R/12|")
P("Va de 0.17 a 0.42 (media 0.29). La lluvia está bien repartida a lo largo del año, sin una estación seca "
  "marcada. Para la presa, las dos temporadas secas implican dos estiajes por año, y el de julio–agosto es el "
  "más severo.")

# ============================================================================= 15. ciclo productos
H("15. Comparación del ciclo anual entre productos (punto 14)")
P("Se compararon los ciclos de cada producto, como promedio de la cuenca, con el ciclo IDEAM (n = 12 meses). Las métricas fueron "
  "el sesgo, el RMSE y la correlación de Pearson r. Se añadió el **diagrama de Taylor** (Taylor, 2001), opcional en el enunciado. "
  "En él, la distancia a la referencia es el RMSE centrado normalizado.")
F("14_ciclo_productos/ciclos_productos.png", "Ciclo anual de la precipitación media de la cuenca según cada producto.", 15)
F("14_ciclo_productos/taylor.png", "Diagrama de Taylor de los ciclos anuales frente al IDEAM.", 11)
T("Métricas del ciclo anual frente al IDEAM (n = 12)",
  [[k, f"{r['Sesgo (mm/mes)']:+.1f} ({r['Sesgo (%)']:+.1f} %)", f"{r['RMSE (mm/mes)']:.1f}", f"{r['r']:.3f}", f"{r['σ normalizada']:.2f}",
    r["Meses de máximos (2 picos)"], r["Mes mínimo"]] for k, r in mc.drop("IDEAM").iterrows()],
  ["Producto", "Sesgo (mm/mes)", "RMSE (mm/mes)", "r", "σ normalizada", "Máximos", "Mínimo"], [2.4, 3.6, 2.4, 1.6, 2.4, 2.2, 1.8])
H("Discusión: ¿qué producto es mejor?", 2)
P("**CHIRPS v2.0 es el mejor producto para esta cuenca en todos los criterios evaluados:**")
B(["**Ciclo anual:** r = 0.998, sesgo +1.4 %, RMSE 4.8 mm/mes, y queda casi sobre la referencia en el diagrama de Taylor.",
   "**Mapa anual:** r espacial 0.89 y sesgo +2 %.",
   "**Balance:** cierra con −2.2 % de error; la corrección de P necesaria es inferior al 5 %.",
   "**Estaciones:** su error punto a píxel es el mismo del kriging en validación cruzada."])
P("ERA5 y ERA5-Land tienen tres defectos:")
B(["Triplican la lluvia, con un sesgo de +199 %.",
   "Desplazan el máximo del ciclo a abril–mayo, cuando el observado es octubre–noviembre.",
   "Su r es de 0.62–0.69 y su σ normalizada de 1.6, lejos de la referencia en el diagrama de Taylor."])
P("Su balance es físicamente imposible sin una corrección de sesgo. Entre ellos, ERA5-Land es apenas mejor (r = 0.69 frente a "
  "0.62), porque hereda la precipitación de ERA5.")
P("Una limitación de la evaluación: el ciclo de referencia es el kriging de las mismas estaciones que CHIRPS usa para corregirse. "
  "Por eso su buen ajuste está en parte asegurado. La prueba independiente es el balance con caudales, y ahí CHIRPS también cierra.")

# ============================================================================= 16. adicionales
H("16. Decisiones propias y análisis adicionales")
P("Esta sección reúne todo lo que se hizo fuera de lo que pide la rúbrica, y lo que se consideró y no se aplicó.")
T("Análisis estadísticos y técnicas adicionales", [
    ["Relleno de series de caudal por regresión log-lineal con corrección de Duan", "Sí", "Punto 8 (libro aparte)",
     "NSE 0.80–0.98; las medias cambian 2 % o menos"],
    ["Validación cruzada dejando un año fuera (relleno)", "Sí", "Punto 8", "Verifica el relleno con datos no usados en el ajuste"],
    ["Validación cruzada dejando una estación fuera (interpolación)", "Sí", "Punto 3", "Kriging RMSE 363 mm frente a IDW 364–377 mm"],
    ["Ajuste del variograma por mínimos cuadrados ponderados (Cressie)", "Sí", "Puntos 3 y 13", "Pepita realista (21 % de la meseta)"],
    ["Correlación de Pearson", "Sí", "Puntos 4, 11, 12 y 14", "T–Z, r espacial, Q est–obs, ciclos"],
    ["Correlación de Spearman", "Sí", "Punto 3", "P–Z: ρ = 0.30 (r = 0.18): sin deriva por elevación"],
    ["Intervalo de confianza del 95 % de la pendiente y residuos estudentizados", "Sí", "Punto 4", "α con ±0.2–0.3 °C/km; atípicos marcados"],
    ["Índice de estacionalidad de Walsh y Lawler", "Sí", "Punto 13", "SI 0.17–0.42"],
    ["Diagrama de Taylor", "Sí", "Punto 14 (opcional)", "Resume r, σ y RMSE centrado"],
    ["P necesaria por inversión de Budyko (método de Brent)", "Sí", "Punto 12", "Separa el error de P del de ETP y Budyko"],
    ["Comparación punto a píxel", "Sí", "Punto 12", "CHIRPS RMSE 369 mm; ERA5 ≈ 6300 mm"],
    ["Análisis de sensibilidad", "Sí", "Puntos 9 y 12", "Método de P, estaciones, ETP, Budyko agregado, CHIRPS v3.0, Q rellenado"],
    ["Compuestos ENSO de caudal y lluvia anual", "Sí", "Punto 8", f"Q: {rango_nino} en El Niño, {rango_nina} en La Niña"],
    ["Elasticidad del caudal a la lluvia (Budyko) frente a la amplificación observada", "Sí", "Punto 8",
     f"{eps_b:.1f} teórica frente a ≈ {amp:.1f} observada"],
    ["Contraste con la literatura colombiana", "Sí", "Puntos 3–14", "Poveda, Mesa, Hoyos, Barco y otros"],
    ["Correlación no lineal (información mutua, regresión no paramétrica)", "No", "—", "Spearman bastó para descartar la relación P–Z"],
    ["Funciones ortogonales empíricas (EOF) / análisis de componentes principales (ACP)", "No", "—",
     "Se trabaja con climatologías de 30 años, no con campos en el tiempo"],
    ["Análisis espectral singular (AES)", "No", "—", "No se analizaron series temporales"],
    ["Espectro de Fourier", "No", "—", "El ciclo anual se describe con 12 medias mensuales (Mejía et al., 1999, usan la FFT para "
     "separar los ciclos anual y semianual)"],
    ["Transformada de ondículas", "No", "—", "El ENSO se evaluó con compuestos anuales; no hizo falta un análisis tiempo-frecuencia"],
    ["Regresión logística", "No", "—", "No hay variable de respuesta binaria"],
    ["K vecinos más cercanos (KNN)", "No", "—", "El relleno por regresión ya tenía NSE ≥ 0.80"],
    ["Quantile mapping", "No", "—", "La rúbrica pide evaluar los productos sin corregir"]],
  ["Análisis", "¿Aplicado?", "Dónde", "Resultado o razón"], [6.2, 1.6, 3.2, 5.5], fs=8.5)
P("**Por qué no se aplicaron los métodos de series de tiempo.** El trabajo es un balance de largo plazo. Cada variable se reduce a "
  "su media 1981–2010 (anual o mensual). La única pregunta interanual, la coherencia de los caudales con el ENSO, se respondió con "
  "compuestos. EOF, ACP, AES, Fourier y ondículas servirían para una extensión: los modos espaciales y los periodos de la "
  "variabilidad del caudal.")
P("El quantile mapping sería el paso natural para usar ERA5 en la cuenca. Aquí no se aplicó, porque el objetivo era evaluar los "
  "productos tal como se distribuyen.")
P("**Otras decisiones propias:**")
B(["Priority-Flood + ε en lugar del relleno de pysheds.",
   "Grilla común de 90 m en EPSG:3116.",
   "Exclusión de Briceño.",
   "Mismas 47 estaciones para Tmax, Tmin y Tmed.",
   "Budyko celda a celda en lugar de agregado.",
   "ETP de Hargreaves sin escalar.",
   "Cierre con Puerto Valdivia transferido por áreas.",
   "CHIRPS v2.0 como producto principal.",
   "Escala de color común por variable en todos los mapas."])

# ============================================================================= 17. conclusiones
H("17. Conclusiones")
B(["La cuenca aportante a Hidroituango (35 992 km², hasta la presa) recibe 1985 mm/año de lluvia. Evapora 1085 mm/año (55 %) y "
   "produce 900 mm/año de escorrentía, unos 1026 m³/s en la presa.",
   "El balance Q = P − ETR, con kriging, Hargreaves-Samani y Budyko celda a celda, reproduce los caudales observados con errores "
   "de ±7 % en 9 estaciones y −5.3 % en el cierre. Eso está dentro de la incertidumbre de la medición de caudal y de la "
   "interpolación de P.",
   "La temperatura depende casi solo de la elevación (R² > 0.96), con gradientes de 7.3, 6.4 y 5.7 °C/km para Tmax, Tmed y Tmin. "
   "La mitad de la cuenca está en el piso templado.",
   "Hargreaves sobrestima la ETP del IDEAM en un 22 %, pero mantiene su patrón espacial (r = 0.92). Escalarla empeora el balance, "
   "así que el sesgo lo compensa en parte la curva de Budyko. La sobrestimación coincide con lo reportado en la zona cafetera "
   "(Ramírez et al., 2011).",
   f"Los caudales responden al ENSO con una variabilidad ≈ {amp:.1f} veces la de la lluvia. Es mayor que la elasticidad de "
   f"Budyko ({eps_b:.1f}), y es coherente con el papel de la humedad del suelo y la evapotranspiración que señalan Poveda et al. (2001, "
   "2011).",
   "El caudal medio estimado en la presa (1026 m³/s por balance; 1020–1084 m³/s observado) coincide con el que reporta el "
   "proyecto (1010–1100 m³/s).",
   "Las mayores incertidumbres son la lluvia de alta montaña, la regulación y las extracciones en el alto Cauca y el Valle, y la "
   "falta de una estación de caudal en la presa.",
   "CHIRPS v2.0 es el mejor producto: +2 % de P, cierre en −2.2 % y r del ciclo de 0.998, en línea con su validación en Antioquia "
   "(López-Bermeo et al., 2022). ERA5 y ERA5-Land triplican la lluvia, ubican mal su patrón espacial y su ciclo, y producen un "
   "balance imposible. Su sobrestimación concuerda con la reportada en el Sinú (Vega-Durán et al., 2021), aquí agravada por la "
   "topografía. No deben usarse sin corrección.",
   "La lluvia es bimodal en casi toda la cuenca, con la temporada principal en octubre–noviembre y el estiaje más severo en "
   "julio–agosto. Esto es relevante para la operación del embalse."])

# ============================================================================= referencias
H("Referencias")
for r in sorted([
    "Alcaldía de Medellín (s. f.). Hidroituango es pura energía y confianza para Colombia. https://www.medellin.gov.co/es/sala-de-prensa/"
    "noticias/hidroituango-es-pura-energia-y-confianza-para-colombia/",
    "Allen, R. G., Pereira, L. S., Raes, D. y Smith, M. (1998). *Crop evapotranspiration*. FAO Irrigation and Drainage Paper 56, Roma.",
    "Barco, J., Cuartas, A., Mesa, O., Poveda, G., Vélez, J. I., Mantilla, R., Hoyos, C., Mejía, J. F., Botero, B. y Montoya, M. "
    "(2000). Estimación de la evaporación en Colombia. *Avances en Recursos Hidráulicos*, 7, 43–51.",
    "Chaves, B. y Jaramillo, A. (1999). Regionalización de la temperatura del aire en Colombia. *Avances en Recursos Hidráulicos*, 6, "
    "37–42.",
    "Eslava, J. (1992). Perfil altitudinal de la temperatura media del aire en Colombia. *Earth Sciences Research Journal*, "
    "1(1), 37–52.",
    "Hoyos, I., Dominguez, F., Cañón-Barriga, J., Martínez, J. A., Nieto, R., Gimeno, L. y Dirmeyer, P. A. (2018). Moisture origin "
    "and transport processes in Colombia, northern South America. *Climate Dynamics*, 50, 971–990.",
    "Hoyos, N., Escobar, J., Restrepo, J. C. et al. (2013). Impact of the 2010–2011 La Niña phenomenon in "
    "Colombia, South America: The human toll of an extreme weather event. *Applied Geography*, 39, 16–25.",
    "López-Bermeo, C. et al. (2022). Validation of the accuracy of the CHIRPS precipitation dataset at representing climate "
    "variability in a tropical mountainous region of South America. *Physics and Chemistry of the Earth*, 127, 103184.",
    "Mejía, J. F., Mesa, O., Poveda, G. et al. (1999)."
    " Distribución espacial y ciclos anual y semianual de la precipitación en Colombia. *DYNA*, 127, 7–24.",
    "Poveda, G. (2004). La hidroclimatología de Colombia: una síntesis desde la escala inter-decadal hasta la escala diurna. *Revista "
    "de la Academia Colombiana de Ciencias Exactas, Físicas y Naturales*, 28(107), 201–221.",
    "Poveda, G., Jaramillo, A., Gil, M. M., Quiceno, N. y Mantilla, R. I. (2001). Seasonality in ENSO-related precipitation, river "
    "discharges, soil moisture, and vegetation index in Colombia. *Water Resources Research*, 37(8), 2169–2178.",
    "Poveda, G., Vélez, J. I., Mesa, O. J. et al. (2007). Linking long-term water balances and statistical scaling to estimate river "
    "flows along the drainage network of Colombia. *Journal of Hydrologic Engineering*, 12(1), 4–13.",
    "Poveda, G., Álvarez, D. M. y Rueda, O. A. (2011). Hydro-climatic variability over the Andes of Colombia associated with ENSO: a "
    "review of climatic processes and their impact on one of the Earth's most important biodiversity hotspots. *Climate Dynamics*, "
    "36, 2233–2249.",
    "Ramírez, V. H., Mejía, A., Marín, E. V. y Arango, R. (2011). Evaluation of models for estimating the reference "
    "evapotranspiration in Colombian coffee zone. *Agronomía Colombiana*, 29(1), 107–114.",
    "Vega-Durán, J., Escalante-Castro, B., Canales, F. A., Acuña, G. J. y Kaźmierczak, B. (2021). Evaluation of areal monthly average "
    "precipitation estimates from MERRA2 and ERA5 reanalysis in a Colombian Caribbean basin. *Atmosphere*, 12(11), 1430.",
    "Barnes, R., Lehman, C. y Mulla, D. (2014). Priority-flood: An optimal depression-filling and watershed-labeling algorithm for "
    "digital elevation models. *Computers & Geosciences*, 62, 117–127.",
    "Budyko, M. I. (1974). *Climate and Life*. Academic Press, Nueva York.",
    "Cressie, N. (1985). Fitting variogram models by weighted least squares. *Mathematical Geology*, 17(5), 563–586.",
    "Duan, N. (1983). Smearing estimate: A nonparametric retransformation method. *Journal of the American Statistical Association*, "
    "78(383), 605–610.",
    "European Space Agency (2021). *Copernicus Global Digital Elevation Model (GLO-30)*. OpenTopography / AWS Open Data.",
    "Funk, C. et al. (2015). The climate hazards infrared precipitation with stations — a new environmental record for monitoring "
    "extremes. *Scientific Data*, 2, 150066.",
    "Hargreaves, G. H. y Samani, Z. A. (1985). Reference crop evapotranspiration from temperature. *Applied Engineering in "
    "Agriculture*, 1(2), 96–99.",
    "Hersbach, H. et al. (2020). The ERA5 global reanalysis. *Quarterly Journal of the Royal Meteorological Society*, 146(730), "
    "1999–2049.",
    "IDEAM. Promedios climatológicos 1981–2010; caudales medios diarios (HidrologiaNacionalDiaria, 2026); Catálogo Nacional de "
    "Estaciones (datos.gov.co).",
    "Lehner, B., Verdin, K. y Jarvis, A. (2008). New global hydrography derived from spaceborne elevation data. *Eos*, 89(10), 93–94.",
    "Muñoz-Sabater, J. et al. (2021). ERA5-Land: a state-of-the-art global reanalysis dataset for land applications. *Earth System "
    "Science Data*, 13, 4349–4383.",
    "Taylor, K. E. (2001). Summarizing multiple aspects of model performance in a single diagram. *Journal of Geophysical Research*, "
    "106(D7), 7183–7192.",
    "Walsh, R. P. D. y Lawler, D. M. (1981). Rainfall seasonality: description, spatial patterns and change through time. "
    "*Weather*, 36(7), 201–208."], key=str.lower):
    p = runs(doc.add_paragraph(), r); p.paragraph_format.left_indent = Cm(1); p.paragraph_format.first_line_indent = Cm(-1)

H("Anexo. Archivos de soporte")
T("Libros de cálculo y scripts", [
    ["Punto4_temperatura_elevacion.xlsx", "Regresiones T–Z con fórmulas vivas"],
    ["Punto8_caudales_estaciones.xlsx", "Caracterización de caudales (punto 8)"],
    ["Punto8_caudales_relleno.xlsx", "Relleno de faltantes (análisis adicional, separado)"],
    ["Punto9_balance_hidrico.xlsx", "Balance por área de drenaje, tramos, sensibilidad e incertidumbre"],
    ["Punto12_balance_productos.xlsx", "Balance con cada producto y desempeño"],
    ["scripts/01–22", "Procesamiento completo en Python (delimitación a informe)"],
    ["Página web", "https://anajul1a4.github.io/balance-hidrico-hidroituango/"]], ["Archivo", "Contenido"], [6.5, 10])

# pie de página con número
for s in doc.sections:
    p = s.footer.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    campo(p, "PAGE").font.size = Pt(9)

ruta = OUT / "Informe_Trabajo1_Hidroituango.docx"
doc.save(ruta)
print(ruta, f"{NF[0]} figuras, {NT[0]} tablas")
