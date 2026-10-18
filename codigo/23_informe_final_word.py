"""
Completa el informe escrito del equipo ("Trabajo 1 Hidrometeorología.docx", Google Docs) conservando su formato:
  · reescribe Resumen, Introducción y Descripción de la zona de estudio con citas verificadas;
  · corrige numeración de tablas, referencias cruzadas y erratas de las secciones 1–5;
  · reemplaza las figuras 2–7 por versiones dibujadas a escala de impresión (24_figuras_informe.py), insertadas 1:1;
  · agrega las secciones 6–14, conclusiones y referencias en el mismo estilo (Times New Roman 11, leyendas 9 pt).

Entrada : ~/Downloads/Trabajo 1 Hidrometeorología.docx   (no se modifica)
Salida  : ~/Downloads/Trabajo 1 Hidrometeorología - completo.docx
"""
import copy
import re
import sys
from pathlib import Path

import docx
import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "resultados"
DL = Path.home() / "Downloads"
ENTRADA = DL / "Trabajo 1 Hidrometeorología.docx"
SALIDA = DL / "Trabajo 1 Hidrometeorología - completo (figuras HD).docx"
sys.path.insert(0, str(Path(__file__).parent))
from productos import abrir  # noqa: E402

doc = docx.Document(ENTRADA)
body = doc.element.body
P = list(doc.paragraphs)
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# ============================================================================= bloques XML en el estilo del documento
TNR = '<w:rFonts w:ascii="Times New Roman" w:cs="Times New Roman" w:eastAsia="Times New Roman" w:hAnsi="Times New Roman"/>'


def rpr(b=False, i=False, sz=None, sub=False, sup=False, hl=False):
    s = TNR + ('<w:b w:val="1"/><w:bCs w:val="1"/>' if b else "") + ('<w:i w:val="1"/><w:iCs w:val="1"/>' if i else "")
    s += '<w:highlight w:val="yellow"/>' if hl else ""
    s += f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>' if sz else ""
    s += '<w:vertAlign w:val="subscript"/>' if sub else ('<w:vertAlign w:val="superscript"/>' if sup else "")
    return f"<w:rPr>{s}</w:rPr>"


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def runs(texto, b=False, i=False, sz=None, hl=False):
    """**negrita**, *cursiva*, _{subíndice}, ^{superíndice}."""
    out = []
    for parte in re.split(r"(\*\*.+?\*\*|\*.+?\*|_\{.+?\}|\^\{.+?\})", texto):
        if not parte:
            continue
        kw = dict(b=b, i=i, sz=sz, hl=hl)
        if parte.startswith("**"):
            parte, kw["b"] = parte[2:-2], True
        elif parte.startswith("*"):
            parte, kw["i"] = parte[1:-1], True
        elif parte.startswith("_{"):
            parte, kw["sub"] = parte[2:-1], True
        elif parte.startswith("^{"):
            parte, kw["sup"] = parte[2:-1], True
        out.append(f'<w:r>{rpr(**kw)}<w:t xml:space="preserve">{esc(parte)}</w:t></w:r>')
    return "".join(out)


PPR = {
    "body": '<w:spacing w:after="240" w:before="240" w:lineRule="auto"/><w:jc w:val="both"/>',
    "sub": '<w:spacing w:after="240" w:before="240" w:lineRule="auto"/><w:jc w:val="both"/>',
    "head": '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr><w:spacing w:after="120" w:before="240" w:lineRule="auto"/>'
            '<w:ind w:left="720" w:hanging="360"/><w:jc w:val="both"/>',
    "bullet": '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr><w:spacing w:after="0" w:before="120" w:lineRule="auto"/>'
              '<w:ind w:left="720" w:hanging="360"/><w:jc w:val="both"/>',
    "eq": '<w:spacing w:after="240" w:before="240" w:lineRule="auto"/><w:jc w:val="center"/>',
    "capfig": '<w:spacing w:after="240" w:lineRule="auto"/><w:jc w:val="center"/>',
    "nota": '<w:spacing w:after="240" w:before="60" w:lineRule="auto"/><w:jc w:val="both"/>',
    "captab": '<w:keepNext w:val="1"/><w:spacing w:after="120" w:before="240" w:lineRule="auto"/><w:jc w:val="both"/>',
    "ref": '<w:spacing w:after="120" w:lineRule="auto"/><w:ind w:left="720" w:hanging="720"/><w:jc w:val="both"/>',
    "title": '<w:spacing w:after="240" w:before="240" w:lineRule="auto"/><w:jc w:val="both"/>',
}


def par(texto, tipo="body", hl=False):
    if tipo == "capfig":
        n, resto = texto.split(". ", 1)
        r = runs(n + ". ", b=True, sz=18) + runs(resto, sz=18)
    elif tipo == "captab":
        n, resto = texto.split(". ", 1)
        r = runs(n + ". ", b=True, i=True, sz=18) + runs(resto, i=True, sz=18)
    elif tipo == "nota":
        r = runs(texto, sz=18)
    else:
        r = runs(texto, b=tipo in ("head", "sub", "title"), hl=hl)
    return parse_xml(f'<w:p {nsdecls("w")}><w:pPr>{PPR[tipo]}</w:pPr>{r}</w:p>')


BORDE = '<w:{0} w:color="bfbfbf" w:space="0" w:sz="5" w:val="single"/>'


def tabla(filas, enc, anchos_cm, primera_izq=True):
    total = 8910
    w = [round(a / sum(anchos_cm) * total) for a in anchos_cm]
    grid = "".join(f'<w:gridCol w:w="{x}"/>' for x in w)
    trs = []
    for k, fila in enumerate([enc] + filas):
        tcs = []
        for j, v in enumerate(fila):
            jc = "left" if (primera_izq and j == 0 and k > 0) else "center"
            bord = "".join(BORDE.format(s) for s in ("top", "left", "bottom", "right"))
            tcs.append(f'<w:tc><w:tcPr><w:tcW w:w="{w[j]}" w:type="dxa"/><w:tcBorders>{bord}</w:tcBorders><w:shd w:fill="ffffff" w:val="clear"/>'
                       f'<w:tcMar><w:left w:w="100" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tcMar><w:vAlign w:val="center"/></w:tcPr>'
                       f'<w:p><w:pPr><w:spacing w:after="60" w:before="60" w:lineRule="auto"/><w:jc w:val="{jc}"/></w:pPr>'
                       f'{runs(str(v), b=(k == 0), sz=18)}</w:p></w:tc>')
        hdr = '<w:tblHeader w:val="1"/>' if k == 0 else ""
        trs.append(f'<w:tr><w:trPr><w:cantSplit w:val="1"/>{hdr}</w:trPr>{"".join(tcs)}</w:tr>')
    return parse_xml(f'<w:tbl {nsdecls("w")}><w:tblPr><w:tblW w:w="{total}" w:type="dxa"/><w:jc w:val="center"/>'
                     f'<w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid>{grid}</w:tblGrid>{"".join(trs)}</w:tbl>')


FIGS = RES / "informe_figs"          # figuras dibujadas a escala de impresión (24_figuras_informe.py)


def ancho_nativo(nombre):
    """Ancho (cm) al que la figura queda a escala 1:1: el texto se imprime al tamaño con que se dibujó (6.5–8.5 pt)."""
    im = Image.open(FIGS / nombre)
    w = im.size[0] / im.info.get("dpi", (300, 300))[0] * 2.54
    return min(w * 1.2, 16.0) if w > 11 else w      # las anchas se amplían hasta 20 % para llenar la página (texto ≥ 7 pt)


def figura(nombre, ancho_cm=None):
    """Párrafo centrado con la imagen a su tamaño nativo (o reducida si excede el ancho de la página)."""
    ancho = min(ancho_cm or ancho_nativo(nombre), 16.0)
    im = Image.open(FIGS / nombre).convert("RGB")
    tmp = Path(__file__).parent / "_tmp_fig.png"
    im.save(tmp, "PNG", optimize=True)
    p = doc.add_paragraph()           # crea la relación de imagen; luego se mueve a su lugar
    p.add_run().add_picture(str(tmp), width=Cm(ancho))
    tmp.unlink()
    el = p._p
    el.insert(0, parse_xml(f'<w:pPr {nsdecls("w")}><w:keepNext w:val="1"/><w:spacing w:after="60" w:before="240" w:lineRule="auto"/>'
                           f'<w:jc w:val="center"/></w:pPr>'))
    return el


