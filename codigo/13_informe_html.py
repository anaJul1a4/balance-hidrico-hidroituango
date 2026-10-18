"""
Informe interactivo del Trabajo 1 (una pestaña por punto de la rúbrica).

Todas las figuras son interactivas (Plotly): los mapas son rásteres agregados a ~1.2 km con zoom y valor por celda;
las series permiten zoom y lectura de picos. El contenido se limita a lo que pide el enunciado más una
justificación breve de las decisiones metodológicas.

Lee trabajo1/resultados y escribe trabajo1/informe_html/index.html (local) e informe_artifact.html (publicación).
"""
import html
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from openpyxl import load_workbook
from scipy.spatial.distance import pdist

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "trabajo1" / "resultados"
DAT = ROOT / "trabajo1" / "datos"
OUT = ROOT / "trabajo1" / "informe_html"
OUT.mkdir(parents=True, exist_ok=True)
SEG = 365.25 * 86400
F = 13                                   # bloque de agregación: 13 × 90 m ≈ 1.17 km


# ----------------------------------------------------------------------------- utilidades
def raster(p, dec=0):
    with rasterio.open(p) as s:
        a = s.read(1).astype("float64"); a[a == s.nodata] = np.nan; t = s.transform
    h, w = a.shape[0] // F * F, a.shape[1] // F * F
    b = a[:h, :w].reshape(h // F, F, w // F, F)
    with np.errstate(all="ignore"):
        m = np.nanmean(b, axis=(1, 3))
        m[np.isnan(b).mean(axis=(1, 3)) > 0.5] = np.nan
    z = [[None if np.isnan(v) else (round(float(v), dec) if dec else int(round(v))) for v in fila] for fila in m]
    x = [round(t.c + t.a * F * (j + 0.5)) for j in range(m.shape[1])]
    y = [round(t.f + t.e * F * (i + 0.5)) for i in range(m.shape[0])]
    return {"x": x, "y": y, "z": z}


def lineas(geoms, tol):
    xs, ys = [], []
    for g in geoms:
        g = g.simplify(tol)
        partes = getattr(g, "geoms", [g])
        for p in partes:
            c = np.asarray(p.exterior.coords if p.geom_type == "Polygon" else p.coords)
            xs += [round(v) for v in c[:, 0]] + [None]; ys += [round(v) for v in c[:, 1]] + [None]
    return {"x": xs, "y": ys}


def fmt(v, f=",.0f"):
    return format(v, f).replace(",", " ")


def tabla(df, titulo, f=None, nota=""):
    f = f or {}
    cab = "".join(f"<th>{html.escape(str(c))}</th>" for c in [df.index.name or ""] + list(df.columns))
    filas = ""
    for i, r in df.iterrows():
        celdas = f"<th>{html.escape(str(i))}</th>"
        for c, v in r.items():
            if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
                celdas += f"<td class='n'>{'—' if pd.isna(v) else fmt(v, f.get(c, ',.1f'))}</td>"
            else:
                celdas += f"<td>{html.escape(str(v))}</td>"
        filas += f"<tr>{celdas}</tr>"
    return (f"<div class='tw'><table><caption>{titulo}</caption><thead><tr>{cab}</tr></thead><tbody>{filas}</tbody></table>"
            + (f"<p class='nota'>{nota}</p>" if nota else "") + "</div>")


def bloque(cid, texto, alto="mapa"):
    """Figura interactiva a la izquierda y texto a la derecha (o debajo en pantallas angostas)."""
    return f"<div class='fila'><div class='plot {alto}' id='{cid}'></div><div class='texto'>{texto}</div></div>"


def ancho(cid, texto, alto="serie", extra=""):
    return f"<div class='plot {alto}' id='{cid}'></div>{extra}<div class='pie'>{texto}</div>"


IMG = OUT / "img"
IMG.mkdir(exist_ok=True)


def figura(src, nombre, titulo, nota="", ancho_px=1800):
    """Figura estática (mapas y paneles tal cual se generaron), convertida a WebP; clic para ampliar."""
    from PIL import Image
    im = Image.open(RES / src).convert("RGB")
    if im.width > ancho_px:
        im = im.resize((ancho_px, round(im.height * ancho_px / im.width)), Image.LANCZOS)
    im.save(IMG / f"{nombre}.webp", "WEBP", quality=88, method=6)
    ruta = f"img/{nombre}.webp"
    return (f"<figure class='fig'><button type='button' class='zoom' data-src='{ruta}' aria-label='Ampliar: {html.escape(titulo)}'>"
            f"<img src='{ruta}' width='{im.width}' height='{im.height}' loading='lazy' alt='{html.escape(titulo)}'></button>"
            f"<figcaption><b>{titulo}.</b> {nota}</figcaption></figure>")


def lado(fig, texto):
    """Mapa alto a la izquierda, texto paralelo a la derecha."""
    return f"<div class='fila'><div class='figcol'>{fig}</div><div class='texto'>{texto}</div></div>"


def abajo(figs, texto="", cols=1):
    """Figuras a todo el ancho (paneles o pares de mapas) y el texto debajo en dos columnas."""
    return f"<div class='figs c{cols}'>{figs}</div><div class='cols'>{texto}</div>"


def dec(items):
    return "<h3>Decisiones</h3><ul class='dec'>" + "".join(f"<li><b>{a}.</b> {b}</li>" for a, b in items) + "</ul>"


# ----------------------------------------------------------------------------- datos
D = RES / "01_delimitacion"
cuenca = gpd.read_file(D / "cuenca_cauca_hidroituango.gpkg", layer="cuenca")
rio = gpd.read_file(D / "cuenca_cauca_hidroituango.gpkg", layer="rio_principal")
dren = gpd.read_file(D / "cuenca_cauca_hidroituango.gpkg", layer="drenajes")
cierre = gpd.read_file(D / "cuenca_cauca_hidroituango.gpkg", layer="punto_cierre").geometry[0]
morf = pd.read_csv(D / "parametros_morfometricos.csv", index_col=0).valor
vc = pd.read_csv(D / "verificacion_cierre.csv", index_col=0).iloc[:, 0]
perfil = np.load(D / "perfil_rio_principal.npy")[::8]

cvP = pd.read_csv(RES / "04_precipitacion_interpolada" / "validacion_cruzada.csv", index_col=0)
resP = pd.to_numeric(pd.read_csv(RES / "04_precipitacion_interpolada" / "resumen_precipitacion.csv", index_col=0).valor, errors="coerce")
vario_txt = pd.read_csv(RES / "04_precipitacion_interpolada" / "resumen_precipitacion.csv", index_col=0).valor.filter(like="Variograma").iloc[0]
c0, cc, rg = [float(v) for v in vario_txt.split("/")]

ep = gpd.read_file(RES / "03_estaciones_precipitacion" / "estaciones_precipitacion.gpkg")
ep["zona"] = ep.CODIGO.astype(int).astype(str).str.zfill(8).str[:2]
ep = ep[(ep.dentro | (ep.zona == "26")) & (ep.CODIGO.astype(int) != 26230160)]
xyP, zP = np.c_[ep.geometry.x, ep.geometry.y], ep.ANUAL.to_numpy()
h, sv = pdist(xyP), 0.5 * pdist(zP[:, None], "sqeuclidean")
bins = np.linspace(0, 100_000, 21); k = np.digitize(h, bins) - 1
vario = {"h": [round(h[k == i].mean() / 1000, 1) for i in range(20)], "g": [round(sv[k == i].mean()) for i in range(20)],
         "n": [int((k == i).sum()) for i in range(20)], "c0": c0, "c": cc, "a": rg}

coefT = pd.read_csv(RES / "05_temperatura_elevacion" / "coeficientes_T_Z.csv", index_col=0)
wb = load_workbook(RES / "05_temperatura_elevacion" / "Punto4_temperatura_elevacion.xlsx", read_only=True)
eT = pd.DataFrame([r[:7] for r in wb["Datos_anuales"].iter_rows(min_row=2, values_only=True) if r[0]],
                  columns=["cod", "nombre", "municipio", "Z", "Tmax", "Tmin", "Tmed"])
resT = pd.read_csv(RES / "07_mapas_temperatura" / "resumen_temperatura.csv", index_col=0)
etpm = pd.read_csv(RES / "08_etp_etr" / "ETP_mensual_cuenca.csv", index_col=0)
cETP = pd.read_csv(RES / "08_etp_etr" / "contraste_ETP_IDEAM.csv", index_col=0).iloc[:, 0]
resB = pd.read_csv(RES / "08_etp_etr" / "resumen_balance_largo_plazo.csv", index_col=0)["media cuenca"]
bal = pd.read_csv(RES / "09_balance" / "balance_subcuencas.csv", dtype={"codigo": str})
wb = load_workbook(RES / "09_balance" / "Punto9_balance_hidrico.xlsx", read_only=True)
hdr = [c.value for c in next(wb["Sensibilidad"].iter_rows(min_row=1, max_row=1))]
sens = pd.DataFrame(list(wb["Sensibilidad"].iter_rows(min_row=2, max_row=11, values_only=True)), columns=hdr)

disp = pd.read_csv(DAT / "caudales_ideam" / "disponibilidad_caudales.csv", dtype={"codigo": str})
val = disp[disp["apta (>=15 anos 1981-2010)"] == True].copy()
cat = pd.DataFrame(json.load(open(DAT / "catalogo_ideam_zona26_hidrometricas.json", encoding="utf-8"))).drop_duplicates("codigo")
cat["codigo"] = cat.codigo.str[2:]
val = val.merge(cat[["codigo", "municipio", "departamento", "latitud", "longitud"]], on="codigo")
sub = gpd.read_file(RES / "06_caudales" / "subcuencas_estaciones.gpkg", layer="areas_drenaje")
pts = gpd.read_file(RES / "06_caudales" / "subcuencas_estaciones.gpkg", layer="estaciones")
val = val.merge(pts[["codigo", "area_km2_DEM"]], on="codigo")
Qm = pd.read_csv(DAT / "caudales_ideam" / "Q_mensual_completa.csv", index_col=0, parse_dates=True)
anual = lambda s: s.groupby(s.index.year).apply(lambda x: x.mean() if x.count() == 12 else np.nan)
val["Q"] = [anual(Qm.loc["1981":"2010", c]).mean() for c in val.codigo]
val["anos"] = [int(anual(Qm.loc["1981":"2010", c]).count()) for c in val.codigo]
val = val.sort_values("area_km2_DEM").reset_index(drop=True)
nom = lambda s: s.title().replace("Puerto", "Pto.").replace("Puente", "Pte.")

# ----------------------------------------------------------------------------- datos para las figuras
R = RES
DATA = {
    "base": {"cuenca": lineas(cuenca.geometry, 300), "rio": lineas(rio.geometry, 300),
             "cierre": [round(cierre.x), round(cierre.y)]},
    "dren": lineas(dren[dren.orden >= 3].geometry, 400),
    "perfil": {"d": perfil[:, 0].round(1).tolist(), "z": perfil[:, 1].round(0).tolist()},
    "estP": {"x": ep.geometry.x.round().tolist(), "y": ep.geometry.y.round().tolist(), "n": ep.NOMBRE.tolist(),
             "p": ep.ANUAL.round().tolist(), "z": ep.ELEV.tolist()},
    "vario": vario,
    "tz": {"n": eT.nombre.tolist(), "m": eT.municipio.tolist(), "Z": eT.Z.astype(float).tolist(),
           **{v: eT[v].astype(float).round(2).tolist() for v in ["Tmax", "Tmin", "Tmed"]},
           "coef": {v: [coefT.loc[v, "T0"], coefT.loc[v, "alfa"], coefT.loc[v, "R2"]] for v in ["Tmax", "Tmin", "Tmed"]}},
    "etpm": etpm["ETP_m media cuenca (mm)"].round(1).tolist(),
    "sub": [{"n": nom(r.estacion), **lineas([g], 800)} for r, g in zip(sub.itertuples(), sub.geometry)],
    "estQ": {"x": pts.set_index("codigo").loc[val.codigo].geometry.x.round().tolist(),
             "y": pts.set_index("codigo").loc[val.codigo].geometry.y.round().tolist(),
             "n": [nom(s) for s in val.estacion], "A": val.area_km2_DEM.round().tolist(), "Q": val.Q.round(1).tolist()},
    "serie": {"t": [d.strftime("%Y-%m") for d in Qm.index],
              "q": {nom(r.estacion): [None if pd.isna(v) else round(v, 1) for v in Qm[r.codigo]] for r in val.itertuples()}},
    "bal": {"n": [nom(s).replace(" (Cierre)", "") for s in bal.estacion], "obs": bal["Q obs (m³/s)"].round(1).tolist(),
            "est": bal["Q est"].round(1).tolist(), "err": bal["error %"].round(1).tolist(),
            "P": bal["P (mm/año)"].round().tolist(), "ETR": bal["ETR Budyko celda a celda (mm/año)"].round().tolist(),
            "A": bal["A (km²)"].round().tolist()},
}

prod = pd.read_csv(RES / "10_productos" / "P_anual_cuenca_productos.csv", index_col=0)
cobP = pd.read_csv(RES / "10_productos" / "cobertura_productos.csv", index_col=0)
DATA["prod"] = {"anos": prod.index.tolist(), **{c: prod[c].round(0).tolist() for c in prod.columns},
                "ideam": round(float(resP["P media cuenca (mm/año)"]))}

for k in ["base", "dren", "estP", "sub", "estQ", "etpm"]:   # usados sólo por los mapas interactivos (retirados)
    DATA.pop(k, None)

# ----------------------------------------------------------------------------- textos
Pm, ETPm, ETRm = resB["P (mm/año)"], resB["ETP Hargreaves Σ mensual (mm/año)"], resB["ETR Budyko (mm/año)"]
H = bal.set_index("codigo").loc["HIDRO"]
A_C = morf["Área (km²)"]
S = {}

S["p1"] = ("1. Selección de la cuenca", f"""
<p class="lead">Cuenca del río Cauca hasta la presa de Hidroituango (Antioquia): {fmt(A_C)} km² entre las cordilleras Occidental y Central,
desde el Macizo Colombiano (≈ 3400 m) hasta el cañón del Cauca (≈ 240 m), en siete departamentos.</p>
<h3>Importancia para el sector hidroeléctrico</h3>
<p>Cerca de dos tercios de la electricidad de Colombia es de origen hidráulico, y Hidroituango es la central más grande del país:
2 400 MW de capacidad de diseño, que según EPM pueden cubrir alrededor del 17 % de la demanda nacional. Su generación depende del caudal
que llega a la presa (≈ 1 000 m³/s), es decir, del agua que producen los {fmt(A_C)} km² aguas arriba.</p>
<p>El balance hídrico de largo plazo responde preguntas directas para la operación y la planeación: cuánta agua aporta la cuenca en un año
medio, qué zonas la producen y cuáles la consumen, y qué tan confiables son los datos con que se estima la energía firme. La cuenca tiene
además otros usos que compiten por el agua: el embalse de Salvajina (regulación y generación en el alto Cauca), el abastecimiento de Cali
y el riego de la caña de azúcar en el Valle. Esos usos se notan en el balance de los puntos 8 y 9.</p>
<p>Es también un caso exigente para el método: combina un valle plano y seco a la sombra de lluvia, laderas muy húmedas y páramos, con
gradientes fuertes de lluvia y temperatura en pocas decenas de kilómetros.</p>""")

S["p2"] = ("2. Delimitación", lado(figura("01_delimitacion/mapa_cuenca_cauca_hidroituango.png", "p2_mapa", "Cuenca del río Cauca hasta Hidroituango", "DEM, límite, red de drenaje (Strahler 3–5), río principal, punto de cierre, norte, escala y sistema de coordenadas MAGNA-SIRGAS / Colombia Bogotá (EPSG:3116)."), f"""
<p class="lead">Área {fmt(A_C)} km² · perímetro {fmt(morf['Perímetro (km)'])} km · río principal {fmt(morf['Long. río principal (km)'])} km ·
elevación {fmt(morf['Elevación mínima cuenca (m)'])}–{fmt(morf['Elevación máxima cuenca (m)'])} m (media {fmt(morf['Elevación media cuenca (m)'])} m).</p>
<h3>Metodología</h3>
<p>DEM Copernicus GLO-30 (14 teselas) reproyectado a MAGNA-SIRGAS / Colombia Bogotá (EPSG:3116) y promediado a 90 m. Se rellenaron
depresiones con Priority-Flood + ε, se calcularon direcciones de flujo D8 y área acumulada, y se delimitó la cuenca aguas arriba del
punto de cierre en la presa (7.136° N, 75.663° W). La red de drenaje son las celdas con más de 25 km² acumulados; el río principal se
trazó desde el cierre siguiendo en cada confluencia el tributario de mayor área.</p>
{dec([("GLO-30 y no el mdt900 del curso", "932 m de celda suavizan el relieve y escalonan el límite; GLO-30 es el DEM global más exacto"),
      ("90 m", "a 30 m serían 120 millones de celdas sin cambio apreciable en el límite; 90 m es la grilla común de todos los mapas"),
      ("Priority-Flood + ε", "el relleno estándar de pysheds cortaba el flujo en la planicie del Valle y dejaba la cuenca en 20 000 km²")])}
<h3>Análisis</h3>
<p>Kc = {morf['Coef. compacidad Gravelius Kc']:.2f} y Kf = {morf['Factor de forma Kf = A/L²']:.2f}: cuenca muy alargada, cuyas crecientes de cabecera
tardan días en llegar a la presa y se atenúan.</p>
""") + ancho("s_perfil", "<p><b>Perfil longitudinal del río Cauca.</b> Caída fuerte en la cabecera, tramo casi "
                                       "plano en el Valle (≈ 950 m de altura en 400 km) y descenso continuo en el cañón antioqueño hasta la presa. "
                                       f"Pendiente media {morf['Pendiente media río principal (%)']:.2f} %.</p>") +
           lado(figura("01_delimitacion/verificacion_cierre.png", "p2_cierre", "Verificación del punto de cierre",
                       "Detalle de la presa: DEM sombreado, drenajes, límite de la cuenca, punto de cierre y ubicación publicada de la presa.", 1500), f"""
<h3>Verificación del cierre</h3>
<p>La presa está inmediatamente aguas arriba de la desembocadura del río Ituango y aguas abajo de la del río San Andrés (EPM). La cuenca
delimitada cumple las dos condiciones:</p>
<ul class="dec">
<li><b>Ubicación.</b> El punto de cierre está a {vc['Distancia cierre – presa (m)']:.0f} m de la coordenada publicada de la presa
(7°08′04″ N, 75°39′43″ W), dentro del error de una coordenada con precisión de segundos y de la celda de 90 m.</li>
<li><b>Río Ituango excluido.</b> Entra 0.5 km aguas abajo del cierre con {vc['Río Ituango en el DEM (km²)']:.0f} km²
({vc['Río Ituango en HydroSHEDS (km²)']:.0f} km² en HydroSHEDS; 572 km² según la Alcaldía de Ituango).</li>
<li><b>Río San Andrés incluido.</b> Entra 7 km aguas arriba con {vc['Río San Andrés en el DEM (km²)']:.0f} km².</li>
<li><b>Área.</b> La red HydroSHEDS del curso, independiente del DEM usado, acumula {fmt(vc['Área HydroSHEDS aguas arriba del río Ituango (km²)'])} km²
justo antes de la confluencia del Ituango: {vc['Diferencia con HydroSHEDS (%)']:.1f} % de diferencia con la cuenca delimitada. El DEM de 900 m
del curso dio 35 827 km².</li>
</ul>
<p class="nota">Un documento de monitoreo de EPM menciona ≈ 37 820 km² drenados por el río en el tramo del proyecto, sin precisar el punto
ni el método; las tres delimitaciones independientes coinciden en ≈ 35 800–36 000 km² hasta la presa.</p>"""))

cvt = cvP[["RMSE (mm)", "Sesgo (mm)", "R2"]].rename(columns={"R2": "R²"}).loc[["Kriging ordinario (gaussiano)", "IDW p=1.5", "IDW p=2", "IDW p=3"]]
cvt.index.name = "Método"
S["p3"] = ("3. Precipitación", abajo(figura("03_estaciones_precipitacion/mapa_estaciones_precipitacion.png", "p3_est", "Estaciones IDEAM dentro de la cuenca y en su vecindario", "Coloreadas por precipitación media anual 1981–2010; círculos dentro de la cuenca, triángulos a menos de 20 km.", 1400) + figura("04_precipitacion_interpolada/mapa_precipitacion_media_anual.png", "p3_mapa", "Precipitación media anual multianual (kriging ordinario)", "Isoyetas cada 500 mm y las 266 estaciones usadas en la interpolación.", 1400), cols=2, texto=f"""
<p class="lead">Precipitación media anual 1981–2010 de la cuenca: <b>{fmt(resP['P media cuenca (mm/año)'])} mm/año</b>
({fmt(resP['P mín (mm/año)'])}–{fmt(resP['P máx (mm/año)'])} mm).</p>
<h3>Estaciones</h3>
<p>266 estaciones de los promedios climatológicos IDEAM 1981–2010: 259 dentro de la cuenca y 7 a menos de 20 km en la misma vertiente
(zona hidrográfica 26). Se dejaron fuera las del vecindario en la vertiente del Pacífico y del Magdalena, y Briceño (6455 mm), que está
fuera de la cuenca y ninguna vecina corrobora.</p>
<h3>Interpolación</h3>
<p>Se compararon IDW (potencias 1 a 3) y kriging ordinario con validación cruzada dejando una estación fuera. Se eligió <b>kriging
ordinario</b> con variograma gaussiano: tiene el menor error, no tiene sesgo y entrega la incertidumbre de la estimación. No se usó la
elevación como tendencia porque la lluvia no crece linealmente con la altura (máxima entre 1500 y 2500 m; r = 0.18).</p>
{tabla(cvt, "Validación cruzada", {"RMSE (mm)": ",.0f", "Sesgo (mm)": "+.0f", "R²": ".2f"})}
<h3>Análisis</h3>
<p>El fondo del Valle del Cauca es la zona más seca (1000–1500 mm) por la sombra de lluvia entre las cordilleras; los núcleos húmedos
están en la ladera occidental del alto Cauca (> 3000 mm), el Eje Cafetero y el tramo antioqueño. Hay pocas estaciones sobre 3000 m,
así que la lluvia de los páramos probablemente está subestimada.</p>""") +
           ancho("s_vario", f"<p><b>Variograma.</b> Semivarianza entre pares de estaciones por distancia y modelo gaussiano ajustado: las estaciones "
                            f"dejan de parecerse a partir de ≈ {rg:.0f} km, y la pepita (≈ {100 * c0 / (c0 + cc):.0f} %) refleja la variabilidad local por el relieve.</p>",
                 alto="serie corta"))

ct = coefT[["T0", "alfa_km", "R2", "n"]].rename(columns={"T0": "T0 (°C)", "alfa_km": "α (°C/km)", "R2": "R²", "n": "n"}); ct.index.name = "Variable"
ct["Ecuación"] = [f"{v} = {coefT.loc[v, 'T0']:.2f} − {coefT.loc[v, 'alfa']:.5f}·Z" for v in ct.index]
from scipy.stats import t as t_student  # noqa: E402
for v in ct.index:                                   # IC 95 % de la pendiente: t(0.975, n−2)·s/√Sxx
    z_, y_ = eT.Z.astype(float).to_numpy(), eT[v].astype(float).to_numpy()
    b_, a_ = np.polyfit(z_, y_, 1); s_ = np.sqrt(np.sum((y_ - a_ - b_ * z_) ** 2) / (len(z_) - 2))
    ct.loc[v, "± IC 95 % (°C/km)"] = 1000 * t_student.ppf(0.975, len(z_) - 2) * s_ / np.sqrt(np.sum((z_ - z_.mean()) ** 2))
ct = ct[["Ecuación", "T0 (°C)", "α (°C/km)", "± IC 95 % (°C/km)", "R²", "n"]]
S["p4"] = ("4. Temperatura y elevación", f"""
<p class="lead">Relación T = T0 − α·Z con 47 estaciones IDEAM (1981–2010) dentro de la cuenca, entre 500 y 4150 m.</p>
<div class="tres"><div class="plot cuadro" id="s_tmax"></div><div class="plot cuadro" id="s_tmed"></div><div class="plot cuadro" id="s_tmin"></div></div>
{tabla(ct, "Ecuaciones, gradiente térmico y ajuste", {"T0 (°C)": ".2f", "α (°C/km)": ".2f", "± IC 95 % (°C/km)": ".2f", "R²": ".3f", "n": ".0f"},
       "IC 95 % de α: ± t(0.975, n − 2)·s/√Σ(Z − Z̄)², con s el error típico de la regresión. Los tres gradientes son distintos entre sí con 95 % de confianza.")}
<div class="dos"><div>
{dec([("Mismas 47 estaciones para las tres variables", "sólo las que tienen Tmax, Tmin y Tmed completas; así las ecuaciones son comparables"),
      ("Elevación del catálogo", "es la altura medida en la estación; la coordenada del IDEAM puede caer en otra cota del DEM en ladera"),
      ("Aragón excluida", "su coordenada cae en el cañón pero la estación está en Santa Rosa de Osos, fuera de la cuenca"),
      ("Atípicos conservados", "Brisas Las, San Félix y Cedral El; sin ellos α cambia como máximo 0.23 °C/km")])}
</div><div>
<h3>Interpretación física</h3>
<p>Tmed baja 6.4 °C por km, casi igual al gradiente estándar de la atmósfera (6.5 °C/km): es el enfriamiento del aire húmedo que asciende.
Tmax baja más rápido (7.3 °C/km) que Tmin (5.7 °C/km): de día el sol calienta mucho los fondos de valle y de noche el aire frío drena
hacia ellos. Por eso la amplitud diaria se reduce con la altura, de ≈ 12.6 °C a nivel del mar a ≈ 5.8 °C a 4150 m. La isoterma de 0 °C de
Tmed queda a ≈ 4700 m, en el límite de los glaciares del Ruiz y el Santa Isabel.</p></div></div>""")

S["p5"] = ("5. Mapas de temperatura", abajo(figura("07_mapas_temperatura/mapas_temperatura_panel.png", "p5_panel", "Temperatura mínima, media y máxima media anual", "T = T0 − α·Z aplicada a cada celda del DEM de 90 m; isotermas cada 4 °C; la misma escala de color en los tres mapas.", 2400), f"""
<p class="lead">Media de la cuenca: Tmax <b>{resT.loc['Tmax', 'media cuenca (°C)']:.1f} °C</b>, Tmed <b>{resT.loc['Tmed', 'media cuenca (°C)']:.1f} °C</b>,
Tmin <b>{resT.loc['Tmin', 'media cuenca (°C)']:.1f} °C</b>.</p>
<p>Cada celda del DEM de 90 m recibe T = T0 − α·Z con las ecuaciones del punto 4.</p>
<h3>Análisis</h3>
<p><b>Efecto de la elevación.</b> La temperatura dibuja el relieve. El 64 % de la cuenca está entre 500 y 2000 m (Tmed de 19 a 24 °C).</p>
<p><b>Sectores más fríos.</b> El macizo Ruiz–Santa Isabel–Tolima en el borde oriental (Tmin bajo 0 °C en ≈ 76 km²), los páramos de
Las Hermosas y Barragán y la cabecera en el Puracé.</p>
<p><b>Sectores más cálidos.</b> El cañón del Cauca en Antioquia bajo 600 m (Tmax 32–35 °C) y el fondo del Valle (Tmed ≈ 24 °C).</p>
<p><b>Coherencia.</b> En ninguna celda se viola Tmin &lt; Tmed &lt; Tmax, y Tmed difiere menos de 0.5 °C de (Tmax + Tmin)/2. Sólo el 0.7 % del
área queda fuera del rango de altura de las estaciones. Una sola recta no capta inversiones nocturnas ni el calor extra del cañón seco.</p>"""))

S["p6"] = ("6. Evapotranspiración potencial", lado(figura("08_etp_etr/mapa_ETP_anual_hargreaves.png", "p6_mapa", "Evapotranspiración potencial anual (Hargreaves-Samani)", "Suma de las 12 ETP mensuales; isolíneas cada 200 mm."), f"""
<p class="lead">ETP media de la cuenca por Hargreaves-Samani: <b>{fmt(ETPm)} mm/año</b>.</p>
<h3>Metodología</h3>
<p>Para cada mes y cada celda: Tmax y Tmin de las regresiones mensuales del punto 4, Tmed = (Tmax + Tmin)/2, radiación extraterrestre
Ra con la latitud de la celda y el día juliano representativo (Anexo 3), ETP_d = 0.0023·Ra·(Tmed + 17.8)·√(Tmax − Tmin) y ETP_m = ETP_d·N_d.
La ETP anual es la suma de los 12 meses; coincide con el cálculo anual × 365.</p>
<h3>Análisis</h3>
<p>La ETP sigue a la temperatura: más de 1800 mm en el cañón y el fondo del Valle, menos de 600 mm en los páramos. Es casi constante en el
año (107 a 128 mm por mes) porque cerca del ecuador Ra y la temperatura varían poco. Comparada con la ETP que reporta el IDEAM en
{cETP['n estaciones']:.0f} estaciones de la cuenca, Hargreaves es {cETP['sesgo (%)']:.0f} % mayor, con el mismo patrón espacial (r = {cETP['r']:.2f}):
es un sesgo conocido del método en climas húmedos.</p>""") +
           figura("08_etp_etr/ETP_mensual.png", "p6_mensual", "ETP mensual y radiación extraterrestre, media de la cuenca",
                  "Barras: ETP de cada mes (mm). Línea: Ra (MJ m⁻² día⁻¹) calculada con el día juliano representativo de cada mes (Anexo 3).", 1600))

S["p7"] = ("7. Evapotranspiración real", abajo(figura("08_etp_etr/mapa_indice_aridez_phi.png", "p7_phi", "Índice de aridez φ = ETP/P", "φ < 1: limitado por energía (húmedo); φ > 1: limitado por agua.", 1400) + figura("08_etp_etr/mapa_ETR_anual_budyko.png", "p7_etr", "Evapotranspiración real anual (Budyko)", "Isolíneas cada 200 mm.", 1400), cols=2, texto=f"""
<p class="lead">ETR media de la cuenca por Budyko: <b>{fmt(ETRm)} mm/año</b>, el {100 * ETRm / Pm:.0f} % de la precipitación.
Índice de aridez de la cuenca φ = ETP/P = {ETPm / Pm:.2f}.</p>
<p>φ = ETP/P y ETR = P·[φ·tanh(1/φ)·(1 − e<sup>−φ</sup>)]<sup>½</sup> en cada celda, con P del punto 3 y ETP del punto 6.</p>
<p class="nota">En el enunciado la fórmula aparece con «tanh tanh» por un error de formato; se usó una sola tangente hiperbólica, como
en la ecuación original de Budyko (1974).</p>
{dec([("Celda a celda", "la curva de Budyko no es lineal; aplicarla al φ medio de la cuenca subestima la escorrentía ≈ 4 %"),
      ("Sin parámetro de calibración", "así el punto 9 es una validación independiente y no un ajuste")])}
<h3>Análisis</h3>
<p>La cuenca es húmeda: en el 61 % del área φ &lt; 0.75 y la ETR está limitada por la energía disponible. Sólo el 17 % tiene φ &gt; 1 (limitada
por agua): el fondo del Valle entre Cali y Cartago y parte del cañón. La ETR es mayor en las zonas bajas y húmedas (1200–1450 mm) y menor en
los páramos (&lt; 600 mm), donde falta energía.</p>"""))

qt = val.set_index(val.estacion.map(nom))[["codigo", "municipio", "latitud", "longitud", "area_km2_DEM", "inicio", "fin", "anos", "Q"]].copy()
qt["latitud"] = qt.latitud.astype(float); qt["longitud"] = qt.longitud.astype(float)
qt.columns = ["Código", "Municipio", "Lat (°)", "Lon (°)", "Área (km²)", "Inicio", "Fin", "Años 1981–2010", "Q medio (m³/s)"]
qt.index.name = "Estación"
S["p8"] = ("8. Caudales observados", lado(figura("06_caudales/mapa_estaciones_caudal_validadas.png", "p8_mapa", "Estaciones de caudal validadas y sus áreas de drenaje", "Q = caudal medio anual multianual 1981–2010."), f"""
<p class="lead">Diez estaciones IDEAM sobre el cauce principal del Cauca, de La Balsa ({fmt(qt['Área (km²)'].min())} km²) a Pto. Valdivia
({fmt(qt['Área (km²)'].max())} km²).</p>
<h3>Metodología</h3>
<p>Los Excel del curso no traían el cauce principal, así que se descargó el caudal medio diario del archivo nacional del IDEAM
(HidrologiaNacionalDiaria, 2026). Un mes cuenta si tiene datos en al menos el 80 % de los días y un año si tiene los 12 meses. Se
usaron las estaciones con <b>15 años completos o más en 1981–2010</b>, el mismo periodo de la climatología. El área de drenaje de cada una
se delimitó con el mismo DEM. El caudal medio anual multianual es el promedio de los años completos.</p>
{dec([("Periodo 1981–2010", "el de la precipitación y la temperatura; además es anterior al llenado de Hidroituango (2019)"),
      ("Faltantes sin rellenar", "no hay ceros ni negativos; las medias cambian 2 % o menos según el criterio de faltantes"),
      ("La Pintada antes del río Arma", "entre Irra y La Pintada el caudal sólo sube 26 m³/s, menos de lo que aporta el Arma"),
      ("Pte. Pescadero y Olaya excluidas", "sólo 10 años completos cada una")])}
"""))
S["p8"] = (S["p8"][0], S["p8"][1] + tabla(qt, "Ubicación, área de drenaje, periodo de registro y caudal medio anual multianual (1981–2010)",
                                          {"Lat (°)": ".4f", "Lon (°)": ".4f", "Área (km²)": ",.0f", "Años 1981–2010": ".0f", "Q medio (m³/s)": ",.1f"}) +
           figura("06_caudales/disponibilidad_caudales.png", "p8_disp", "Disponibilidad de datos de las estaciones descargadas",
                  "Meses con al menos 80 % de días con dato. Verde: 15 años completos o más en 1981–2010 (validada); rojo: no cumple.", 1600) +
           ancho("s_Q", "<p><b>Caudal medio mensual.</b> Seleccione una o varias estaciones en la leyenda; arrastre sobre el gráfico o use la barra "
                        "inferior para acercarse a un periodo. La franja marca 1981–2010. El régimen es bimodal, con picos en mayo y noviembre. Los años más "
                        "caudalosos (1999, 2008, 2010–11, 2022) coinciden con La Niña, con el máximo mensual en noviembre de 2010 (3167 m³/s en Pto. Valdivia); "
                        "los más secos (1992, 2015–16) con El Niño.</p>",
                 alto="serie alta"))

bt = bal.set_index(bal.estacion.map(nom).str.replace(" (Cierre)", ""))[["A (km²)", "P (mm/año)", "ETR Budyko celda a celda (mm/año)", "R est (mm)",
                                                                       "Q est", "Q obs (m³/s)", "error %"]]
bt.columns = ["A (km²)", "P (mm)", "ETR (mm)", "P − ETR (mm)", "Q estimado (m³/s)", "Q observado (m³/s)", "Error (%)"]
bt.index.name = "Área de drenaje"
st = sens.set_index("Estación").filter(like="Error")
st.columns = ["P kriging (base)", "P por IDW", "P con todas las estaciones", "ETP escalada al IDEAM"]
st.index = [nom(i) for i in st.index]; st.index.name = "Error (%)"
# Figuras complementarias de los puntos 3 a 8 (se insertan en 13_informe_html.py antes del punto 9).
C15 = RES / "15_complementarias"
_cv = pd.read_csv(RES / "04_precipitacion_interpolada" / "validacion_cruzada_estaciones.csv")
DATA["cv"] = {"n": _cv.nombre.tolist(), "obs": _cv["P observada"].tolist(),
              "kri": _cv["P estimada Kriging ordinario (gaussiano)"].tolist(), "idw": _cv["P estimada IDW p=1.5"].tolist()}
S["p3"] = (S["p3"][0], S["p3"][1] + ancho(
    "s_cv", "<p><b>Precipitación observada frente a estimada en la validación cruzada.</b> Cada punto es una estación: su lluvia se estimó "
            "con las demás y se comparó con la medida. Sobre la línea 1:1 la estimación es exacta. Los puntos más alejados son núcleos "
            "lluviosos aislados (El Tambo, la ladera occidental) que ninguna estación vecina representa. Use los botones para comparar "
            "kriging e IDW.</p>"))

pis = pd.read_csv(C15 / "pisos_termicos.csv")
pist = pis.set_index("piso")[["Tmed (°C)", "elevación (m)", "área (km²)", "% del área"]]; pist.index.name = "Piso térmico"
coh = pd.read_csv(C15 / "coherencia_temperatura.csv")
DATA["coh"] = {"n": coh.estacion.tolist(), "dz": (coh["Z DEM"] - coh["Z catálogo"]).round(0).tolist(),
               **{f"{v}_{k}": coh[f"{v} {k}"].round(2).tolist() for v in ["Tmax", "Tmed", "Tmin"] for k in ["obs", "mapa"]}}
_e = {v: coh[f"{v} mapa"] - coh[f"{v} obs"] for v in ["Tmax", "Tmed", "Tmin"]}
S["p5"] = (S["p5"][0], S["p5"][1] + lado(
    figura("15_complementarias/pisos_termicos.png", "p5_pisos", "Pisos térmicos según la temperatura media",
           "Clasificación de Caldas aplicada a cada celda del mapa de Tmed.", 1400), f"""
<h3>Pisos térmicos</h3>
<p>La Tmed de cada celda se clasificó en los pisos térmicos de Caldas. Los límites de elevación salen de la ecuación de Tmed de esta
cuenca (Z = (T<sub>0</sub> − T)/α), no de valores genéricos.</p>
{tabla(pist, "Pisos térmicos de la cuenca", {"área (km²)": ",.0f", "% del área": ".1f"})}
<p>La mitad de la cuenca es templada (944–1882 m), con el fondo del Valle en el límite templado–cálido. El piso cálido (8.9 %) está en el
cañón antioqueño y el fondo del Valle bajo 944 m; los pisos de páramo y nival (12.7 %) forman la franja alta de la Cordillera Central y el
Macizo.</p>""") + ancho(
    "s_coh", f"<p><b>Coherencia: mapa frente a estaciones.</b> Valor del mapa en la celda de cada una de las 47 estaciones frente a la temperatura "
             f"medida. Sesgo de {_e['Tmax'].mean():+.1f} / {_e['Tmed'].mean():+.1f} / {_e['Tmin'].mean():+.1f} °C y RMSE de "
             f"{np.sqrt((_e['Tmax'] ** 2).mean()):.1f} / {np.sqrt((_e['Tmed'] ** 2).mean()):.1f} / {np.sqrt((_e['Tmin'] ** 2).mean()):.1f} °C "
             "(Tmax / Tmed / Tmin). Los puntos más alejados son estaciones cuya coordenada cae en otra cota del DEM: el cursor muestra la "
             "diferencia entre la elevación del DEM y la del catálogo. Use los botones para cambiar de variable.</p>"))

ra = pd.read_csv(C15 / "Ra_mes_latitud.csv", index_col=0)
et = pd.read_csv(C15 / "ETP_vs_Tmed.csv")
DATA["ra"] = {c: ra[c].round(2).tolist() for c in ra.columns}
DATA["etpT"] = {"T": et.Tmed.tolist(), "ETP": et.ETP.tolist(), "Z": et.Z.tolist()}
S["p6"] = (S["p6"][0], S["p6"][1] + "<div class='dos'><div>" + ancho(
    "s_ra", "<p><b>Radiación extraterrestre equivalente por mes y latitud</b> (Anexo 3, día juliano representativo de cada mes). Entre el sur "
            "y el norte de la cuenca Ra cambia menos de 1 mm/día; los máximos están cerca de los equinoccios. Por eso el ciclo de la ETP es "
            "suave.</p>", alto="serie corta") + "</div><div>" + ancho(
    "s_etpT", "<p><b>ETP anual frente a temperatura media</b> en una muestra de 3 000 celdas, coloreadas por elevación. La relación casi "
              "lineal muestra que la elevación controla la ETP a través de la temperatura.</p>", alto="serie corta") + "</div></div>")

S["p7"] = (S["p7"][0], S["p7"][1] + lado(
    figura("08_etp_etr/curva_budyko.png", "p7_curva", "Celdas de la cuenca en el espacio de Budyko",
           "Muestra de 20 000 celdas sobre la curva de Budyko, con los límites de energía (ETR = ETP) y de agua (ETR = P).", 1300), """
<h3>Espacio de Budyko</h3>
<p>Todas las celdas caen sobre la curva porque la ETR se calculó con ella; la figura muestra en qué régimen está la cuenca. La mayoría está
a la izquierda de φ = 1 (húmeda, limitada por energía); a la derecha quedan las celdas del fondo del Valle, que evaporan la mayor parte de
su lluvia.</p>
<p>La estrella (Budyko celda a celda) queda debajo del círculo (Budyko con el φ medio de la cuenca): promediar φ antes de aplicar la curva
sobreestima la ETR, porque la curva no es lineal. La validación con caudales se hace en el punto 9.</p>"""))

qa = pd.read_csv(C15 / "Q_anual_estaciones.csv", index_col=0)
DATA["qa"] = {"anos": qa.index.tolist(), "q": {nom(c): [None if pd.isna(v) else v for v in qa[c]] for c in qa.columns}}
S["p8"] = (S["p8"][0], S["p8"][1] + ancho(
    "s_qa", "<p><b>Caudal medio de cada año completo</b> (12 meses con al menos 80 % de días). El caudal medio multianual de cada estación "
            "es el promedio de estos años dentro de 1981–2010 (franja gris). Se ven los años húmedos de La Niña (1999, 2008, 2010–2011) y "
            "secos de El Niño (1992, 2015–2016) en todas las estaciones a la vez.</p>"))


S["p9"] = ("9. Balance hídrico", abajo(figura("08_etp_etr/mapas_ETP_phi_ETR_R_panel.png", "p9_panel", "Balance hídrico de largo plazo celda a celda", "ETP (Hargreaves), índice de aridez φ, ETR (Budyko) y escorrentía R = P − ETR.", 2400), f"""
<p class="lead">Con ΔS ≈ 0 en 30 años, R = P − ETR. En la presa: Q estimado <b>{H['Q est']:.0f} m³/s</b> frente a
{H['Q obs rellenado (m³/s)']:.0f}–{H['Q obs (m³/s)']:.0f} m³/s observados.</p>
<p>Para cada estación se promediaron P y ETR en su área de drenaje y se calculó Q<sub>est</sub> = (P − ETR)·A. Q observado en la presa:
Pto. Valdivia transferido por relación de áreas (Pto. Valdivia drena 3.5 % más que la cuenca).</p>
<h3>Resultado</h3>
<p>Las diez áreas de drenaje cierran con error entre −7 % y +7 % (error absoluto medio 4.5 %). Aguas arriba (La Balsa, Juanchito,
La Victoria) el balance sobreestima 5–7 %: el caudal medido no es natural por la evaporación del embalse de Salvajina y las extracciones
para riego y acueductos en el Valle.</p>
<p>La escorrentía (último mapa) se genera en las laderas húmedas (1000–2500 mm/año); el fondo del Valle aporta poco.</p>"""))
S["p9"] = (S["p9"][0], S["p9"][1] + "<div class='dos'><div class='plot cuadro' id='s_bal'></div><div>"
           + tabla(bt, "Balance por área de drenaje (1981–2010)", {"A (km²)": ",.0f", "P (mm)": ",.0f", "ETR (mm)": ",.0f", "P − ETR (mm)": ",.0f",
                                                                     "Q estimado (m³/s)": ",.0f", "Q observado (m³/s)": ",.0f", "Error (%)": "+.1f"})
           + "</div></div>" + tabla(st, "Sensibilidad: error del balance al cambiar una fuente", {c: "+.1f" for c in st.columns}) + f"""
<h3>Fuentes de incertidumbre</h3>
<dl class="inc">
<dt>Precipitación</dt><dd>Pocas estaciones sobre 3000 m: la lluvia de los páramos está probablemente subestimada. Cambiar el método o las
estaciones de P mueve el error 2 puntos como máximo.</dd>
<dt>Evapotranspiración</dt><dd>Hargreaves supera en {cETP['sesgo (%)']:.0f} % la ETP del IDEAM, y Budyko no tiene calibración. Con la ETP del IDEAM el
balance empeora (+9 a +23 %): el exceso de Hargreaves probablemente compensa la lluvia que falta en alta montaña.</dd>
<dt>Caudal</dt><dd>Curvas de calibración (3–5 % de error), 10–22 % de días faltantes en Pto. Valdivia y el Valle, regulación de Salvajina
y extracciones. Por eso los caudales de tramos cortos entre estaciones no son confiables.</dd>
<dt>Interpolación</dt><dd>Error de validación de ≈ 363 mm por estación; en el Valle el cauce del DEM se separa 3–5 km del real (±5 % de área).</dd>
<dt>Periodos</dt><dd>P y T son promedios de estaciones con registros de distinta longitud; cada estación de caudal tiene sus propios años
completos dentro de 1981–2010. El caudal en la presa varía entre 1020 y 1084 m³/s según la fuente.</dd>
</dl>""")

# Bloque de los puntos 10 a 14 del informe (se inserta en 13_informe_html.py). CHIRPS = v2.0 (IRI); v3.0 = sensibilidad.
C15 = RES / "15_complementarias"
cv2 = pd.read_csv(RES / "12_balance_productos" / "chirps_v2" / "comparacion_chirps_v2_v3.csv", index_col=0)
num_cv2 = lambda fila, col: float(cv2.loc[fila, col])
tp = pd.DataFrame({
    "Fuente": ["Climate Hazards Center (UC Santa Barbara): satélite infrarrojo combinado con estaciones; descarga en la IRI Data Library (Columbia University)",
               "ECMWF / Copernicus (C3S): reanálisis de superficie terrestre forzado por ERA5",
               "ECMWF / Copernicus (C3S): reanálisis atmosférico global",
               "Climate Hazards Center (UC Santa Barbara), versión nueva"],
    "Resolución espacial": ["0.05° (≈ 5.5 km)", "0.1° (≈ 11 km)", "0.25° (≈ 28 km)", "0.05° (≈ 5.5 km)"],
    "Resolución temporal": ["diaria, pentadal y mensual (se usa mensual)", "horaria (se usa mensual)", "horaria (se usa mensual)",
                            "diaria y mensual (se usa mensual)"],
    "Periodo disponible": ["1981 – presente", "1950 – presente", "1940 – presente", "1981 – presente"],
    "Archivo usado": [f"Descarga propia (IRI), recorte de la cuenca, {cobP.loc['CHIRPS', 'inicio']} a {cobP.loc['CHIRPS', 'fin']}",
                      f"Drive del curso, {cobP.loc['ERA5-Land', 'inicio']} a {cobP.loc['ERA5-Land', 'fin']}",
                      f"Drive del curso, {cobP.loc['ERA5', 'inicio']} a {cobP.loc['ERA5', 'fin']}", "Drive del curso, 1981-01 a 2025-12"],
    "Celdas en la cuenca": [int(cobP.loc[k, "celdas en la cuenca"]) for k in ["CHIRPS", "ERA5-Land", "ERA5"]] + [1173],
    "Periodo seleccionado": ["1981–2010"] * 4}, index=["CHIRPS v2.0", "ERA5-Land", "ERA5", "CHIRPS v3.0 (sensibilidad)"])
tp.index.name = "Producto"
pm = pd.DataFrame({"1981–2010": prod.loc[1981:2010].mean(), "1991–2020": prod.loc[1991:2020].mean(), "1981–2025": prod.mean()})
pm = pm.rename(index={"CHIRPS": "CHIRPS v2.0"})
pm.loc["IDEAM (kriging, punto 3)"] = [float(resP["P media cuenca (mm/año)"]), np.nan, np.nan]
pm.index.name = "P media de la cuenca (mm/año)"
S["p10"] = ("10. Productos de precipitación", f"""
<p class="lead">Los tres productos tienen precipitación mensual completa sobre la cuenca de enero de 1981 a diciembre de 2025: 540 meses
sin faltantes en ninguna celda. El periodo común más largo posible es 1981 – presente, porque CHIRPS empieza en 1981; no hay datos
de CHIRPS para 1980.</p>
{tabla(tp, "Documentación de los productos", {"Celdas en la cuenca": ".0f"})}
<div class="dos"><div>
{dec([("1981–2010 como periodo de análisis", "es el periodo de la climatología IDEAM (punto 3), de los caudales validados (punto 8) y del "
       "balance (punto 9); así la comparación entre productos no mezcla diferencias de periodo con diferencias de producto"),
      ("CHIRPS v2.0 como producto principal", "es la versión publicada y más citada (Funk et al., 2015) y se descargó de la IRI Data Library "
       "recortada a la cuenca, como pide el enunciado. El Drive del curso trae CHIRPS v3.0, que se evalúa como sensibilidad en el punto 12"),
      ("ERA5 y ERA5-Land del Drive del curso", "cubren 1981–2025 completos; ampliar antes de 1981 no sirve porque CHIRPS no existe antes"),
      ("Promedio areal ponderado", "celdas con centro dentro de la cuenca, ponderadas por cos(latitud) porque el área de una celda en "
       "grados disminuye con la latitud")])}
</div><div>
{tabla(pm, "Precipitación media de la cuenca según el periodo", {c: ",.0f" for c in pm.columns})}
<h3>Primera lectura</h3>
<p>CHIRPS ({fmt(pm.loc['CHIRPS v2.0', '1981–2010'])} mm) queda apenas 2 % sobre la interpolación de estaciones IDEAM; ERA5 y ERA5-Land
(≈ {fmt(round(pm.loc['ERA5', '1981–2010'], -2))} mm) la triplican. ERA5-Land y ERA5 dan casi lo mismo porque la precipitación de ERA5-Land
es la de ERA5 llevada a una grilla más fina. La media cambia menos de 3 % entre periodos, así que la elección del periodo pesa poco
frente a la elección del producto.</p>
</div></div>""" + ancho("s_prod", "<p><b>Precipitación anual promedio de la cuenca, 1981–2025.</b> La línea punteada es la media IDEAM 1981–2010 "
                         "y la franja marca el periodo seleccionado. CHIRPS reproduce los años extremos que muestran los caudales del punto 8 "
                         "(1991–1992 y 2015 secos; 1999, 2008, 2011 y 2022 húmedos). ERA5 y ERA5-Land no: sus años más secos son 2018–2019 "
                         "y los más húmedos 1988 y 1998. La correlación de la lluvia anual entre CHIRPS y los reanálisis es de solo 0.4 a 0.6.</p>"))

r11 = pd.read_csv(RES / "11_mapas_productos" / "resumen_productos.csv", index_col=0)
t11 = r11[["P media cuenca (mm/año)", "mínimo (mm/año)", "máximo (mm/año)", "sesgo vs IDEAM (%)", "correlación espacial con IDEAM"]].copy()
t11.columns = ["P media (mm/año)", "Mínimo (mm/año)", "Máximo (mm/año)", "Diferencia con IDEAM (%)", "Correlación espacial con IDEAM"]
t11 = t11.rename(index={"CHIRPS": "CHIRPS v2.0"}); t11.index.name = "1981–2010"
S["p11"] = ("11. Mapas de precipitación por producto", abajo(
    figura("11_mapas_productos/panel_P_productos.png", "p11_panel", "Precipitación media anual multianual 1981–2010",
           "IDEAM (kriging, punto 3) como referencia y los tres productos en su resolución original, con la misma escala de color.", 2400),
    f"""
<p class="lead">Precipitación media de la cuenca 1981–2010: IDEAM {fmt(r11.loc['IDEAM (kriging)', 'P media cuenca (mm/año)'])} mm, CHIRPS
<b>{fmt(r11.loc['CHIRPS', 'P media cuenca (mm/año)'])} mm</b>, ERA5-Land <b>{fmt(r11.loc['ERA5-Land', 'P media cuenca (mm/año)'])} mm</b> y ERA5
<b>{fmt(r11.loc['ERA5', 'P media cuenca (mm/año)'])} mm</b>.</p>
<h3>Metodología</h3>
<p>Para cada producto se sumaron los 12 meses de cada año y se promediaron los 30 años de 1981–2010 en su grilla original. Luego cada
celda de 90 m de la cuenca tomó el valor de la celda del producto que la contiene (vecino más cercano, sin suavizar).</p>
{dec([("Sin interpolar los productos", "el mapa muestra la resolución real de cada uno (5.5, 11 y 28 km); suavizar daría un detalle que el producto no tiene"),
      ("Misma grilla de 90 m que la ETP", "el punto 12 repite el balance celda a celda cambiando sólo la precipitación"),
      ("Escala de color común por variable", "cada valor tiene el mismo color en todos los mapas de P (naranja → amarillo → verde → azul, como los mapas de Balances 1999): 1000 mm es el mismo tono en IDEAM, CHIRPS y ERA5. Cada barra llega sólo hasta el máximo de su mapa")])}
{tabla(t11, "Comparación con la precipitación de estaciones IDEAM", {"P media (mm/año)": ",.0f", "Mínimo (mm/año)": ",.0f", "Máximo (mm/año)": ",.0f",
                                                                   "Diferencia con IDEAM (%)": "+.0f", "Correlación espacial con IDEAM": ".2f"})}
<h3>Análisis</h3>
<p><b>CHIRPS</b> reproduce el patrón de las estaciones (correlación espacial {r11.loc['CHIRPS', 'correlación espacial con IDEAM']:.2f}) y su
magnitud (+{r11.loc['CHIRPS', 'sesgo vs IDEAM (%)']:.0f} %): fondo del Valle seco, ladera occidental del alto Cauca y Eje Cafetero húmedos. Con
5.5 km capta el contraste entre valle y laderas. Hay que tener en cuenta que CHIRPS incorpora estaciones, muchas del IDEAM.</p>
<p><b>ERA5 y ERA5-Land</b> triplican la lluvia y no tienen relación espacial con las estaciones (correlación −0.06). Sus máximos, de más
de 8000 mm/año, caen sobre el fondo del Valle del Cauca y el Eje Cafetero, justo donde las estaciones miden 1000 a 2000 mm. Es un sesgo
conocido de los reanálisis en montaña tropical, donde la convección se parametriza y la orografía se suaviza a 28 km. ERA5-Land no lo
corrige porque su precipitación es la de ERA5 llevada a una grilla más fina.</p>""") +
    figura("11_mapas_productos/panel_razon_IDEAM.png", "p11_razon", "Razón entre cada producto y la precipitación IDEAM",
           "Azul: el producto subestima; rojo: sobreestima. Los reanálisis llegan a 5 veces la lluvia de las estaciones en el Valle del Cauca.", 2000) +
    lado(figura("15_complementarias/verificacion_productos_colombia.png", "p11_verif", "Verificación de lectura en toda Colombia",
                "Precipitación anual 1981–2010 de cada archivo en el dominio completo, con la cuenca en rojo y lugares de referencia.", 2200), """
<h3>Verificación de los archivos</h3>
<p>Antes de interpretar el sesgo de los reanálisis se comprobó que los archivos se leyeron en la posición correcta. En los tres el máximo
nacional está en la costa Pacífica y coinciden en Quibdó (≈ 8 100–8 800 mm/año), La Guajira es seca (Riohacha 700–1 250 mm) y al invertir la
latitud la correlación con CHIRPS cae de 0.53 a 0.20.</p>
<p>Las diferencias aparecen en los Andes: ERA5 y ERA5-Land dan a Manizales 10 000–15 000 mm/año (CHIRPS ≈ 2 400) y a Cali ≈ 3 500 mm (CHIRPS
≈ 1 450), y en cambio subestiman el piedemonte llanero (Villavicencio ≈ 1 500–1 750 frente a ≈ 4 500). Es decir, desplazan la lluvia del
Pacífico tierra adentro sobre la Cordillera Occidental y el valle del Cauca.</p>
<p class="nota">El panel usa CHIRPS v3.0 del Drive del curso porque cubre toda Colombia; CHIRPS v2.0 se descargó sólo para la cuenca.</p>"""))

bp = pd.read_csv(RES / "12_balance_productos" / "balance_productos.csv", dtype={"codigo": str})
dp = pd.read_csv(RES / "12_balance_productos" / "desempeno_productos.csv", index_col=0)
bud = pd.read_csv(C15 / "budyko_estaciones_productos.csv", dtype={"codigo": str})
PRODS = ["IDEAM", "CHIRPS", "ERA5-Land", "ERA5"]
est12 = bp[bp.codigo != "HIDRO"]
orden12 = list(dict.fromkeys(est12.estacion))
DATA["p12"] = {"est": [nom(e) for e in orden12] + ["Hidroituango"],
               **{p: [round(float(bp[(bp.producto == p) & (bp.estacion == e)].Qest.iloc[0] / bp[(bp.producto == p) & (bp.estacion == e)].Qobs.iloc[0]), 3)
                      for e in orden12 + ["HIDROITUANGO (cierre)"]] for p in PRODS}}
hid = bp[bp.codigo == "HIDRO"].set_index("producto").loc[PRODS]
_b2 = pd.read_csv(RES / "12_balance_productos" / "chirps_v2" / "balance_chirps_v2_v3.csv", dtype={"codigo": str})
_h3 = _b2[(_b2.codigo == "HIDRO") & (_b2.producto == "CHIRPS v3.0")].iloc[0]
R_obs_c = float(hid.Qobs.iloc[0] * SEG / (hid.A.iloc[0] * 1e6) * 1000)
DATA["p12bar"] = {"prod": ["IDEAM", "CHIRPS", "ERA5-Land", "ERA5"], "P": hid.P.round(0).tolist(), "ETR": hid.ETR.round(0).tolist(),
                  "R": hid.R.round(0).tolist(), "Robs": round(R_obs_c)}
bh = bud[bud.codigo != "HIDRO"]
DATA["p12bud"] = {p: {"est": [nom(e) for e in bh[bh.producto == p].estacion], "phi": bh[bh.producto == p].phi.round(3).tolist(),
                      "obs": bh[bh.producto == p]["ETRobs/P"].round(3).tolist(),
                      "k": bh[bh.producto == p]["corrección de P necesaria (%)"].round(1).tolist()} for p in PRODS}
t12 = pd.DataFrame({"P anual (mm/año)": hid.P, "ETR (mm/año)": hid.ETR, "Q estimado (mm/año)": hid.R,
                    "Q observado (mm/año)": hid.Qobs * SEG / (hid.A * 1e6) * 1000, "Error (%)": hid.err, "Q estimado (m³/s)": hid.Qest})
t12.index = ["IDEAM (estaciones)", "CHIRPS v2.0", "ERA5-Land", "ERA5"]; t12.index.name = "Producto"
t12.loc["CHIRPS v3.0 (sensibilidad)"] = [_h3.P, _h3.ETR, _h3.R, t12.iloc[0]["Q observado (mm/año)"], _h3.err, _h3.Qest]
e12 = bp.pivot(index="estacion", columns="producto", values="err").loc[orden12 + ["HIDROITUANGO (cierre)"], PRODS]
e12 = e12.rename(columns={"CHIRPS": "CHIRPS v2.0"})
e12.index = [nom(i).replace(" (Cierre)", "") for i in e12.index]; e12.index.name = "Error del caudal (%)"
kk = bud.groupby("producto")["corrección de P necesaria (%)"].agg(["min", "max"])
posibles = bud[bud.codigo != "HIDRO"].groupby("producto")["balance posible"].sum()
d12 = dp.loc[PRODS, ["sesgo", "MAE", "r"]].rename(columns={"sesgo": "Sesgo medio (%)", "MAE": "Error absoluto medio (%)", "r": "Correlación Q est–Q obs"})
d12["Corrección de P necesaria (%)"] = [f"{kk.loc[p, 'min']:+.0f} a {kk.loc[p, 'max']:+.0f}" for p in PRODS]
d12["Estaciones con balance posible"] = [f"{int(posibles[p])} de 9" for p in PRODS]
d12 = d12.rename(index={"CHIRPS": "CHIRPS v2.0"}); d12.index.name = "9 estaciones"


def _num(x):
    try:
        return float(x)
    except ValueError:
        return x


cvt2 = pd.DataFrame({c: [_num(x) for x in cv2[c]] for c in cv2.columns}, index=cv2.index, dtype=object)
cvt2 = cvt2[["CHIRPS v2.0", "CHIRPS v3.0"]]; cvt2.index.name = "CHIRPS v2.0 (principal) frente a v3.0 (Drive del curso)"
S["p12"] = ("12. Balance con cada producto", f"""
<p class="lead">El balance del punto 9 repetido cambiando sólo la precipitación. En la presa de Hidroituango CHIRPS reproduce el caudal
con {t12.loc['CHIRPS v2.0', 'Error (%)']:+.1f} %, prácticamente igual que las estaciones IDEAM ({t12.loc['IDEAM (estaciones)', 'Error (%)']:+.1f} %);
ERA5 y ERA5-Land lo multiplican por cinco.</p>
{tabla(t12, "Balance de largo plazo de la cuenca hasta Hidroituango con cada producto (1981–2010)",
       {"P anual (mm/año)": ",.0f", "ETR (mm/año)": ",.0f", "Q estimado (mm/año)": ",.0f", "Q observado (mm/año)": ",.0f",
        "Error (%)": "+.1f", "Q estimado (m³/s)": ",.0f"},
       "Q estimado = P − ETR (Budyko celda a celda con la ETP de Hargreaves). Q observado: Pto. Valdivia transferido por áreas, "
       "1084 m³/s (950 mm/año); con Pte. Pescadero rellenada sería 1020 m³/s (894 mm/año).")}""" +
    ancho("s_p12bar", "<p><b>P, ETR y escorrentía en el cierre con cada producto.</b> La línea punteada es la escorrentía observada "
                      "(950 mm/año). Escala logarítmica, porque los reanálisis llegan a casi 6 000 mm.</p>", alto="serie corta") + f"""
<div class="dos"><div>
<h3>Metodología</h3>
<p>Para cada producto se usó su precipitación media 1981–2010 en la grilla de 90 m (punto 11) y, con la misma ETP de Hargreaves, se
calcularon φ = ETP/P y la ETR de Budyko celda a celda. Se promediaron P y ETR en cada una de las diez áreas de drenaje y se comparó
Q<sub>est</sub> = (P − ETR)·A con el caudal observado.</p>
<p>Más allá de comparar la lluvia, cada producto se evaluó contra el caudal medido con dos indicadores: la <b>corrección de P
necesaria</b> (el factor que habría que aplicar a la lluvia del producto, celda a celda, para que el balance dé exactamente el caudal
observado) y el <b>balance posible</b> (la ETR implícita en lo observado, P − Q<sub>obs</sub>, debe quedar entre 0 y la ETP).</p>
{dec([("Sólo cambia la precipitación", "ETP, método, áreas, periodo y caudales son los del punto 9: las diferencias se deben sólo al producto"),
      ("Evaluar en las diez áreas de drenaje", "un producto puede acertar en el cierre por compensación de errores; las estaciones intermedias "
       "muestran si el acierto es consistente a lo largo del río")])}
{tabla(d12, "Desempeño en las estaciones", {"Sesgo medio (%)": "+.0f", "Error absoluto medio (%)": ",.0f", "Correlación Q est–Q obs": ".3f"})}
</div><div>
<h3>Análisis</h3>
<p><b>IDEAM</b> cierra el balance con error de −7 a +7 %; es la referencia, porque es la información de la que se derivó el resto del balance.</p>
<p><b>CHIRPS</b> cierra el balance casi tan bien como las estaciones: error de −4 a +10 % en las estaciones y {t12.loc['CHIRPS v2.0', 'Error (%)']:+.1f} %
en el cierre. Su lluvia necesitaría una corrección de apenas {kk.loc['CHIRPS', 'min']:+.0f} a {kk.loc['CHIRPS', 'max']:+.0f} % para reproducir
exactamente los caudales, y el balance es posible en las 9 estaciones.</p>
<p><b>ERA5 y ERA5-Land</b> estiman entre 2.6 y 6.8 veces el caudal observado: habría que quitarles entre 47 y 74 % de la lluvia para cerrar el
balance, y en ninguna estación la ETR implícita queda por debajo de la ETP (balance imposible). El error es mayor en el Valle y el Eje
Cafetero, donde el punto 11 mostró el desplazamiento de la lluvia del Pacífico.</p>
<p>Un error de la lluvia se amplifica en el caudal: la ETR casi no cambia (está limitada por la energía), así que todo el exceso de
lluvia se vuelve escorrentía. Por eso CHIRPS v3.0, con 11 % más lluvia que v2.0, sobreestima el caudal 15 a 32 %.</p>
<p>Conclusión: para el balance hídrico de esta cuenca CHIRPS representa mejor las condiciones observadas; los reanálisis sólo servirían con
una corrección de sesgo basada en estaciones.</p>
</div></div>
{tabla(e12, "Error del caudal estimado por área de drenaje y producto", {p: "+.1f" for p in e12.columns})}""" +
    ancho("s_p12", "<p><b>Q estimado / Q observado por área de drenaje</b> (escala logarítmica). 1 = balance perfecto; la franja marca ±10 %. "
                   "Haga clic en la leyenda para mostrar u ocultar productos.</p>") +
    ancho("s_bud", "<p><b>Áreas de drenaje en el espacio de Budyko con la ETR «observada» = P − Q<sub>obs</sub>.</b> Sobre la curva, la lluvia "
                   "del producto es coherente con el caudal; por encima del límite de energía (línea punteada) el balance no puede cerrar. "
                   "El cursor muestra la corrección de P necesaria.</p>") +
    figura("15_complementarias/R_por_producto.png", "p12_R", "Escorrentía de largo plazo R = P − ETR con cada producto",
           "Misma ETP de Hargreaves para todos; las diferencias vienen sólo de la precipitación. Compárese con los rendimientos observados del punto 8.", 2200) + f"""
<h3>Sensibilidad a la versión de CHIRPS</h3>
<div class="dos"><div>
<p>El Drive del curso trae <b>CHIRPS v3.0</b>. Con esa versión la lluvia de la cuenca queda {num_cv2('Diferencia con IDEAM (%)', 'CHIRPS v3.0'):+.0f} %
sobre el IDEAM y el caudal se sobreestima {cv2.loc['Rango de error estaciones (%)', 'CHIRPS v3.0']} % en las estaciones
({num_cv2('Error en el cierre (%)', 'CHIRPS v3.0'):+.0f} % en el cierre). Las dos versiones tienen el mismo patrón espacial (correlación 0.89 con el IDEAM) y
el mismo ciclo anual (r = 0.998); la diferencia es de magnitud.</p>
<p>La conclusión del punto no cambia con la versión: CHIRPS es el producto que mejor representa la cuenca. Se eligió v2.0 como principal por
ser la versión publicada y porque cierra el balance con los caudales observados.</p>
</div><div>
{tabla(cvt2.loc[["P media cuenca (mm/año)", "Diferencia con IDEAM (%)", "Correlación espacial con IDEAM", "ETR cuenca (mm/año)",
                 "Q estimado cierre (mm/año)", "Error en el cierre (%)", "Error abs. medio estaciones (%)", "Rango de error estaciones (%)",
                 "Ciclo: sesgo (mm/mes)", "Ciclo: RMSE (mm/mes)", "Ciclo: r"]], "CHIRPS v2.0 (principal) frente a v3.0 (Drive del curso), 1981–2010",
       {"CHIRPS v3.0": ",.2f", "CHIRPS v2.0": ",.2f"})}
</div></div>
{figura("12_balance_productos/chirps_v2/panel_chirps_v2_v3.png", "p12_chirps_v2", "CHIRPS v3.0 frente a v2.0",
        "Precipitación media anual 1981–2010 de cada versión en su resolución original y diferencia relativa entre ellas.", 2200)}""")

ci = pd.read_csv(RES / "13_climatologia" / "ciclo_anual.csv", index_col=0)
cr = pd.read_csv(RES / "13_climatologia" / "ciclo_regiones.csv", index_col=0)
er = pd.read_csv(C15 / "estacionalidad_resumen.csv", index_col=0).iloc[:, 0]
MES3 = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
_pm = ci["P media cuenca (mm)"]
HUM = [MES3[i] for i in range(12) if _pm.iloc[i] > _pm.mean()]
SEC = [MES3[i] for i in range(12) if _pm.iloc[i] <= _pm.mean()]
DATA["p13"] = {"humedo": [bool(v > _pm.mean()) for v in _pm], "media": round(float(_pm.mean()), 1),
               "cuenca": ci["P media cuenca (mm)"].round(1).tolist(),
               "reg": {n: cr[n].iloc[:12].round(1).tolist() for n in cr.columns}}
t13 = pd.DataFrame({"Cuenca (mm)": ci["P media cuenca (mm)"].to_numpy(), "% del año": ci["% del total anual"].to_numpy(),
                    **{n.split(" (")[0] + " (mm)": cr[n].iloc[:12].to_numpy() for n in cr.columns}}, index=MES3).T
t13.index.name = "1981–2010"
S["p13"] = ("13. Climatología de la precipitación", abajo(
    figura("13_climatologia/panel_P_mensual.png", "p13_panel", "Precipitación media mensual multianual 1981–2010",
           "Kriging ordinario mes a mes con las 266 estaciones IDEAM del punto 3; misma escala de clases en los doce mapas; "
           "en el título de cada mapa, la media de la cuenca (P̄m).", 2400),
    f"""
<p class="lead">Régimen <b>bimodal</b>: dos temporadas de lluvia, marzo–mayo (máximo en abril, {ci['P media cuenca (mm)'].iloc[3]:.0f} mm) y
septiembre–noviembre (máximo en octubre, {ci['P media cuenca (mm)'].iloc[9]:.0f} mm, el mes más lluvioso), separadas por dos temporadas secas,
diciembre–febrero ({ci['P media cuenca (mm)'].iloc[1]:.0f} mm en febrero) y junio–agosto ({ci['P media cuenca (mm)'].iloc[7]:.0f} mm en agosto, el mes
más seco).</p>
<p><b>Meses húmedos</b> (sobre la media mensual de {_pm.mean():.0f} mm): {", ".join(HUM)}. <b>Meses secos</b>: {", ".join(SEC)}.
Septiembre ({_pm.iloc[8]:.0f} mm) queda en el límite: es la transición hacia la segunda temporada de lluvias.</p>
<h3>Metodología</h3>
<p>Para cada mes se interpoló la precipitación media mensual 1981–2010 de las 266 estaciones por kriging ordinario, con un variograma
gaussiano ajustado a ese mes. P̄<sub>m</sub> de la cuenca es el promedio del mapa del mes. Los doce meses suman {ci['P media cuenca (mm)'].sum():.0f} mm,
0.7 % más que el mapa anual del punto 3 ({fmt(resP['P media cuenca (mm/año)'])} mm).</p>
{dec([("Interpolar cada mes por separado", "el patrón espacial cambia en el año: en julio y agosto el rango del variograma sube a 150–165 km "
       "(lluvia más homogénea) y en los meses húmedos baja a 50–60 km (lluvia convectiva, más local)"),
      ("Regiones por áreas de drenaje", "alto Cauca (hasta La Balsa), Valle del Cauca (La Balsa → La Virginia) y Cauca medio "
       "(La Virginia → Hidroituango), para describir la variación espacial del ciclo con unidades hidrológicas")])}
<h3>Variaciones espaciales del ciclo</h3>
<p><b>Valle del Cauca:</b> el bimodal más marcado y el más seco; julio y agosto bajan a ≈ 70 mm, cerca de un tercio de abril u octubre.</p>
<p><b>Alto Cauca:</b> la segunda temporada domina (noviembre ≈ 300 mm) y diciembre–enero siguen húmedos (200–240 mm); la única temporada
seca marcada es junio–agosto.</p>
<p><b>Cauca medio (Antioquia):</b> más húmedo a mitad de año (julio–agosto ≈ 160 mm, sin un verano marcado); su época seca es
enero–febrero (100–110 mm), y su primer máximo se corre a mayo.</p>
<p>El ciclo responde al paso de la Zona de Convergencia Intertropical, que cruza la cuenca dos veces al año: hacia el norte en
marzo–mayo y hacia el sur en septiembre–noviembre. Por eso el sur (alto Cauca) recibe más lluvia a fin de año y el norte (Antioquia) a
mitad de año. Los caudales del punto 8 reproducen este régimen bimodal.</p>""") +
    ancho("s_p13", "<p><b>Ciclo anual de la precipitación.</b> Barras: media de la cuenca (P̄m), en azul los meses húmedos (sobre la media "
                   "mensual, línea punteada) y en gris los secos; líneas: media de cada región. "
                   "Haga clic en la leyenda para mostrar u ocultar regiones.</p>") +
    tabla(t13, "Precipitación media mensual 1981–2010 (mm)", {c: ",.0f" for c in t13.columns}) +
    lado(figura("15_complementarias/estacionalidad.png", "p13_estac", "Mes de máxima lluvia, número de temporadas lluviosas e índice de estacionalidad",
                "Calculados en cada celda (≈ 900 m) a partir de los 12 mapas mensuales.", 2200), f"""
<h3>Dónde cambia el régimen</h3>
<p><b>Número de temporadas.</b> El {er['% área bimodal']:.0f} % de la cuenca tiene dos temporadas lluviosas (máximos del ciclo que superan en
10 % la media mensual); no hay zonas unimodales. El norte no llega a ser unimodal, pero allí la temporada seca de mitad de año casi
desaparece.</p>
<p><b>Mes de máximo.</b> Octubre o noviembre en el {er['% área con máximo en Oct'] + er['% área con máximo en Nov']:.0f} % del área (todo el sur y la
ladera oriental) y abril o mayo en el {er['% área con máximo en Abr'] + er['% área con máximo en May']:.0f} % (fondo del Valle y Antioquia), según qué
paso de la ZCIT deja más lluvia.</p>
<p><b>Índice de estacionalidad</b> de Walsh y Lawler (1981): SI = (1/R)·Σ|P<sub>m</sub> − R/12|. Va de {er['SI mínimo']:.2f} a {er['SI máximo']:.2f}
(media {er['SI medio']:.2f}): lluvia repartida en el año con estaciones secas moderadas. Es mayor en el fondo del Valle y en el cañón
antioqueño, donde los veranos son más marcados, y menor en las laderas altas.</p>"""))

cp = pd.read_csv(RES / "14_ciclo_productos" / "ciclos_productos.csv", index_col=[0, 1])
mc = pd.read_csv(RES / "14_ciclo_productos" / "metricas_ciclo.csv", index_col=0)
mrg = pd.read_csv(RES / "14_ciclo_productos" / "metricas_regiones.csv", index_col=[0, 1])
ppm = pd.read_csv(C15 / "punto_a_pixel_metricas.csv", index_col=0)
pp = pd.read_csv(C15 / "punto_a_pixel.csv")
PR4 = ["IDEAM", "CHIRPS", "ERA5-Land", "ERA5"]
cu = cp.loc["Cuenca"].loc[MES3, PR4]
DATA["p14"] = {p: cu[p].round(1).tolist() for p in PR4}
DATA["p14"]["taylor"] = {p: [round(float(mc.loc[p, "r"]), 4), round(float(mc.loc[p, "σ normalizada"]), 4)] for p in PR4[1:]}
DATA["pp"] = {"est": pp.estacion.tolist(), "obs": pp["P medida"].tolist(),
              **{k: pp[k].round(0).tolist() for k in ["IDEAM (kriging sin la estación)", "CHIRPS", "ERA5-Land", "ERA5"]},
              "met": {k: [round(float(ppm.loc[k, "RMSE (mm/año)"])), round(float(ppm.loc[k, "r"]), 2)] for k in ppm.index}}


def picos(y):
    y = np.asarray(y)
    i1 = 1 + int(np.argmax(y[1:7])); i2 = 7 + int(np.argmax(y[7:12]))
    seco1 = [11, 0, 1, 2][int(np.argmin(y[[11, 0, 1, 2]]))]; seco2 = 5 + int(np.argmin(y[5:9]))
    return f"{MES3[i1]} y {MES3[i2]}", f"{MES3[seco1]} y {MES3[seco2]}"


t14 = pd.DataFrame({p: {"Total anual (mm)": cu[p].sum(), "Sesgo (mm/mes)": mc.loc[p, "Sesgo (mm/mes)"], "Sesgo (%)": mc.loc[p, "Sesgo (%)"],
                        "RMSE (mm/mes)": mc.loc[p, "RMSE (mm/mes)"], "Correlación r": mc.loc[p, "r"],
                        "σ normalizada (Taylor)": mc.loc[p, "σ normalizada"],
                        "Máximos": picos(cu[p])[0], "Mínimos": picos(cu[p])[1],
                        "Mes más lluvioso": MES3[int(np.argmax(cu[p]))], "Mes más seco": MES3[int(np.argmin(cu[p]))],
                        "Amplitud máx − mín (mm)": cu[p].max() - cu[p].min(),
                        "Amplitud / media": (cu[p].max() - cu[p].min()) / cu[p].mean()} for p in PR4}).T
t14.loc["IDEAM", ["Sesgo (mm/mes)", "Sesgo (%)", "RMSE (mm/mes)", "Correlación r", "σ normalizada (Taylor)"]] = np.nan
for c in ["Total anual (mm)", "Sesgo (mm/mes)", "Sesgo (%)", "RMSE (mm/mes)", "Correlación r", "σ normalizada (Taylor)",
          "Amplitud máx − mín (mm)", "Amplitud / media"]:
    t14[c] = t14[c].astype(float)
t14 = t14.rename(index={"CHIRPS": "CHIRPS v2.0"}); t14.index.name = "Ciclo anual 1981–2010"
t14r = mrg["r"].unstack(1)[["CHIRPS", "ERA5-Land", "ERA5"]].loc[["Cuenca", "Alto Cauca", "Valle del Cauca", "Cauca medio"]]
t14r = t14r.rename(columns={"CHIRPS": "CHIRPS v2.0"}); t14r.index.name = "Correlación r del ciclo"
tpp = ppm[["sesgo (mm/año)", "RMSE (mm/año)", "r"]].rename(index={"CHIRPS": "CHIRPS v2.0"}); tpp.index.name = f"Punto a píxel ({int(ppm.n.iloc[0])} estaciones)"
S["p14"] = ("14. Ciclo anual entre productos", f"""
<p class="lead">CHIRPS reproduce el ciclo anual del IDEAM (r = {mc.loc['CHIRPS', 'r']:.3f}) con un sesgo de apenas
{mc.loc['CHIRPS', 'Sesgo (mm/mes)']:+.1f} mm/mes ({mc.loc['CHIRPS', 'Sesgo (%)']:+.1f} %). ERA5-Land (r = {mc.loc['ERA5-Land', 'r']:.2f}) y ERA5
(r = {mc.loc['ERA5', 'r']:.2f}) triplican la lluvia de todos los meses, corren el máximo a mayo y casi borran la temporada seca de mitad de año.</p>""" +
    ancho("s_p14", "<p><b>Ciclo anual de la cuenca por producto</b> (media mensual 1981–2010 promediada sobre la cuenca). Use los botones "
                   "para ver la magnitud o el ciclo normalizado (% del total anual), que compara sólo la estacionalidad.</p>",
          extra="") + f"""
{tabla(t14, "Indicadores del ciclo anual (n = 12 meses, referencia IDEAM)",
       {"Total anual (mm)": ",.0f", "Sesgo (mm/mes)": "+,.1f", "Sesgo (%)": "+.1f", "RMSE (mm/mes)": ",.1f", "Correlación r": ".3f",
        "σ normalizada (Taylor)": ".2f", "Amplitud máx − mín (mm)": ",.0f", "Amplitud / media": ".2f"},
       "Bias = (1/n) Σ (P producto − P IDEAM); RMSE = √[(1/n) Σ (P producto − P IDEAM)²]; r de Pearson; n = 12. Máximos: mes más lluvioso de "
       "cada temporada (feb–jul y ago–dic); mínimos: mes más seco de dic–mar y de jun–sep.")}
<div class="dos"><div class="plot cuadro" id="s_taylor" style="height:26rem"></div><div>
<h3>Diagrama de Taylor</h3>
<p>Resume en un punto la correlación (ángulo), la variabilidad relativa (distancia al origen, σ producto / σ IDEAM) y el RMSE centrado
(distancia a la estrella del IDEAM). CHIRPS queda prácticamente sobre la referencia (r = {mc.loc['CHIRPS', 'r']:.3f}, σ = {mc.loc['CHIRPS', 'σ normalizada']:.2f}).
ERA5 y ERA5-Land quedan lejos: correlación de 0.6–0.7 y 60 % más variabilidad absoluta, aunque en términos relativos su ciclo es más plano
(amplitud/media 0.46 frente a 0.76). El diagrama no muestra el sesgo, que se lee en la tabla.</p>
{tabla(t14r, "Correlación del ciclo por región", {c: ".2f" for c in t14r.columns})}
</div></div>""" +
    ancho("s_pp", "<p><b>Producto frente a estación (punto a píxel).</b> Precipitación media anual de cada producto en la celda de cada una de "
                  "las estaciones de la cuenca, frente a la medida. Para el IDEAM se usa el valor estimado sin esa estación (validación cruzada), "
                  "para que la comparación sea justa. Use los botones para cambiar de producto.</p>") + f"""
<div class="dos"><div>
{tabla(tpp, "Comparación punto a píxel 1981–2010", {"sesgo (mm/año)": "+,.0f", "RMSE (mm/año)": ",.0f", "r": ".2f"},
       "Parte del error es de escala: un píxel de 28 km (ERA5) no puede reproducir un valor puntual.")}
<h3>Magnitud y estacionalidad</h3>
<p><b>Magnitud.</b> CHIRPS difiere del IDEAM en menos de 10 mm en todos los meses (sesgo {mc.loc['CHIRPS', 'Sesgo (%)']:+.1f} %); ERA5 y ERA5-Land lo
superan por 240 a 400 mm (sesgo +199 %).</p>
<p><b>Estacionalidad, máximos y mínimos.</b> CHIRPS conserva los dos máximos en los mismos meses que el IDEAM (abril y octubre); sus
mínimos caen en enero y julio, meses que en el IDEAM difieren en apenas 1 mm de febrero y agosto. Los reanálisis ponen el máximo en mayo y el
mínimo en enero; su temporada seca de mitad de año es apenas una leve disminución (julio ≈ 500 mm, frente a ≈ 590 mm en mayo).</p>
<p><b>Amplitud.</b> CHIRPS mantiene la amplitud relativa del IDEAM ({t14.loc['CHIRPS v2.0', 'Amplitud / media']:.2f} frente a
{t14.loc['IDEAM', 'Amplitud / media']:.2f}); los reanálisis la reducen a 0.46: su ciclo es más plano porque llueve mucho todo el año.</p>
<p><b>Variación espacial.</b> CHIRPS mantiene r ≈ 1.00 en las tres regiones, con sesgos de −2 a +3 %. Los reanálisis fallan sobre todo en el
Valle del Cauca (r ≈ 0.5, sesgo ≈ +300 %), donde su lluvia del Pacífico desplazada tapa el verano de mitad de año.</p>
</div><div>
<h3>¿Qué producto representa mejor la cuenca?</h3>
<dl class="inc">
<dt>Media de largo plazo</dt><dd>CHIRPS: {fmt(r11.loc['CHIRPS', 'P media cuenca (mm/año)'])} mm frente a {fmt(r11.loc['IDEAM (kriging)', 'P media cuenca (mm/año)'])} mm
del IDEAM ({r11.loc['CHIRPS', 'sesgo vs IDEAM (%)']:+.0f} %). ERA5 y ERA5-Land la triplican.</dd>
<dt>Balance hídrico</dt><dd>CHIRPS: caudal {t12.loc['CHIRPS v2.0', 'Error (%)']:+.0f} % en el cierre y −4 a +10 % en las estaciones, casi como el
IDEAM. Con los reanálisis el caudal estimado es 3 a 7 veces el observado.</dd>
<dt>Ciclo anual</dt><dd>CHIRPS: r = {mc.loc['CHIRPS', 'r']:.3f}, sesgo {mc.loc['CHIRPS', 'Sesgo (%)']:+.1f} %, mismos máximos y misma amplitud relativa.</dd>
<dt>Distribución espacial</dt><dd>CHIRPS: correlación espacial {r11.loc['CHIRPS', 'correlación espacial con IDEAM']:.2f} con el mapa IDEAM y, punto a
píxel, el mismo error que la interpolación de estaciones (RMSE ≈ 370 mm, r = 0.79). Los reanálisis −0.06 y r ≈ 0.06: su patrón no se
parece al observado.</dd>
</dl>
<p><b>CHIRPS es el producto que mejor representa las condiciones hidroclimáticas de la cuenca en los cuatro aspectos</b>, con un desempeño
casi igual al de la propia interpolación de estaciones. Hay que matizarlo: CHIRPS incorpora estaciones, muchas del IDEAM, así que no es
del todo independiente de la referencia. ERA5 y ERA5-Land tienen la ventaja de series largas (desde 1940 y 1950) y datos horarios, pero en
esta cuenca sólo serían útiles con una corrección de sesgo basada en estaciones.</p>
</div></div>""")


S["ref"] = ("Referencias", """
<ul class="refs">
<li>Barnes, R., Lehman, C. y Mulla, D. (2014). Priority-flood: An optimal depression-filling and watershed-labeling algorithm for digital
elevation models. <i>Computers &amp; Geosciences</i>, 62, 117–127.</li>
<li>Budyko, M. I. (1974). <i>Climate and Life</i>. Academic Press, Nueva York.</li>
<li>Cressie, N. (1985). Fitting variogram models by weighted least squares. <i>Mathematical Geology</i>, 17(5), 563–586.</li>
<li>Duan, N. (1983). Smearing estimate: A nonparametric retransformation method. <i>Journal of the American Statistical Association</i>, 78(383), 605–610.</li>
<li>European Space Agency (2021). <i>Copernicus Global Digital Elevation Model (GLO-30)</i>. Distribuido por OpenTopography / AWS Open Data.</li>
<li>Funk, C. et al. (2015). The climate hazards infrared precipitation with stations — a new environmental record for monitoring extremes.
<i>Scientific Data</i>, 2, 150066. (CHIRPS v2.0; v3.0: Climate Hazards Center, UC Santa Barbara.)</li>
<li>Hargreaves, G. H. y Samani, Z. A. (1985). Reference crop evapotranspiration from temperature. <i>Applied Engineering in Agriculture</i>, 1(2), 96–99.</li>
<li>Hersbach, H. et al. (2020). The ERA5 global reanalysis. <i>Quarterly Journal of the Royal Meteorological Society</i>, 146(730), 1999–2049.</li>
<li>IDEAM. Promedios climatológicos 1981–2010 (precipitación y temperatura); caudales medios diarios (HidrologiaNacionalDiaria, 2026);
Catálogo Nacional de Estaciones (datos.gov.co).</li>
<li>Lehner, B., Verdin, K. y Jarvis, A. (2008). New global hydrography derived from spaceborne elevation data (HydroSHEDS). <i>Eos</i>, 89(10), 93–94.</li>
<li>Muñoz-Sabater, J. et al. (2021). ERA5-Land: a state-of-the-art global reanalysis dataset for land applications. <i>Earth System Science Data</i>, 13, 4349–4383.</li>
<li>Taylor, K. E. (2001). Summarizing multiple aspects of model performance in a single diagram. <i>Journal of Geophysical Research</i>, 106(D7), 7183–7192.</li>
<li>Allen, R. G., Pereira, L. S., Raes, D. y Smith, M. (1998). <i>Crop evapotranspiration</i>. FAO Irrigation and Drainage Paper 56, Roma
(radiación extraterrestre, Anexo 3).</li>
</ul>
<p class="nota">Datos y procesamiento: scripts 01 a 21 del proyecto (Python: pysheds, rasterio, geopandas, xarray, scipy, matplotlib, Plotly).</p>""")

# ----------------------------------------------------------------------------- página
orden = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9", "p10", "p11", "p12", "p13", "p14", "ref"]
tabs = "".join(f'<button role="tab" type="button" id="t-{k}" aria-controls="{k}" aria-selected="false">{S[k][0]}</button>' for k in orden)
panes = "".join(f'<section role="tabpanel" id="{k}" aria-labelledby="t-{k}" hidden><h2>{S[k][0]}</h2>{S[k][1]}</section>' for k in orden)
page = (Path(__file__).parent / "13_informe_plantilla.html").read_text(encoding="utf-8")
page = page.replace("%%TABS%%", tabs).replace("%%PANES%%", panes).replace("%%DATA%%", json.dumps(DATA, ensure_ascii=False, separators=(",", ":")))
(OUT / "informe_artifact.html").write_text(page, encoding="utf-8")
(OUT / "index.html").write_text('<!doctype html>\n<html lang="es"><head><meta charset="utf-8">\n'
                                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                                + page.replace("</style>", "</style>\n</head><body>", 1) + "\n</body></html>", encoding="utf-8")
print(f"informe: {len(page.encode('utf-8')) / 1e6:.2f} MB; {len(list(IMG.glob('*.webp')))} figuras estáticas")