# ============================================================================= utilidades de edición
def reemplazar_texto(p, nuevo, hl=False):
    """Reemplaza el texto de un párrafo conservando su pPr (formato del documento)."""
    for r in list(p._p):
        if r.tag != qn("w:pPr"):
            p._p.remove(r)
    for r in parse_xml(f'<w:p {nsdecls("w")}>{runs(nuevo, hl=hl)}</w:p>'):
        p._p.append(r)


def sustituir(viejo, nuevo):
    """Sustitución dentro de los runs (para referencias cruzadas y erratas)."""
    n = 0
    for p in doc.paragraphs:
        for r in p.runs:
            if viejo in r.text:
                r.text = r.text.replace(viejo, nuevo); n += 1
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                for p in c.paragraphs:
                    for r in p.runs:
                        if viejo in r.text:
                            r.text = r.text.replace(viejo, nuevo); n += 1
    if n == 0:
        print("AVISO, no encontrado:", viejo)
    return n


def despues(ancla, elementos):
    for el in elementos:
        ancla.addnext(el)
        ancla = el
    return ancla


def buscar(inicio):
    for p in doc.paragraphs:
        if p.text.strip().startswith(inicio):
            return p
    raise KeyError(inicio)


def num(x, d=0):
    return f"{x:,.{d}f}".replace(",", " ").replace("-", "−")


def sg(x, d=0):
    return f"{x:+.{d}f}".replace("-", "−")


# ============================================================================= datos
morf = pd.read_csv(RES / "01_delimitacion" / "parametros_morfometricos.csv", index_col=0).iloc[:, 0]
A = morf["Área (km²)"]
rb = pd.read_csv(RES / "08_etp_etr" / "resumen_balance_largo_plazo.csv", index_col=0)
bal = pd.read_csv(RES / "09_balance" / "balance_subcuencas.csv", dtype={"codigo": str})
bp = pd.read_csv(RES / "12_balance_productos" / "balance_productos.csv", dtype={"codigo": str})
des = pd.read_csv(RES / "12_balance_productos" / "desempeno_productos.csv", index_col=0)
rp = pd.read_csv(RES / "11_mapas_productos" / "resumen_productos.csv", index_col=0)
mc = pd.read_csv(RES / "14_ciclo_productos" / "metricas_ciclo.csv", index_col=0)
cic = pd.read_csv(RES / "13_climatologia" / "ciclo_anual.csv")
qa = pd.read_csv(RES / "15_complementarias" / "Q_anual_estaciones.csv", index_col=0)
est = pd.ExcelFile(RES / "06_caudales" / "Punto8_caudales_estaciones.xlsx").parse("Estaciones")
qm = pd.read_csv(ROOT / "datos" / "caudales_ideam" / "Q_mensual_1981_2010.csv", index_col=0, parse_dates=True)
qc = qm.groupby(qm.index.month).mean()          # ciclo anual de caudal por estación (código)
jc, pv = qc["26067010"], qc["26237040"]         # Juanchito (valle alto) y Puerto Valdivia

# compuestos ENSO
_cu = gpd.read_file(RES / "01_delimitacion" / "cuenca_cauca_hidroituango.gpkg", layer="cuenca").to_crs(4326).geometry[0]
_p = abrir("CHIRPS").precip
_m = shapely.contains_xy(_cu, *np.meshgrid(_p.lon.values, _p.lat.values))
p_anual = _p.groupby("time.year").sum("time", min_count=12).where(_m).mean(["lat", "lon"]).to_series()
NINO, NINA = [1983, 1987, 1992, 1998, 2003, 2010], [1989, 1999, 2000, 2008, 2011]


def compuesto(c):
    m = c.loc[1981:2010].mean()
    a = lambda ys: np.array([100 * (c.get(y, np.nan) / m - 1) for y in ys])  # noqa: E731
    n, l = a(NINO), a(NINA)
    return np.nanmean(n), int((~np.isnan(n)).sum()), np.nanmean(l), int((~np.isnan(l)).sum()), 100 * c.loc[1981:2010].std() / m


ORDEN = ["La Balsa", "Juanchito", "La Victoria", "La Virginia", "Irra", "La Pintada", "Puente Iglesias", "Bolombolo", "Cañafisto",
         "Puerto Valdivia"]
enso = {"P de la cuenca (CHIRPS v2.0)": compuesto(p_anual)} | {f"Q {k}": compuesto(qa[k]) for k in ORDEN}
cvq = [v[4] for k, v in enso.items() if k.startswith("Q ")]
cv_p = enso["P de la cuenca (CHIRPS v2.0)"][4]
amp = float(np.median(cvq)) / cv_p
_F = lambda f: np.sqrt(f * np.tanh(1 / f) * (1 - np.exp(-f)))  # noqa: E731
eps_b = 1 + 0.71 * (_F(0.71 + 1e-5) - _F(0.71 - 1e-5)) / 2e-5 / (1 - _F(0.71))
qn_, ql_ = [v[0] for k, v in enso.items() if k.startswith("Q ")], [v[2] for k, v in enso.items() if k.startswith("Q ")]

# ============================================================================= 1. Resumen, introducción y zona de estudio
reemplazar_texto(buscar("Estudiar las alteraciones"), (
    "Conocer cuánta agua produce una cuenca en un año medio, dónde se genera y qué tan confiable es la información con que se estima "
    "es la base para planear el uso del recurso y la generación hidroeléctrica. En este trabajo se estimó el balance hídrico de largo "
    f"plazo (1981–2010) de la cuenca aportante a Hidroituango, el río Cauca desde su nacimiento en el Macizo Colombiano hasta la presa "
    f"({num(A)} km²), con la ecuación Q = P − ETR. La precipitación se interpoló por kriging ordinario a partir de 266 estaciones del "
    "IDEAM (1985 mm/año); la temperatura se regionalizó con regresiones lineales con la elevación (R² > 0.96); la evapotranspiración "
    "potencial se calculó con Hargreaves-Samani (1409 mm/año) y la real con la curva de Budyko (1085 mm/año). La escorrentía resultante, "
    "900 mm/año (1026 m³/s), difiere en −5.3 % del caudal observado en el cierre y entre −7 % y +7 % del de nueve estaciones del río "
    "Cauca, errores comparables con la incertidumbre de la medición de caudales. Al repetir el balance con productos globales, CHIRPS "
    "v2.0 reprodujo la lluvia (+2 %), el balance (−2.2 %) y el ciclo anual (r = 0.998), mientras que ERA5 y ERA5-Land triplicaron la "
    "lluvia de la cuenca y produjeron un balance físicamente imposible. La lluvia es bimodal en casi toda la cuenca, con máximos en "
    f"abril y octubre, y los caudales responden al ENSO con una variabilidad interanual {amp:.1f} veces mayor que la de la lluvia. Se "
    "concluye que la oferta hídrica que llega a Hidroituango es muy sensible a la variabilidad climática y que la escasez de estaciones "
    "en alta montaña es la principal limitación para estimarla."))

intro1, intro2 = buscar("El aumento en la frecuencia"), buscar("Los recursos hídricos presentan")
reemplazar_texto(intro1, (
    "La variabilidad climática modifica de forma marcada la disponibilidad de agua en Colombia. Por su ubicación bajo la influencia de "
    "la Zona de Convergencia Intertropical (ZCIT) y por su topografía andina, el país tiene una distribución espacial y temporal de la "
    "lluvia muy compleja, con procesos que van desde la escala diurna hasta la interdecadal (Poveda, 2004). Entre ellos, el fenómeno "
    "El Niño–Oscilación del Sur (ENSO) es la principal fuente de variabilidad interanual: durante El Niño disminuyen la lluvia, los "
    "caudales y la humedad del suelo, y durante La Niña aumentan. Estos efectos son más fuertes entre diciembre y febrero, y más "
    "intensos y tempranos en los Andes occidentales (Poveda et al., 2001; Poveda et al., 2011)."))
reemplazar_texto(intro2, (
    "El valle del río Cauca es especialmente sensible a este fenómeno. Carvajal et al. (1998) asocian los caudales mínimos de sus ríos "
    "con los años de El Niño y los máximos con La Niña, y documentan que la sequía de 1992 causó un racionamiento de energía de "
    "cerca de un año y pérdidas de cosechas en la región. En el extremo opuesto, La Niña 2010–2011 produjo inundaciones y "
    "deslizamientos con graves daños humanos y económicos en todo el país (Hoyos et al., 2013)."))
despues(intro2._p, [
    par("Estos impactos son críticos para el sector eléctrico, porque cerca del 69 % de la capacidad instalada de Colombia es "
        "hidráulica (La República, 2019, con datos de XM). Hidroituango, sobre el río Cauca en Antioquia, es la central más grande del "
        "país, con 2400 MW en ocho unidades de 300 MW (Alcaldía de Medellín, s. f.), y su generación depende del caudal que aporta la "
        "cuenca aguas arriba. Por eso es necesario saber cuánta agua produce esta cuenca en un año medio, cómo se distribuye en el "
        "espacio y a lo largo del año, y qué tan confiable es la información con que se estima."),
    par("Este trabajo estima el balance hídrico de largo plazo (1981–2010) de la cuenca aportante a Hidroituango con la ecuación "
        "Q = P − ETR, que supone un cambio de almacenamiento nulo a esa escala. La precipitación se interpola a partir de estaciones del "
        "IDEAM, la temperatura se regionaliza con la elevación, la evapotranspiración potencial se calcula con Hargreaves-Samani y la "
        "real con la curva de Budyko, y el resultado se valida con los caudales observados en el río Cauca. Luego se evalúan tres "
        "productos globales de precipitación (CHIRPS, ERA5 y ERA5-Land) con el mismo balance y con la comparación de su ciclo anual, "
        "siguiendo el esquema de los balances hidrológicos de largo plazo de Colombia (Poveda et al., 2007).")])

zona = buscar("El río Cauca nace en el Macizo")
reemplazar_texto(zona, (
    "El río Cauca nace en el Macizo Colombiano, en el cerro El Español, cerca del páramo de Sotará, y recorre unos 1360 km hacia el "
    "norte entre las cordilleras Occidental y Central hasta desembocar en el río Magdalena, en el departamento de Bolívar (Minambiente, "
    f"s. f.). La cuenca aportante a Hidroituango corresponde a sus primeros 855 km, cerca del 63 % de su longitud, y drena {num(A)} km² "
    "hasta la presa (7.136° N, 75.663° W). No es la cuenca completa del Cauca, que continúa hasta el Magdalena y la estudia otro "
    "equipo. Casi toda su área está en seis departamentos: Valle del Cauca (10 720 km²), Antioquia (9216 km²), Cauca (7436 km²), "
    "Caldas (4196 km²), Risaralda (2467 km²) y Quindío (1930 km²)."))
reg = [
    par("El relieve es muy contrastante. La elevación va de 229 m, en el cañón del Cauca cerca de la presa, a 5273 m en las cumbres "
        "nevadas de la cordillera Central, con una media de 1806 m. El río atraviesa tres ambientes: una cabecera de fuerte pendiente "
        "en el Macizo, el valle plano del Cauca, que desciende apenas unos 950 m en 400 km entre Cali y Cartago, y el cañón "
        "antioqueño, angosto y cálido, que llega hasta la presa. En pocas decenas de kilómetros se pasa de un valle seco, a la sombra "
        "de la lluvia de la cordillera Occidental, a laderas muy húmedas y páramos, lo que hace de esta cuenca un caso exigente para "
        "el balance hídrico."),
    par("El régimen de lluvias es bimodal, como resultado del doble paso de la ZCIT: los periodos más lluviosos son marzo-abril-mayo "
        "y septiembre-octubre-noviembre, y los más secos diciembre-enero-febrero y junio-julio-agosto (Carvajal et al., 1998; "
        "Poveda, 2004). Los caudales siguen ese ritmo con un rezago. En el valle alto, en la estación Juanchito, julio-agosto-septiembre "
        f"es el trimestre más seco ({num(jc.loc[[7, 8, 9]].min())}–{num(jc.loc[[7, 8, 9]].max())} m³/s) y noviembre-diciembre-enero el "
        f"más caudaloso ({num(jc.loc[[11, 12, 1]].min())}–{num(jc.loc[[11, 12, 1]].max())} m³/s). Cerca del cierre, en Puerto Valdivia, "
        f"los máximos son noviembre ({num(pv[11])} m³/s) y mayo ({num(pv[5])} m³/s) y el mínimo agosto ({num(pv[8])} m³/s). El caudal "
        "del alto Cauca está regulado por el embalse de Salvajina desde 1985, y en el valle la agricultura, principalmente la caña de "
        "azúcar, demanda cerca del 80 % del recurso hídrico (Carvajal et al., 1998). Ambos factores alteran el caudal natural y deben "
        "tenerse en cuenta al validar el balance.")]
despues(zona._p, reg)

# párrafo final del borrador (ENSO y régimen): su contenido pasa a la zona de estudio
viejo = buscar("La hidrometeorología de la cuenca aportante")
viejo._p.getparent().remove(viejo._p)

# ============================================================================= 2. correcciones en las secciones 1–5
for a, b in [("La Tabla 4 resume", "La Tabla 2 resume"), ("Tabla 5.", "Tabla 3."), ("(Tabla 5)", "(Tabla 3)"), ("Tabla 6.", "Tabla 4."),
             ("(Tabla 6 y Figura 5)", "(Tabla 4 y Figura 5)"), ("Tabla 8.", "Tabla 5."), ("(Tabla 7)", "(Tabla 5)"),
             ("Tabla 9.", "Tabla 6."), ("(Tabla 9)", "(Tabla 6)"), ("sección 8", "sección 6"), ("del punto 4", "de la sección 3"),
             ("porqué", "porque"), ("Chaves y Jaramillo (1998)", "Chaves y Jaramillo (1999)")]:
    sustituir(a, b)

# reconciliación de áreas (sección 1): las cifras del resto del informe salen de la delimitación GLO-30 a 90 m
fig1 = buscar("Figura 1.")._p   # después de la figura: la Tabla 1 del borrador es flotante
despues(fig1, [par(
    f"Para los cálculos de las secciones siguientes se usó la delimitación hecha con el DEM Copernicus GLO-30 remuestreado a 90 m, con "
    f"relleno de depresiones Priority-Flood + ε (Barnes et al., 2014), que da {num(A)} km², una elevación de 229 a 5273 m (media 1806 m) "
    "y un punto de cierre a 178 m de la coordenada publicada de la presa. Su área coincide con la de HydroSHEDS (35 841 km²; Lehner et "
    "al., 2008) con una diferencia de 0.4 %. La diferencia con la Tabla 1 (2 %) se debe probablemente a la resolución del DEM, que en "
    "una celda de unos 930 m suaviza las cumbres y el fondo del cañón. [Revisar: unificar el área que se reporta en la Tabla 1.]",
    hl=True)])

# figuras 2–7 del borrador: misma posición y leyenda; imagen redibujada a escala de impresión y tamaño 1:1
import io  # noqa: E402
EMU = 360000                                                  # EMU por cm
for inicio, nombre in [("Figura 2.", "mapa_estaciones_P.png"), ("Figura 3.", "variograma_validacion.png"),
                       ("Figura 4.", "mapa_P_anual.png"), ("Figura 5.", "diagramas_T_Z.png"),
                       ("Figura 6.", "panel_temperatura.png"), ("Figura 7.", "ETP_mensual.png")]:
    cap = buscar(inicio)._p
    el = cap if cap.xpath(".//a:blip") else cap.getprevious()
    while not el.xpath(".//a:blip"):
        el = el.getprevious()
    blip = el.xpath(".//a:blip")[0]
    part = doc.part.related_parts[blip.get(qn("r:embed"))]
    im = Image.open(FIGS / nombre).convert("RGB")
    buf = io.BytesIO(); im.save(buf, "PNG" if part.partname.endswith(".png") else "JPEG", quality=95, subsampling=0); part._blob = buf.getvalue()
    ancho = min(ancho_nativo(nombre), 16.0)
    cx, cy = int(ancho * EMU), int(ancho * EMU * im.size[1] / im.size[0])
    for ext in el.xpath(".//wp:extent") + el.xpath(".//a:ext"):
        ext.set("cx", str(cx)); ext.set("cy", str(cy))
    if el is cap:                     # imagen y leyenda en el mismo párrafo: salto de línea para que la leyenda quede debajo
        r_img = el.xpath(".//w:drawing")[0].getparent()
        r_img.addnext(parse_xml(f'<w:r {nsdecls("w")}><w:br/></w:r>'))

# complemento de la sección 5 (ETP)
etp2 = buscar("En las 244 estaciones que tienen ETP")
despues(etp2._p, [
    par("La ETP varía poco a lo largo del año, entre 107 y 128 mm/mes (Figura 7), porque la radiación extraterrestre cambia menos de "
        "1 mm/día entre el sur y el norte de la cuenca y sus máximos están cerca de los equinoccios. La sobrestimación frente al IDEAM es "
        "conocida en climas húmedos: Hargreaves no considera la nubosidad, que reduce la radiación que llega a la superficie. Ramírez et "
        "al. (2011) encontraron el mismo sesgo frente a mediciones con lisímetro en la zona cafetera colombiana. Como prueba, la ETP se "
        "escaló al IDEAM (factor 0.822); el error del balance pasó de −5.3 % a +9.3 % en el cierre, de modo que se conservó la ETP de "
        "Hargreaves sin corrección, como pide el enunciado. En la evaluación nacional de Barco et al. (2000), los métodos más "
        "confiables frente a balances en cuencas fueron Turc y Penman, que serían la alternativa natural para una sensibilidad "
        "adicional.")])

# ============================================================================= 3. secciones nuevas (6 a 14), conclusiones y referencias
nuevo = []
NF, NT = [7], [6]


def F(nombre, texto, ancho=None):       # el ancho de cada figura es el nativo (escala 1:1)
    NF[0] += 1
    nuevo.extend([figura(nombre), par(f"Figura {NF[0]}. {texto}", "capfig")])
    return NF[0]


def T(texto, filas, enc, anchos, primera_izq=True):
    NT[0] += 1
    nuevo.extend([par(f"Tabla {NT[0]}. {texto}", "captab"), tabla(filas, enc, anchos, primera_izq)])
    return NT[0]


def B(t, tipo="body", hl=False):
    nuevo.append(par(t, tipo, hl))


# ---- 6. ETR
B("Evapotranspiración real — Budyko", "head")
B("La evapotranspiración real (ETR) se calculó celda a celda con la ecuación de Budyko (1974), que expresa la fracción de la lluvia "
  "que se evapora en función del índice de aridez φ = ETP/P:")
B("ETR = P · [φ · tanh(1/φ) · (1 − e^{−φ})]^{1/2}", "eq")
B("La curva tiene dos límites físicos. Cuando φ es pequeño, el clima es húmedo y la evaporación está limitada por la energía, de modo "
  "que la ETR se acerca a la ETP. Cuando φ es grande, el clima es seco y la evaporación está limitada por el agua, de modo que la ETR "
  "se acerca a P. Se aplicó en cada celda de 90 m con la P de la sección 2 y la ETP de la sección 5, y no con los promedios de la "
  "cuenca, porque la curva no es lineal: promediar φ antes de aplicarla sobrestima la ETR.")
T("Balance hídrico de largo plazo de la cuenca (1981–2010).", [
    ["Precipitación P", f"{num(rb.iloc[0, 0])} mm/año", f"{num(rb.iloc[0, 3])} m³/s"],
    ["Evapotranspiración potencial ETP", f"{num(rb.iloc[1, 0])} mm/año", f"{num(rb.iloc[1, 3])} m³/s"],
    ["Índice de aridez φ = ETP/P (medias de la cuenca / media de celdas)", f"{rb.iloc[1, 0] / rb.iloc[0, 0]:.2f} / {rb.iloc[3, 0]:.2f}", "—"],
    ["Evapotranspiración real ETR (Budyko celda a celda)", f"{num(rb.iloc[4, 0])} mm/año", f"{num(rb.iloc[4, 3])} m³/s"],
    ["Fracción evaporada ETR/P", f"{rb.iloc[5, 0]:.2f}", "—"],
    ["Escorrentía R = P − ETR", f"{num(rb.iloc[6, 0])} mm/año", f"{num(rb.iloc[6, 3])} m³/s"],
    ["Escorrentía con Budyko agregado (φ medio)", f"{num(rb.iloc[8, 0])} mm/año", f"{num(rb.iloc[8, 3])} m³/s"]],
  ["Variable", "Lámina", "Caudal equivalente"], [9, 3.5, 3.5])
F("panel_ETP_phi_ETR_R.png", "Evapotranspiración potencial de Hargreaves, índice de aridez φ, evapotranspiración "
  "real de Budyko y escorrentía R = P − ETR. ETP y ETR comparten las clases de la escala de color.", 15.5)
F("curva_budyko.png", "Celdas de la cuenca en el espacio de Budyko, con los límites de energía (ETR = ETP) y de agua "
  "(ETR = P).", 11)
B(f"La cuenca evapora 1085 mm/año, el 55 % de su lluvia, y produce una escorrentía de 900 mm/año, equivalente a 1026 m³/s en la presa "
  "(Tabla 7). La mayor parte de su área tiene φ < 1, es decir, un clima húmedo en el que la evaporación está limitada por la energía "
  "(Figura 9). Solo el fondo del valle del Cauca tiene φ > 1: allí la ETR está limitada por el agua y se evapora entre el 80 % y el "
  "88 % de la lluvia, así que el valle casi no produce escorrentía. La escorrentía se concentra en las vertientes húmedas de ambas "
  "cordilleras y en la cuenca media antioqueña, donde R supera los 1500 mm/año (Figura 8).")
B("Aplicar la curva con el φ medio de la cuenca da una ETR de 1123 mm/año y una escorrentía de 862 mm/año, un 4 % menor que la "
  "obtenida celda a celda. Esa diferencia, debida solo a la no linealidad de la curva, justifica el cálculo distribuido.")

# ---- 7. Caudales
B("Caudales observados", "head")
B("Los caudales medios diarios se tomaron del archivo nacional del IDEAM (HidrologiaNacionalDiaria), y la ubicación de las estaciones "
  "del Catálogo Nacional de Estaciones. Se descargaron las 12 estaciones del cauce principal del Cauca entre La Balsa y Puerto "
  "Valdivia, y se aplicaron tres criterios de validez:")
B("Mes válido: al menos el 80 % de los días con dato; el caudal mensual es el promedio de esos días.", "bullet")
B("Año válido: los 12 meses válidos.", "bullet")
B("Estación validada: al menos 15 años válidos dentro de 1981–2010, el mismo periodo de la precipitación y la temperatura.", "bullet")
B("Diez estaciones cumplen (Tabla 8). Puente Pescadero y Olaya, las más cercanas a la presa, tienen solo 10 años completos y quedaron "
  "por fuera. En los archivos del IDEAM el dato faltante es la ausencia de la fecha; se verificó que no hay ceros ni valores negativos "
  "usados como código de faltante. El área de drenaje de cada estación se delimitó con el mismo DEM de la cuenca, llevando la "
  "estación a la celda del cauce más cercana con al menos 1000 km² acumulados.")
filas = []
for _, r in est.iterrows():
    n = r["Estación"]; c = qa[n]; w = c.loc[1981:2010]
    filas.append([n, r["Código"], f"{r['Latitud (°)']:.3f} / {r['Longitud (°)']:.3f}", num(r["Área de drenaje (km²)"]),
                  f"{int(c.first_valid_index())}–{int(c.last_valid_index())}", f"{int(w.notna().sum())}", num(w.mean(), 1)])
T("Estaciones de caudal validadas: ubicación, área de drenaje, periodo de registro y caudal medio anual multianual (1981–2010).",
  filas, ["Estación", "Código", "Lat / Lon (°)", "Área (km²)", "Registro", "Años válidos 1981–2010", "Q medio (m³/s)"],
  [2.6, 1.9, 3.1, 1.8, 2, 2.1, 2])
F("mapa_estaciones_Q.png", "Estaciones de caudal validadas y sus áreas de drenaje.", 9.5)
F("disponibilidad_caudales.png", "Disponibilidad de datos de las estaciones descargadas (meses con al menos 80 % de días con "
  "dato). Verde: estación validada; rojo: no cumple.", 15.5)
B("El caudal crece aguas abajo de forma regular, de 179 m³/s en La Balsa, regulada por Salvajina, a 1122 m³/s en Puerto Valdivia. "
  "Entre Irra y La Pintada el caudal solo aumenta 26 m³/s, menos de lo que aporta el río Arma; por eso La Pintada se ubicó aguas "
  "arriba de esa desembocadura. Como no hay una estación validada en la presa, el caudal del cierre se obtuvo transfiriendo el de "
  "Puerto Valdivia, unos 35 km aguas abajo, por relación de áreas (37 267 → 35 992 km²): **1084 m³/s, o 950 mm/año**. Este valor es "
  "consistente con el caudal medio de 1010–1100 m³/s que reporta el proyecto en el sitio de presa (Alcaldía de Medellín, s. f.).")
B("Relleno de datos faltantes", "sub")
B("El balance usa solo años completos observados. Como análisis adicional, en un libro de cálculo aparte, se rellenaron los meses "
  "faltantes con regresiones log-lineales entre estaciones, ln Q_{obj} = a + b · ln Q_{pred}, corregidas con el factor de Duan (1983) "
  "para eliminar el sesgo de volver de logaritmos a caudales. Las predictoras debían tener al menos 60 meses comunes y r ≥ 0.8, y cada "
  "mes faltante se rellenó con la de mayor correlación que tuviera dato ese mes. En una validación cruzada dejando un año fuera, el "
  "índice de Nash-Sutcliffe varió entre 0.80 (La Balsa) y 0.98 (Bolombolo), con sesgos menores del 3 %. Con las series rellenadas "
  "las medias cambian 2 % o menos, y el caudal transferido al cierre queda entre 1020 y 1040 m³/s. El relleno no usa P − ETR, para no "
  "condicionar la validación del balance.")
B("Variabilidad interanual y ENSO", "sub")
B("Para comprobar la coherencia de las series se compararon las anomalías anuales del caudal y de la lluvia de la cuenca (CHIRPS v2.0) "
  "en años El Niño (1983, 1987, 1992, 1998, 2003 y 2010) y La Niña (1989, 1999, 2000, 2008 y 2011), respecto a la media 1981–2010 "
  "(Tabla 9).")
T("Anomalía media anual en años El Niño y La Niña y coeficiente de variación interanual (CV).",
  [[k, f"{sg(v[0])} % (n = {v[1]})", f"{sg(v[2])} % (n = {v[3]})", f"{v[4]:.0f} %"] for k, v in enso.items()],
  ["Serie", "El Niño", "La Niña", "CV 1981–2010"], [6, 3.3, 3.3, 3])
B(f"Todas las estaciones muestran la misma señal al mismo tiempo: caudales entre {sg(max(qn_))} % y {sg(min(qn_))} % en El Niño y entre "
  f"{sg(min(ql_))} % y {sg(max(ql_))} % en La Niña, sin saltos aislados que sugieran errores de una sola estación. La señal es mucho más "
  f"fuerte en el caudal que en la lluvia: el CV interanual del caudal es de {min(cvq):.0f}–{max(cvq):.0f} %, frente a {cv_p:.0f} % de la "
  f"lluvia, una amplificación de unas {amp:.1f} veces. La elasticidad del caudal a la lluvia que predice la curva de Budyko para "
  f"φ = 0.71 es de solo {eps_b:.1f}. Poveda et al. (2001) encontraron lo mismo a escala nacional y lo atribuyen a los cambios simultáneos "
  "de la humedad del suelo y la evapotranspiración: en El Niño, más temperatura y radiación elevan la evaporación justo cuando llueve "
  "menos. La señal es además más fuerte en los Andes occidentales, donde está la cuenca (Poveda et al., 2011).")

# ---- 8. Balance
B("Balance hídrico de largo plazo y validación", "head")
B("Para cada área de drenaje con caudal observado se promediaron la P, la ETP y la ETR de sus celdas, y se calculó el caudal "
  "estimado y su error frente al observado:")
B("Q_{est} = (P − ETR) · A / 31 557 600 s          Error = (Q_{est} − Q_{obs}) / Q_{obs}", "eq")
filas = [[r.estacion.replace(" (cierre)", ""), num(r._3), num(r._4), num(r._6), num(r._10), num(r._11, 1), num(r._8, 1), sg(r._12, 1)]
         for r in bal.itertuples()]
T("Balance hídrico de largo plazo por área de drenaje (1981–2010).", filas,
  ["Área de drenaje", "A (km²)", "P (mm)", "ETR (mm)", "P − ETR (mm)", "Q est (m³/s)", "Q obs (m³/s)", "Error (%)"],
  [3.2, 1.8, 1.6, 1.6, 1.9, 2, 2, 1.6])
F("balance_Q.png", "Caudal estimado por el balance frente al observado en las áreas de drenaje.", 12)
B("El balance reproduce los caudales observados en todas las estaciones, con errores entre −7 % y +7 %, un error absoluto medio de "
  "4.5 % y una correlación de 0.995 (Tabla 10 y Figura 12). En el cierre el error es de −5.3 %, y pasa a +0.6 % si el caudal "
  "observado se toma de la serie rellenada. El signo del error tiene un patrón espacial: en el alto Cauca y el valle (La Balsa, "
  "Juanchito, La Victoria) el balance sobrestima entre 5 % y 7 %, lo que es coherente con un caudal observado menor que el natural por "
  "la regulación de Salvajina, el riego y los acueductos; en La Virginia e Irra subestima, posiblemente por lluvia orográfica de alta "
  "montaña que las estaciones no captan; y en el cañón antioqueño los errores son de 1 % a 7 %.")
T("Sensibilidad del error en el cierre a las decisiones metodológicas.", [
    ["Base: kriging, Hargreaves, Budyko celda a celda", "−5.3 %"], ["Precipitación por IDW (p = 1.5)", "−5.6 %"],
    ["Precipitación con las 358 estaciones del mapa de estaciones", "−4.1 %"], ["ETP escalada al IDEAM (× 0.822)", "+9.3 %"],
    ["Budyko agregado (φ medio de la cuenca)", "−9.2 %"], ["Caudal observado de la serie rellenada", "+0.6 %"]],
  ["Variante", "Error en el cierre"], [11, 4])
B("Las principales fuentes de incertidumbre son:")
for t in ["Precipitación: pocas estaciones sobre 3000 m y un error de interpolación de 363 mm/año (≈ 18 % de la media).",
          "Evapotranspiración: Hargreaves sobrestima la ETP del IDEAM en un 22 %, y la curva de Budyko es empírica y no considera "
          "vegetación, suelos ni estacionalidad.",
          "Caudal: las curvas de calibración nivel–caudal tienen errores típicos del 5 al 15 %, el caudal del cierre es transferido y el "
          "río está regulado y con extracciones.",
          "Áreas de drenaje: en el valle plano el cauce del DEM se separa 3–5 km del real, lo que da una incertidumbre de ±5 % en el área "
          "de Juanchito y La Victoria.",
          "Almacenamiento: el supuesto ΔS ≈ 0 es razonable a 30 años, aunque Salvajina y los acuíferos del valle pueden almacenar agua."]:
    B(t, "bullet")
B("Poveda et al. (2007) aplicaron el mismo esquema a toda la red de drenaje de Colombia, con unas 200 estaciones de caudal, y "
  "concluyeron que ningún método de evapotranspiración superó claramente a los demás y que el error proviene sobre todo de la escasez "
  "de datos. Los resultados de esta cuenca apuntan en la misma dirección: cambiar la ETP o la forma de aplicar Budyko mueve el cierre "
  "entre −9 % y +9 %, y la mayor sensibilidad está en la lluvia de alta montaña. Un error de ±5 % está dentro de la incertidumbre de la "
  "medición de caudal, de modo que el balance de largo plazo cierra.")

# ---- 9. Productos
B("Productos globales de precipitación", "head")
B("Se evaluaron tres productos de precipitación de cobertura global. Antes de usarlos se verificó que cubren toda la cuenca y que "
  "tienen un periodo común completo, 1981–2025 (540 meses). Para el balance se usó 1981–2010, el mismo periodo de la precipitación, la "
  "temperatura y los caudales, de modo que las diferencias entre fuentes se deban al producto y no al periodo.")
T("Productos de precipitación evaluados.", [
    ["CHIRPS v2.0", "Satélite infrarrojo combinado con estaciones (Funk et al., 2015)", "0.05° (≈ 5.5 km)", "1171", "IRI Data Library"],
    ["ERA5-Land", "Reanálisis de superficie terrestre forzado por ERA5 (Muñoz-Sabater et al., 2021)", "0.1° (≈ 11 km)", "294", "Curso"],
    ["ERA5", "Reanálisis atmosférico global (Hersbach et al., 2020)", "0.25° (≈ 28 km)", "46", "Curso"],
    ["CHIRPS v3.0", "Nueva versión de CHIRPS (análisis de sensibilidad)", "0.05°", "1171", "Curso"]],
  ["Producto", "Tipo y referencia", "Resolución", "Celdas en la cuenca", "Fuente"], [2.3, 6.6, 2.6, 1.8, 2.3])
B("Cada producto se convirtió a mm/mes y se recortó a la cuenca; los valores de relleno negativos sobre el mar (CHIRPS v3.0) se "
  "filtraron. Las sumas anuales se promediaron en 1981–2010 y se llevaron a la grilla de 90 m por vecino más cercano, sin suavizar su "
  "resolución original. La lectura se verificó con la lluvia de lugares de referencia: en Quibdó, ERA5 da 8081 mm/año y CHIRPS "
  "8195 mm/año, valores razonables, mientras que en Manizales ERA5 da 15 164 mm/año y CHIRPS 2361 mm/año. Que ERA5 acierte en el Chocó "
  "y falle en los Andes descarta un error de unidades y apunta a un sesgo del producto sobre la cordillera.")
B("Se eligió CHIRPS v2.0 como producto principal porque es la versión publicada y más citada; se descargó de la IRI Data Library, ya "
  "que el archivo del curso corresponde a la versión 3.0. Esta última se evaluó como sensibilidad: da 11 % más lluvia que la v2.0 sobre "
  "la cuenca, con un patrón espacial similar, y lleva el error del balance en el cierre a +14 %.")

# ---- 10. Mapas por producto
B("Precipitación media anual según cada producto", "head")
F("panel_P_productos.png", "Precipitación media anual 1981–2010 del IDEAM (kriging), CHIRPS v2.0, ERA5-Land y ERA5. "
  "Un mismo valor tiene el mismo color en los cuatro mapas; cada barra llega hasta el máximo de su mapa.", 15.5)
T("Precipitación media anual de la cuenca según cada fuente (1981–2010).",
  [[k, num(r["P media cuenca (mm/año)"]), f"{num(r['mínimo (mm/año)'])}–{num(r['máximo (mm/año)'])}", f"{sg(r['sesgo vs IDEAM (%)'])} %",
    f"{r['correlación espacial con IDEAM']:.2f}".replace("-", "−")] for k, r in rp.iterrows()],
  ["Fuente", "P media (mm/año)", "Rango (mm/año)", "Sesgo frente al IDEAM", "r espacial con el IDEAM"], [3.5, 3, 3.6, 3, 3])
F("panel_razon_IDEAM.png", "Razón entre la precipitación de cada producto y la interpolada con estaciones del "
  "IDEAM.", 14)
B("CHIRPS v2.0 reproduce el patrón y la magnitud de la lluvia del IDEAM, con un sesgo de +2 % y una correlación espacial de 0.89 "
  "(Tabla 13 y Figura 13). Parte de ese acuerdo es esperable, porque CHIRPS incorpora estaciones en su construcción; sin embargo, "
  "López-Bermeo et al. (2022) lo validaron en Antioquia contra 75 pluviómetros independientes y encontraron que representa bien la "
  "lluvia en la mayoría de las condiciones, incluso en los ENSO más intensos, y que funciona mejor en las subregiones andinas.")
B("ERA5 y ERA5-Land triplican la lluvia de la cuenca, con medias cercanas a 5970 mm/año y máximos de 18 000 a 20 000 mm/año sobre la "
  "cordillera, y su patrón espacial no se parece al observado (r ≈ −0.06): ubican la lluvia máxima en las crestas y no reproducen la "
  "sombra de lluvia del valle (Figura 14). Vega-Durán et al. (2021) también encontraron que ERA5 sobrestima de forma consistente los "
  "promedios mensuales de las estaciones del IDEAM en la cuenca del Sinú, aunque con un sesgo mucho menor que el obtenido aquí. La "
  "diferencia es coherente con la topografía: a 0.1–0.25° de resolución la cordillera se suaviza, la convección parametrizada concentra "
  "la lluvia en las laderas de barlovento y el valle interandino del Cauca no se resuelve. ERA5-Land hereda la lluvia de ERA5, y por eso "
  "ambos productos son casi idénticos.")

# ---- 11. Balance con productos
B("Balance hídrico con cada producto", "head")
B("Se repitió el balance de la sección 8 cambiando solo la precipitación. La ETP de Hargreaves, las áreas de drenaje y los caudales "
  "observados son los mismos, y la ETR de Budyko se recalculó celda a celda con la P de cada producto.")
hid = bp[bp.codigo == "HIDRO"].set_index("producto")
ro = hid.Qobs.iloc[0] * 365.25 * 86400 / (A * 1e6) * 1000
T("Balance hídrico en el cierre (Hidroituango, 1981–2010) con cada fuente de precipitación.",
  [[k, num(r.P), num(r.ETR), num(r.R), num(ro), sg(r.err, 1)] for k, r in hid.iterrows()]
  + [["CHIRPS v3.0 (sensibilidad)", "2 202", "1 118", "1 084", num(ro), "+14.1"]],
  ["Producto", "P (mm/año)", "ETR (mm/año)", "Q estimado (mm/año)", "Q observado (mm/año)", "Error (%)"], [4.2, 2.3, 2.3, 2.6, 2.6, 2])
T("Desempeño del balance en las nueve estaciones de caudal (sin el cierre).",
  [[k, sg(r.sesgo, 1), f"{r.MAE:.1f}", f"{r.RMSE:.1f}", f"{r.r:.3f}"] for k, r in des.iterrows()],
  ["Fuente", "Sesgo medio (%)", "Error absoluto medio (%)", "RMSE relativo (%)", "r (Q est – Q obs)"], [3.4, 3, 3.4, 3, 3])
F("panel_R_productos.png", "Escorrentía de largo plazo R = P − ETR con cada fuente de precipitación (misma ETP de "
  "Hargreaves).", 15.5)
B("Con CHIRPS v2.0 el balance cierra con un error de −2.2 % y un error absoluto medio de 5.3 % en las estaciones, prácticamente igual "
  "que con el IDEAM (Tablas 14 y 15). Con ERA5 y ERA5-Land el caudal estimado es casi cinco veces el observado (+390 %). La alta "
  "correlación entre caudal estimado y observado que se obtiene incluso con ERA5 (0.97) no es mérito del producto: refleja que el "
  "caudal crece con el área de drenaje con cualquier fuente. Lo que diferencia a los productos es el sesgo.")
B("Para separar el error de la precipitación del error de la ETP y de la curva de Budyko, se calculó la **P necesaria** en cada área de "
  "drenaje: la precipitación que, con la misma ETP y la curva de Budyko, reproduciría exactamente el caudal observado. Se obtuvo "
  "resolviendo P − ETR(P) = R_{obs} con el método de Brent. Con el IDEAM y CHIRPS v2.0 la corrección necesaria va de −5 % a +4 %, "
  "dentro del error de interpolación, lo que indica que la combinación Hargreaves + Budyko es consistente con los caudales. Con ERA5 y "
  "ERA5-Land habría que reducir la lluvia entre 47 % y 74 %: la ETR «observada» (P − Q_{obs}) sería el 72–88 % de su P con φ de "
  "0.20–0.32, fuera de la curva de Budyko, y ningún ajuste razonable de la ETP compensa ese exceso. Por último, la comparación punto a "
  "píxel en las 259 estaciones da un RMSE de 369 mm/año para CHIRPS, igual al error del kriging en la validación cruzada (366 mm/año), "
  "frente a unos 6300 mm/año y r ≈ 0.06 para ERA5.")

# ---- 12. Ciclo anual
B("Ciclo anual y régimen de precipitación", "head")
B("Para cada mes se interpoló la normal mensual 1981–2010 de las estaciones del IDEAM con kriging ordinario, con un variograma ajustado "
  "a ese mes. Los doce mapas usan la misma escala de color (Figura 16), y el ciclo anual es el promedio de cada mapa sobre la cuenca "
  "(Figura 17 y Tabla 16).")
F("panel_P_mensual.png", "Precipitación media mensual 1981–2010 (kriging de estaciones del IDEAM), con la misma escala "
  "de color en los doce meses.", 15.5)
F("ciclo_anual.png", "Ciclo anual de la precipitación media de la cuenca.", 12.5)
mm = cic["P media cuenca (mm)"].mean()
T("Precipitación media mensual de la cuenca (1981–2010).",
  [[r.mes.capitalize(), num(r._2), f"{r._4:.1f}", "húmedo" if r._2 > mm + 1 else ("límite" if abs(r._2 - mm) <= 1 else "seco")]
   for r in cic.itertuples()],
  ["Mes", "P (mm)", "% del total anual", "Clasificación"], [3, 3, 3.5, 3.5], primera_izq=False)
nuevo.append(par(f"Mes húmedo: precipitación mayor que la media mensual de la cuenca ({mm:.0f} mm); seco: menor.", "nota"))
F("estacionalidad.png", "Mes de máxima lluvia, número de picos del ciclo anual e índice de estacionalidad de Walsh y "
  "Lawler en cada celda.", 15.5)
B("La cuenca tiene un régimen bimodal, con dos temporadas de lluvia y dos secas, explicado por la migración meridional de la ZCIT, que "
  "pasa dos veces al año sobre los Andes colombianos, modulada por la topografía (Mejía et al., 1999; Poveda, 2004). Los meses húmedos "
  "son marzo, abril y mayo, con máximo en abril (218 mm), y octubre y noviembre, con máximo en octubre (240 mm); la segunda temporada "
  "es la más intensa. Los secos son diciembre a febrero, con mínimo en febrero (120 mm), y junio a agosto, con mínimo en agosto "
  "(114 mm); septiembre está en el límite, como transición hacia la temporada de octubre.")
B("El régimen es bimodal en el 99.8 % del área. El máximo anual ocurre en octubre o noviembre en el 63 % de la cuenca y en abril o mayo "
  "en el 37 % (Figura 18). El índice de estacionalidad de Walsh y Lawler (1981), SI = (1/R) · Σ |P_{m} − R/12|, va de 0.17 a 0.42, con "
  "una media de 0.29: la lluvia está bien repartida a lo largo del año, sin una estación seca marcada. Para la presa, las dos "
  "temporadas secas implican dos estiajes por año, de los cuales el de julio-agosto es el más severo, en concordancia con los caudales "
  "descritos en la zona de estudio.")

# ---- 13. Comparación de ciclos
B("Comparación del ciclo anual entre productos", "head")
B("El ciclo anual de cada producto, como promedio de la cuenca, se comparó con el del IDEAM (n = 12 meses) mediante el sesgo, la raíz "
  "del error cuadrático medio (RMSE) y la correlación de Pearson. Se añadió el diagrama de Taylor (Taylor, 2001), que resume en una sola "
  "figura la correlación, la desviación estándar normalizada y el RMSE centrado.")
F("ciclos_productos.png", "Ciclo anual de la precipitación media de la cuenca según cada fuente.", 13)
F("taylor.png", "Diagrama de Taylor de los ciclos anuales frente al IDEAM.", 10)
T("Métricas del ciclo anual frente al IDEAM (n = 12).",
  [[k, f"{sg(r['Sesgo (mm/mes)'], 1)} ({sg(r['Sesgo (%)'], 1)} %)", f"{r['RMSE (mm/mes)']:.1f}", f"{r['r']:.3f}", f"{r['σ normalizada']:.2f}",
    r["Meses de máximos (2 picos)"], r["Mes mínimo"]] for k, r in mc.drop("IDEAM").iterrows()],
  ["Producto", "Sesgo (mm/mes)", "RMSE (mm/mes)", "r", "σ normalizada", "Máximos", "Mínimo"], [2.4, 3.4, 2.3, 1.6, 2.2, 2.2, 1.8])
B("CHIRPS v2.0 es el mejor producto en todos los criterios: en el ciclo anual tiene r = 0.998, un sesgo de +1.4 % y un RMSE de "
  "4.8 mm/mes, y queda casi sobre la referencia en el diagrama de Taylor (Figura 20); en el mapa anual tiene r = 0.89 y +2 % de sesgo; "
  "y su balance cierra con −2.2 %. ERA5 y ERA5-Land, en cambio, triplican la lluvia (sesgo de +199 %), desplazan el máximo del ciclo a "
  "abril-mayo cuando el observado es octubre-noviembre, y tienen r de 0.62–0.69 y una desviación estándar normalizada de 1.6, lejos "
  "de la referencia. Entre ellos, ERA5-Land es apenas mejor, porque hereda la precipitación de ERA5.")
B("Una limitación de esta evaluación es que el ciclo de referencia es el kriging de las mismas estaciones que CHIRPS usa para corregirse, "
  "de modo que su buen ajuste está en parte asegurado. La prueba independiente es el balance con los caudales observados (sección 11), "
  "y en ella CHIRPS también cierra.")

# ---- 14. Decisiones y análisis adicionales
B("Decisiones metodológicas y análisis adicionales", "head")
B("La Tabla 18 reúne los análisis que se hicieron por fuera de lo que pide el enunciado, y los que se consideraron y no se aplicaron, "
  "con su justificación.")
T("Análisis estadísticos y técnicas adicionales.", [
    ["Relleno de caudales por regresión log-lineal con corrección de Duan", "Sí", "NSE 0.80–0.98; las medias cambian 2 % o menos"],
    ["Validación cruzada (estación fuera y año fuera)", "Sí", "Elección del interpolador y verificación del relleno"],
    ["Variograma por mínimos cuadrados ponderados (Cressie, 1985)", "Sí", "Pepita realista (21 % de la meseta)"],
    ["Correlación de Pearson y de Spearman", "Sí", "T–Z, P–Z (r = 0.18; ρ = 0.30), r espacial, ciclos"],
    ["Intervalo de confianza del 95 % y residuos estandarizados", "Sí", "Gradientes T–Z; atípicos marcados y conservados"],
    ["Índice de estacionalidad de Walsh y Lawler", "Sí", "SI 0.17–0.42"],
    ["Diagrama de Taylor", "Sí", "Comparación de ciclos (opcional en el enunciado)"],
    ["P necesaria por inversión de Budyko (método de Brent)", "Sí", "Separa el error de P del de ETP y Budyko"],
    ["Compuestos ENSO y elasticidad de Budyko", "Sí", f"Amplificación ≈ {amp:.1f} frente a {eps_b:.1f} teórica"],
    ["Análisis de sensibilidad", "Sí", "Método de P, estaciones, ETP, Budyko agregado, CHIRPS v3.0, caudal rellenado"],
    ["EOF / componentes principales, análisis espectral singular, Fourier, ondículas", "No",
     "El trabajo usa climatologías de 30 años; el ENSO se evaluó con compuestos"],
    ["Correlación no lineal, regresión logística, KNN", "No", "Spearman bastó para P–Z; no hay respuesta binaria; el relleno ya tenía NSE ≥ 0.80"],
    ["Quantile mapping", "No", "El enunciado pide evaluar los productos sin corregir"]],
  ["Análisis", "¿Aplicado?", "Resultado o razón"], [6.8, 1.8, 7.2])

# ---- Conclusiones
B("Conclusiones", "title")
for t in [
    f"La cuenca aportante a Hidroituango ({num(A)} km²) recibe 1985 mm/año de lluvia, evapora 1085 mm/año (55 %) y produce 900 mm/año de "
    "escorrentía, unos 1026 m³/s en la presa, valor consistente con el caudal observado transferido (1020–1084 m³/s) y con el que reporta "
    "el proyecto (1010–1100 m³/s).",
    "El balance Q = P − ETR, con kriging, Hargreaves-Samani y Budyko celda a celda, reproduce los caudales observados con errores de ±7 % "
    "en nueve estaciones y de −5.3 % en el cierre, dentro de la incertidumbre de la medición de caudales y de la interpolación de la "
    "lluvia, como en los balances nacionales de Poveda et al. (2007).",
    "La temperatura depende casi solo de la elevación (R² > 0.96), con gradientes de 7.3, 6.4 y 5.7 °C/km para Tmax, Tmed y Tmin. "
    "Hargreaves sobrestima la ETP del IDEAM en un 22 %, como se ha reportado en la zona cafetera (Ramírez et al., 2011), pero conserva su "
    "patrón espacial.",
    "Las mayores incertidumbres son la lluvia de alta montaña, la regulación y las extracciones en el alto Cauca y el valle, y la falta "
    "de una estación de caudal validada en la presa.",
    f"Los caudales responden al ENSO con una variabilidad interanual {amp:.1f} veces mayor que la de la lluvia, más de lo que predice la "
    "curva de Budyko, lo que confirma el papel de la humedad del suelo y la evapotranspiración (Poveda et al., 2001) y la sensibilidad de "
    "la oferta hídrica de Hidroituango a El Niño.",
    "CHIRPS v2.0 es el producto más adecuado para balances en esta cuenca: +2 % de lluvia, cierre de −2.2 % y r = 0.998 en el ciclo "
    "anual. ERA5 y ERA5-Land triplican la lluvia, ubican mal su patrón espacial y su ciclo, y producen un balance físicamente imposible; "
    "no deben usarse sin corrección de sesgo.",
    "La lluvia es bimodal en casi toda la cuenca, con la temporada principal en octubre-noviembre y el estiaje más severo en julio-agosto, "
    "lo que define dos periodos críticos al año para la operación del embalse."]:
    B(t, "bullet")

# ---- Referencias
B("Referencias", "title")
REFS = [
    "Alcaldía de Medellín. (s. f.). *Hidroituango es pura energía y confianza para Colombia*. https://www.medellin.gov.co/es/sala-de-"
    "prensa/noticias/hidroituango-es-pura-energia-y-confianza-para-colombia/",
    "Allen, R. G., Pereira, L. S., Raes, D. y Smith, M. (1998). *Crop evapotranspiration: Guidelines for computing crop water "
    "requirements* (FAO Irrigation and Drainage Paper 56). FAO.",
    "Barco, J., Cuartas, A., Mesa, O., Poveda, G., Vélez, J. I., Mantilla, R., Hoyos, C., Mejía, J. F., Botero, B. y Montoya, M. (2000). "
    "Estimación de la evaporación en Colombia. *Avances en Recursos Hidráulicos*, 7, 43–51.",
    "Barnes, R., Lehman, C. y Mulla, D. (2014). Priority-flood: An optimal depression-filling and watershed-labeling algorithm for digital "
    "elevation models. *Computers & Geosciences*, 62, 117–127.",
    "Budyko, M. I. (1974). *Climate and life*. Academic Press.",
    "Carvajal, Y., Jiménez, H. y Materón, H. (1998). Incidencia del fenómeno ENSO en la hidroclimatología del valle del río Cauca, "
    "Colombia. *Bulletin de l'Institut Français d'Études Andines*, 27(3), 743–751.",
    "Chaves, B. y Jaramillo, A. (1999). Regionalización de la temperatura del aire en Colombia. *Avances en Recursos Hidráulicos*, 6, "
    "37–42.",
    "Cressie, N. (1985). Fitting variogram models by weighted least squares. *Mathematical Geology*, 17(5), 563–586.",
    "Duan, N. (1983). Smearing estimate: A nonparametric retransformation method. *Journal of the American Statistical Association*, "
    "78(383), 605–610.",
    "Eslava, J. (1992). Perfil altitudinal de la temperatura media del aire en Colombia. *Earth Sciences Research Journal*, 1(1), 37–52.",
    "European Space Agency. (2021). *Copernicus Global Digital Elevation Model (GLO-30)*. OpenTopography.",
    "Funk, C., Peterson, P., Landsfeld, M., Pedreros, D., Verdin, J., Shukla, S., Husak, G., Rowland, J., Harrison, L., Hoell, A. y "
    "Michaelsen, J. (2015). The climate hazards infrared precipitation with stations—a new environmental record for monitoring "
    "extremes. *Scientific Data*, 2, 150066.",
    "Hargreaves, G. H. y Samani, Z. A. (1985). Reference crop evapotranspiration from temperature. *Applied Engineering in Agriculture*, "
    "1(2), 96–99.",
    "Hersbach, H. et al. (2020). The ERA5 global reanalysis. *Quarterly Journal of the Royal Meteorological Society*, 146(730), "
    "1999–2049.",
    "Hoyos, I., Dominguez, F., Cañón-Barriga, J., Martínez, J. A., Nieto, R., Gimeno, L. y Dirmeyer, P. A. (2018). Moisture origin and "
    "transport processes in Colombia, northern South America. *Climate Dynamics*, 50, 971–990.",
    "Hoyos, N., Escobar, J., Restrepo, J. C. et al. (2013). Impact of the 2010–2011 La Niña phenomenon in Colombia, South America: The "
    "human toll of an extreme weather event. *Applied Geography*, 39, 16–25.",
    "IDEAM. (2026). *Promedios climatológicos 1981–2010; caudales medios diarios (HidrologiaNacionalDiaria); Catálogo Nacional de "
    "Estaciones*. Instituto de Hidrología, Meteorología y Estudios Ambientales.",
    "La República. (20 de marzo de 2019). La oferta hidráulica equivale a cerca de 69 % de la matriz energética del país. "
    "https://www.larepublica.co/especiales/minas-y-energia-marzo-2019/la-oferta-hidraulica-equivale-a-cerca-de-69-de-la-matriz-"
    "energetica-del-pais-2842181",
    "Lehner, B., Verdin, K. y Jarvis, A. (2008). New global hydrography derived from spaceborne elevation data. *Eos*, 89(10), 93–94.",
    "López-Bermeo, C. et al. (2022). Validation of the accuracy of the CHIRPS precipitation dataset at representing climate variability "
    "in a tropical mountainous region of South America. *Physics and Chemistry of the Earth*, 127, 103184.",
    "Mejía, J. F., Mesa, O., Poveda, G. et al. (1999). Distribución espacial y ciclos anual y semianual de la precipitación en Colombia. "
    "*DYNA*, 127, 7–24.",
    "Minambiente. (s. f.). *Plataforma colaborativa 2: cuenca alta del río Cauca*. Ministerio de Ambiente y Desarrollo Sostenible.",
    "Muñoz-Sabater, J. et al. (2021). ERA5-Land: A state-of-the-art global reanalysis dataset for land applications. *Earth System Science "
    "Data*, 13, 4349–4383.",
    "Poveda, G. (2004). La hidroclimatología de Colombia: una síntesis desde la escala inter-decadal hasta la escala diurna. *Revista de "
    "la Academia Colombiana de Ciencias Exactas, Físicas y Naturales*, 28(107), 201–221.",
    "Poveda, G., Álvarez, D. M. y Rueda, O. A. (2011). Hydro-climatic variability over the Andes of Colombia associated with ENSO: A "
    "review of climatic processes and their impact on one of the Earth's most important biodiversity hotspots. *Climate Dynamics*, 36, "
    "2233–2249.",
    "Poveda, G., Jaramillo, A., Gil, M. M., Quiceno, N. y Mantilla, R. I. (2001). Seasonality in ENSO-related precipitation, river "
    "discharges, soil moisture, and vegetation index in Colombia. *Water Resources Research*, 37(8), 2169–2178.",
    "Poveda, G., Vélez, J. I., Mesa, O. J. et al. (2007). Linking long-term water balances and statistical scaling to estimate river flows "
    "along the drainage network of Colombia. *Journal of Hydrologic Engineering*, 12(1), 4–13.",
    "Ramírez, V. H., Mejía, A., Marín, E. V. y Arango, R. (2011). Evaluation of models for estimating the reference evapotranspiration in "
    "Colombian coffee zone. *Agronomía Colombiana*, 29(1), 107–114.",
    "Taylor, K. E. (2001). Summarizing multiple aspects of model performance in a single diagram. *Journal of Geophysical Research*, "
    "106(D7), 7183–7192.",
    "Vega-Durán, J., Escalante-Castro, B., Canales, F. A., Acuña, G. J. y Kaźmierczak, B. (2021). Evaluation of areal monthly average "
    "precipitation estimates from MERRA2 and ERA5 reanalysis in a Colombian Caribbean basin. *Atmosphere*, 12(11), 1430.",
    "Walsh, R. P. D. y Lawler, D. M. (1981). Rainfall seasonality: Description, spatial patterns and change through time. *Weather*, "
    "36(7), 201–208."]
import unicodedata  # noqa: E402
for r in sorted(REFS, key=lambda s: unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore")):
    B(r, "ref")

# ---- inserción al final del cuerpo (antes de sectPr)
sect = body[-1] if body[-1].tag == qn("w:sectPr") else None
for el in nuevo:
    el.getparent().remove(el) if el.getparent() is not None else None
    if sect is not None:
        sect.addprevious(el)
    else:
        body.append(el)

# fuentes heredadas de Google Docs (Gungsuh, Caudex) → Times New Roman, como el resto del texto
for rf in body.iter(qn("w:rFonts")):
    if rf.get(qn("w:ascii")) in ("Gungsuh", "Caudex"):
        for k in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            rf.set(qn(k), "Times New Roman")

doc.save(SALIDA)
print(SALIDA, f"figuras hasta {NF[0]}, tablas hasta {NT[0]}")
