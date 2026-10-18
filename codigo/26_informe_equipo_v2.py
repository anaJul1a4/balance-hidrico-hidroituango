"""
Versión 2 del informe del equipo: reproduce el texto de la versión editada por el equipo (PDF exportado de Google Docs,
"Trabajo 1 Hidrometeorología (1).pdf") sobre el Word con figuras HD, y la complementa. Todo lo agregado o corregido va
resaltado en amarillo: topografía y clima de la zona de estudio, discusión del sesgo de ERA5/ERA5-Land, definición del
diagrama de Taylor, numeración de tablas y figuras, erratas, conclusiones y referencias.

Entradas: ~/Downloads/Trabajo 1 Hidrometeorología - completo (figuras HD).docx  (formato, figuras, tablas)
          ~/Downloads/Trabajo 1 Hidrometeorología (1).pdf                       (texto del equipo)
Salida:   ~/Downloads/Trabajo 1 Hidrometeorología - v2 (cambios en amarillo).docx
"""
import copy
import re
from pathlib import Path

import docx
import pymupdf
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn

DL = Path.home() / "Downloads"
BASE = DL / "Trabajo 1 Hidrometeorología - completo (figuras HD).docx"
PDF = DL / "Trabajo 1 Hidrometeorología (1).pdf"
SALIDA = DL / "Trabajo 1 Hidrometeorología - v2 (cambios en amarillo).docx"

doc = docx.Document(BASE)
body = doc.element.body
norm = lambda s: re.sub(r"\s+", " ", s.replace("​", "")).strip()  # noqa: E731
EQ = norm(" ".join(p.get_text() for p in pymupdf.open(PDF)))


def seg(ini, fin):
    """Texto del equipo entre dos frases (incluidas), tomado del PDF."""
    a = EQ.index(ini)
    b = EQ.index(fin, a) + len(fin)
    return EQ[a:b]


# ============================================================================= texto con resaltado ==...==
TNR = '<w:rFonts w:ascii="Times New Roman" w:cs="Times New Roman" w:eastAsia="Times New Roman" w:hAnsi="Times New Roman"/>'


def _r(t, b=False, i=False, sz=None, hl=False, sub=False, sup=False):
    s = TNR + ('<w:b w:val="1"/><w:bCs w:val="1"/>' if b else "") + ('<w:i w:val="1"/><w:iCs w:val="1"/>' if i else "")
    s += '<w:highlight w:val="yellow"/>' if hl else ""
    s += f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>' if sz else ""
    s += '<w:vertAlign w:val="subscript"/>' if sub else ('<w:vertAlign w:val="superscript"/>' if sup else "")
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<w:r><w:rPr>{s}</w:rPr><w:t xml:space="preserve">{t}</w:t></w:r>'


def runs(texto, b=False, i=False, sz=None, hl=False):
    """==resaltado==, **negrita**, *cursiva*, _{sub}, ^{sup}; hl=True resalta todo."""
    out = []
    for k, trozo in enumerate(texto.split("==")):
        h = hl or k % 2 == 1
        for p in re.split(r"(\*\*.+?\*\*|\*.+?\*|_\{.+?\}|\^\{.+?\})", trozo):
            if not p:
                continue
            kw = dict(b=b, i=i, sz=sz, hl=h)
            if p.startswith("**"):
                p, kw["b"] = p[2:-2], True
            elif p.startswith("*"):
                p, kw["i"] = p[1:-1], True
            elif p.startswith("_{"):
                p, kw["sub"] = p[2:-1], True
            elif p.startswith("^{"):
                p, kw["sup"] = p[2:-1], True
            out.append(_r(p, **kw))
    return "".join(out)


PPR = {"body": '<w:spacing w:after="240" w:before="240" w:lineRule="auto"/><w:jc w:val="both"/>',
       "eq": '<w:spacing w:after="240" w:before="240" w:lineRule="auto"/><w:jc w:val="center"/>',
       "bullet": '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr><w:spacing w:after="0" w:before="120" w:lineRule="auto"/>'
                 '<w:ind w:left="720" w:hanging="360"/><w:jc w:val="both"/>',
       "title": '<w:spacing w:after="240" w:before="240" w:lineRule="auto"/><w:jc w:val="both"/>',
       "ref": '<w:spacing w:after="120" w:lineRule="auto"/><w:ind w:left="720" w:hanging="720"/><w:jc w:val="both"/>',
       "center": '<w:spacing w:after="0" w:lineRule="auto"/><w:jc w:val="center"/>',
       "nota": '<w:spacing w:after="0" w:before="240" w:lineRule="auto"/><w:jc w:val="both"/>'}


def par(texto, tipo="body", hl=False, **kw):
    return parse_xml(f'<w:p {nsdecls("w")}><w:pPr>{PPR[tipo]}</w:pPr>{runs(texto, b=(tipo == "title"), hl=hl, **kw)}</w:p>')


# ============================================================================= utilidades
def P(ini):
    for p in doc.paragraphs:
        if norm(p.text).startswith(ini):
            return p
    raise KeyError(ini)


def texto(p, nuevo, hl=False, sz=None, b=None):
    """Reemplaza el texto del párrafo conservando su formato de párrafo (pPr)."""
    r0 = p.runs[0] if p.runs else None
    bb = b if b is not None else bool(r0 is not None and r0.bold)
    ii = bool(r0 is not None and r0.italic)
    tam = sz or (int(r0.font.size.pt * 2) if r0 is not None and r0.font.size else None)
    for el in list(p._p):
        if el.tag != qn("w:pPr"):
            p._p.remove(el)
    for el in parse_xml(f'<w:p {nsdecls("w")}>{runs(nuevo, b=bb, i=ii, sz=tam, hl=hl)}</w:p>'):
        p._p.append(el)


def leyenda(p, nuevo):
    """Leyenda «Figura/Tabla N. texto»: número en negrita (y cursiva en tablas), como en el documento."""
    tab = norm(p.text).startswith("Tabla")
    n, resto = nuevo.split(". ", 1)
    for el in list(p._p):
        if el.tag != qn("w:pPr"):
            p._p.remove(el)
    xml = runs(n + ". ", b=True, i=tab, sz=18) + runs(resto, i=tab, sz=18)
    for el in parse_xml(f'<w:p {nsdecls("w")}>{xml}</w:p>'):
        p._p.append(el)


def borrar(*els):
    for e in els:
        e = getattr(e, "_p", e)
        e.getparent().remove(e)


def despues(ancla, nuevos):
    ancla = getattr(ancla, "_p", ancla)
    for e in nuevos:
        ancla.addnext(e); ancla = e
    return ancla


def antes(ancla, nuevos):
    ancla = getattr(ancla, "_p", ancla)
    for e in nuevos:
        ancla.addprevious(e)


def tabla_con(txt):
    for t in doc.tables:
        if any(txt in c.text for c in t.rows[0].cells) or any(txt in c.text for r in t.rows for c in r.cells):
            return t
    raise KeyError(txt)


def entre(a, b):
    """Elementos del cuerpo estrictamente entre a y b."""
    a, b = getattr(a, "_p", a), getattr(b, "_p", b)
    out, e = [], a.getnext()
    while e is not None and e is not b:
        out.append(e); e = e.getnext()
    return out


# ============================================================================= portada (texto del equipo)
despues(P("David Moreno Yepes"), [par("https://anajul1a4.github.io/balance-hidrico-hidroituango/", "center"),
                                  par("https://damorenoy.github.io/Hidrometeorologia/", "center")])
despues(P("Octubre de 2026"), [par("Nota: Las figuras presentadas en este informe se limitan a lo solicitado en la rúbrica, no obstante "
                                   "análisis adicionales se produjeron en ambos repositorios de github", "nota", sz=20)])

# ============================================================================= resumen e introducción (texto del equipo)
texto(P("Conocer cuánta agua produce"), seg("Estudiar las alteraciones en la oferta hídrica de una cuenca",
                                            "es la principal limitación para estimarla."))
texto(P("Estos impactos son críticos"), seg("Estos impactos son críticos para el sector eléctrico", "aguas arriba (1010–1100 m³/s).")
      .replace("(1010–1100 m³/s).", "(1010–1100 m³/s; ==Alcaldía de Medellín, s. f.==).")
      + " " + seg("Por eso es necesario saber cuánta agua", "con que se estima."))
borrar(P("Este trabajo estima el balance hídrico de largo plazo"))

# ============================================================================= 1. selección: zona de estudio y topografía
borrar(P("Descripción de la zona de estudio"), P("El río Cauca nace en el Macizo Colombiano, en el cerro"),
       P("El relieve es muy contrastante"), P("El régimen de lluvias es bimodal, como resultado"))
h1 = P("Selección y delimitación de la cuenca del río Cauca")
texto(h1, "Selección y delimitación de la cuenca de estudio")
ZONA = [
    par("El río Cauca nace en el Macizo Colombiano entre las Cordilleras Occidental y Central de los Andes ==y recorre unos 1360 km "
        "hacia el norte hasta desembocar en el río Magdalena (Minambiente, s. f.)==. En el recorrido de sus primeros 855 km (63% de su "
        "longitud) se conforma la cuenca aportante del embalse Hidroituango (7.136° N, 75.663° W), entre la cordillera Occidental y "
        "Central."),
    par("**Topografía.** La cuenca es un corredor estrecho y alargado, de unos 40 km de ancho medio, encajado entre dos cordilleras. "
        "La elevación va de 229 m, en el cañón del Cauca cerca de la presa, a 5273 m en los nevados de la cordillera Central (Nevado "
        "del Ruiz y Santa Isabel), con una media de 1806 m. La cordillera Central es la más alta y la que más área aporta; la "
        "Occidental es más baja y angosta, y separa la cuenca de la vertiente del Pacífico. A lo largo del río se distinguen tres "
        "ambientes: la cabecera en el Macizo, de fuerte pendiente; el valle geográfico del río Cauca, una planicie de pocas decenas "
        "de kilómetros de ancho que desciende apenas unos 950 m en 400 km entre Popayán y Cartago; y el cañón antioqueño, angosto y profundo, desde La "
        "Pintada hasta la presa. En pocas decenas de kilómetros se pasa así de un valle seco, a la sombra de la lluvia de la "
        "cordillera Occidental, a laderas muy húmedas, páramos y nieves perpetuas. Esta topografía controla la distribución de la "
        "lluvia (sección 2) y es también la que los productos globales de baja resolución no logran representar (sección 9).", hl=True),
    par("**Climatología de la cuenca**", hl=True),
    par("*Origen de la humedad.* La lluvia de Colombia se alimenta sobre todo de humedad del océano Atlántico y del reciclaje sobre el "
        "continente, en el que las cuencas del Orinoco y del Amazonas son proveedoras regionales clave. Sobre el occidente del país "
        "convergen además dos corrientes en chorro de niveles bajos: la del Chocó, que entra desde el Pacífico, y la del Caribe (Hoyos "
        "et al., 2018). El chorro del Chocó explica las lluvias extremas de la llanura del Pacífico (Poveda y Mesa, 2000), pero la "
        "cordillera Occidental intercepta buena parte de esa humedad antes de que llegue a la cuenca. Por eso el valle del Cauca queda a "
        "la sombra de la lluvia, con menos de 1200 mm/año, mientras las laderas expuestas de ambas cordilleras superan los 2500 mm/año "
        "(sección 2).", hl=True),
    par("*Ciclo bimodal.* La Zona de Convergencia Intertropical (ZCIT), una banda de ascenso y lluvia que sigue al sol, cruza los "
        "Andes colombianos dos veces al año: hacia el norte en marzo-mayo y hacia el sur en septiembre-noviembre. Su doble paso produce "
        "dos temporadas de lluvia y dos secas, diciembre-febrero y junio-agosto, cuando la ZCIT está más lejos (Mejía et al., 1999; "
        "Poveda, 2004; Carvajal et al., 1998). En esta cuenca la segunda temporada es la más lluviosa (máximo en octubre), y el régimen "
        "es bimodal en casi toda su área (sección 11). Los caudales siguen el ritmo de la lluvia con un rezago: en el valle alto, en "
        "Juanchito, julio-agosto-septiembre es el trimestre más seco (167–185 m³/s) y noviembre-enero el más caudaloso (322–363 m³/s); "
        "cerca del cierre, en Puerto Valdivia, los máximos son noviembre (1465 m³/s) y mayo (1351 m³/s) y el mínimo agosto (841 m³/s).",
        hl=True),
    par("*¿Hay inversión térmica en el valle y el cañón?* En las medias anuales no hay una inversión persistente: la temperatura "
        "disminuye con la altura de forma casi lineal desde el fondo del cañón hasta los nevados (R² = 0.986 para Tmed; sección 3). "
        "Sí hay una señal del efecto de valle. En las diez estaciones situadas por debajo de 1000 m (el valle del Cauca y el cañón, "
        "por ejemplo Cotové, en Santa Fe de Antioquia), la Tmax queda en promedio 0.4 °C por encima de la recta y la Tmin 0.2 °C por "
        "debajo, de modo que la amplitud diaria es mayor que la que predice la elevación. Esto es coherente con un fondo de valle que "
        "se calienta más de día y se enfría más de noche, cuando el aire frío desciende por las laderas y se acumula en el fondo. Esas "
        "inversiones nocturnas son de escala diaria y no pueden verse con normales climatológicas; su efecto anual es menor de 0.5 °C.",
        hl=True),
    par("*¿Por qué es tan sensible a la variabilidad y al cambio climático?* Por cuatro razones:", hl=True),
    par("La cuenca está en la región donde el ENSO tiene su señal más fuerte y temprana (Poveda et al., 2011). En El Niño disminuyen "
        "la lluvia y los caudales; la sequía de 1992 obligó a un racionamiento de energía de cerca de un año (Carvajal et al., 1998).",
        "bullet", hl=True),
    par("La escorrentía amplifica los cambios de la lluvia. Con un índice de aridez de 0.71, la curva de Budyko predice que una "
        "variación de 10 % en la lluvia produce una de unos 19 % en la escorrentía, y los caudales observados responden aún más: su "
        "variabilidad interanual es 2.6 veces la de la lluvia (sección 7).", "bullet", hl=True),
    par("Los glaciares de la cordillera Central, en las cabeceras de la cuenca, retroceden con rapidez. El área glaciar de Colombia "
        "pasó de 60 km² en 2002 a menos de 45 km² en 2007 (Poveda y Pineda, 2009). Su aporte al caudal medio es pequeño, pero su "
        "retroceso es una señal directa del calentamiento en la alta montaña, donde nacen los ríos.", "bullet", hl=True),
    par("La oferta está muy comprometida: el embalse de Salvajina regula el alto Cauca desde 1985, y en el valle la agricultura, "
        "principalmente la caña de azúcar, demanda cerca del 80 % del recurso hídrico (Carvajal et al., 1998). Con poco margen entre "
        "oferta y demanda, cualquier reducción de la lluvia se traduce en déficit.", "bullet", hl=True),
    par("Este trabajo no analiza tendencias, así que estas razones describen la sensibilidad de la cuenca y no un cambio ya observado "
        "en ella.", hl=True)]
despues(h1, ZONA)

g30 = P("Para los cálculos de las secciones siguientes se usó")
texto(g30, "Para los cálculos de las secciones siguientes se usó una delimitación hecha con el DEM Copernicus GLO-30==, remuestreado "
           "a 90 m, que da 35 992 km²==. Su área coincide con la de ==HydroSHEDS (35 841 km²; Lehner et al., 2008)== con una diferencia "
           "de 0.4%. ==La diferencia con la Tabla 1 (35 283 km², 2 %) se debe a la resolución del DEM usado en QGIS, cuya celda de unos "
           "930 m suaviza las divisorias y el fondo del cañón.==")

# ============================================================================= 3–5. ajustes de redacción del equipo y erratas
texto(P("donde T₀ es la temperatura extrapolada"),
      "Donde T₀ es la temperatura extrapolada a nivel del mar y α es el gradiente vertical de temperatura. Se ajustó una sola regresión "
      "para toda la cuenca, ==porque== 47 estaciones no alcanzan para ecuaciones por subregión.")
texto(P("Los tres ajustes tienen R²"), seg("Se encontró que los tres ajustes tienen", "las diferencias entre ellos son significativas."))
texto(P("Para Colombia, Eslava (1992)"), seg("Para Colombia, Eslava (1992)", "dentro del rango típico de la región andina.")
      .replace("Chaves y Jaramillo (1998)", "Chaves y Jaramillo (==1999==)"))
texto(P("La temperatura media de la cuenca es de 18.5"), seg("La temperatura media de la cuenca es de 18.5", "75.6 km² con Tmin negativa."))
p = P("Temperaturas: se tomaron de las 12")
texto(p, "Temperaturas: se tomaron de las 12 regresiones mensuales T–Z ==de la sección 3==. Así, la ETP depende de la elevación por dos "
         "vías: la temperatura media y la amplitud térmica.", b=False)
texto(P("La ETP media de la cuenca es de 1409"), "La ETP media de la cuenca es de 1409 mm/año. Va desde 348 mm/año en los nevados hasta "
      "2003 mm/año en el cañón cálido, cerca de la presa (Tabla 6). Su mapa se presenta en la ==Figura 8==, junto con los de φ, ETR y R.")

# ============================================================================= 7. caudales
texto(P("Los caudales medios diarios se tomaron"), seg("Los caudales medios diarios se tomaron", "tres criterios de validez:"))
texto(P("Diez estaciones cumplen (Tabla 8)"), seg("Diez estaciones cumplen (Tabla 8).", "1000 km² acumulados (Figura 11)."))
cap_mapa, cap_disp = P("Figura 10. Estaciones de caudal"), P("Figura 11. Disponibilidad de datos")
img_mapa, img_disp = cap_mapa._p.getprevious(), cap_disp._p.getprevious()
antes(img_mapa, [img_disp, cap_disp._p])                       # el equipo invirtió el orden: disponibilidad primero
leyenda(cap_disp, seg("Figura 10. Disponibilidad de datos", "rojo: no cumple."))
leyenda(cap_mapa, "Figura 11. Estaciones de caudal validadas y sus áreas de drenaje.")
texto(P("El caudal crece aguas abajo de forma regular"), seg("El caudal crece aguas abajo de forma regular", "el caudal medio de 1010–1100 m³/s")
      + " ==que reporta el proyecto en el sitio de presa (Alcaldía de Medellín, s. f.)==.")

# ============================================================================= 8. balance (texto del equipo)
p_ini = P("Para cada área de drenaje con caudal observado se promediaron")
eqb = p_ini._p.getnext()
texto(p_ini, seg("El balance se validó en cada área de drenaje", "el error baja a +0.6 %."))
borrar(eqb)
leyenda(P("Tabla 10. Balance hídrico de largo plazo"), "Tabla 10. Balance hídrico de largo plazo por área de drenaje (1981–2010)")
p = P("El balance reproduce los caudales observados en todas")
texto(p, seg("El signo del error cambia a lo largo del río.", "no tiene un signo dominante."))
despues(p, [par(seg("Las decisiones sobre la precipitación casi no cambian", "usarla con valores promedio sobreestima la ETR."))])
leyenda(P("Tabla 11. Sensibilidad del error"), "Tabla 11. Sensibilidad del error de cierre a las decisiones metodológicas")
p_inc = P("Las principales fuentes de incertidumbre son")
texto(p_inc, seg("A estas decisiones se suman otras fuentes de incertidumbre.", "de modo que el balance de largo plazo cierra."))
for ini in ["Precipitación: pocas estaciones sobre 3000 m", "Evapotranspiración: Hargreaves sobrestima", "Caudal: las curvas de calibración",
            "Áreas de drenaje: en el valle plano", "Almacenamiento: el supuesto"]:
    borrar(P(ini))
texto(P("Poveda et al. (2007) aplicaron el mismo esquema"), seg("Estos resultados coinciden con los de Poveda et al. (2007)",
                                                                  "comparable con los errores típicos de esos balances nacionales."))

# ============================================================================= 9. productos
texto(P("Se evaluaron tres productos de precipitación"), seg("Se evaluaron tres productos de precipitación de cobertura global.",
                                                              "y no al periodo") + ".")
t12 = tabla_con("CHIRPS v3.0")                                  # tabla 12: el equipo quitó la fila de CHIRPS v3.0
for r in list(t12.rows):
    if "CHIRPS v3.0" in r.cells[0].text:
        r._tr.getparent().remove(r._tr)
texto(P("Cada producto se convirtió a mm/mes"), seg("Cada producto se convirtió a mm/mes y se recortó a la cuenca.",
                                                    "apunta a un sesgo del producto sobre la cordillera."))
borrar(P("Se eligió CHIRPS v2.0 como producto principal"))
h_mapas = P("Precipitación media anual según cada producto")
despues(h_mapas, [par(seg("La Figura 13 compara la precipitación media anual", "con la de tres productos: CHIRPS v2.0, ERA5-Land y ERA5.")
                      + " La Tabla ==13== resume sus estadísticos sobre la cuenca, y la Figura 14 muestra la razón entre cada producto y "
                        "el campo del IDEAM.")])
borrar(h_mapas)
leyenda(P("Tabla 13. Precipitación media anual"), "Tabla 13. ==Precipitación media anual de la cuenca según cada fuente (1981–2010).==")
p_ch = P("CHIRPS v2.0 reproduce el patrón y la magnitud")
texto(p_ch, seg("CHIRPS reproduce tanto el patrón como la magnitud del IDEAM", "lo que respalda su uso en esta cuenca."))
p_era = P("ERA5 y ERA5-Land triplican la lluvia de la cuenca, con medias")
ERA = [
    par("**¿Pueden llover 20 000 mm/año en la cuenca?** No hay ningún registro que lo respalde. Las mayores lluvias medias de Colombia "
        "se miden en la llanura del Pacífico, en el Chocó: en Lloró se reportaron 13 473 mm/año (1952–1954), uno de los valores más "
        "altos del planeta, asociado a la interacción entre el océano, la atmósfera y el chorro de bajo nivel del Chocó (Poveda y Mesa, "
        "2000). Dentro de la cuenca, la estación más lluviosa registra 4373 mm/año y el máximo del kriging es de 3441 mm/año; ni "
        "siquiera las estaciones más húmedas de la vertiente del Pacífico en el vecindario superan los 7400 mm/año. ERA5 y ERA5-Land, "
        "en cambio, dan más de 10 000 mm/año en el 12–13 % de la cuenca y máximos de 18 300 y 20 200 mm/año, una vez y media lo de "
        "Lloró, en una cuenca interandina. Esos valores no tienen sustento físico.", hl=True),
    par("Los máximos de ERA5 no están en las cumbres: el 1 % más lluvioso de sus celdas está a 1200–1600 m de elevación, en la cuenca "
        "media entre el norte del Valle y Caldas (3.7–5.1° N), donde la red del IDEAM es precisamente más densa y no mide nada "
        "parecido. Además, su lluvia no se relaciona con la elevación de la forma en que lo hace la observada, y su patrón espacial "
        "no se parece al del IDEAM (r ≈ −0.06): no reproduce la sombra de lluvia del valle ni las laderas húmedas (Figura 14).", hl=True),
    par("**¿A qué se debe el sesgo?** A las dos causas planteadas, que actúan juntas:", hl=True),
    par("Ausencia de calibración con estaciones. La precipitación de ERA5 no es una observación: se acumula a partir de los "
        "pronósticos de corto plazo del modelo, y ERA5 no asimila datos de pluviómetros, salvo compuestos de radar y pluviómetros en "
        "Estados Unidos desde 2009 (Hersbach et al., 2020). Ninguna estación del IDEAM corrige su lluvia, a diferencia de CHIRPS, que "
        "combina el satélite con estaciones (Funk et al., 2015). ERA5-Land tampoco la corrige: no asimila observaciones y obtiene su "
        "precipitación interpolando linealmente la de ERA5 de unos 31 km a unos 9 km (Muñoz-Sabater et al., 2021). Por eso las dos "
        "medias son casi iguales (5961 y 5976 mm/año): una malla más fina no agrega información sobre la lluvia.", "bullet", hl=True),
    par("Resolución y topografía compleja. Con celdas de 0.1–0.25° (11–28 km), un valle de pocas decenas de kilómetros de ancho entre dos "
        "cordilleras ocupa una o dos celdas, y el relieve del modelo se suaviza: desaparece la sombra de lluvia y la convección y el ascenso "
        "orográfico, que el modelo parametriza, generan lluvia sobre laderas que no existen como tales a esa escala. Posada-Marín et "
        "al. (2019) encontraron un problema similar en ERA-Interim, el antecesor de ERA5, en los Andes centrales de Colombia: "
        "sobrestima la lluvia en la temporada seca de los años El Niño, y los autores lo atribuyen a una topografía simplificada que "
        "excluye el valle interandino del Cauca. Vega-Durán et al. (2021) también encontraron que ERA5 sobrestima de forma "
        "consistente la lluvia de las estaciones del IDEAM en la cuenca del Sinú, aunque mucho menos que aquí, porque el Sinú es una "
        "cuenca de llanura.", "bullet", hl=True),
    par("La resolución por sí sola no explica el exceso, porque promediar en celdas grandes suaviza los extremos en lugar de "
        "amplificarlos. El sesgo surge de la física del modelo sobre una topografía mal representada, y persiste porque no hay "
        "estaciones que lo corrijan. Para usar estos productos en la cuenca habría que corregir su sesgo con las estaciones, por "
        "ejemplo con un mapeo de cuantiles; en este trabajo se evaluaron sin corregir, como pide el enunciado.", hl=True)]
despues(p_era, ERA)
borrar(p_era)

# ============================================================================= 10. balance con productos (texto del equipo)
texto(P("Balance hídrico con cada producto"), "==Balance== hídrico con cada producto")   # el equipo escribió «Blande»: se conserva «Balance»
p_bp = P("Se repitió el balance de la sección 8 cambiando")
texto(p_bp, seg("Para evaluar los productos de precipitación se repitió", "que equivalen a 950 mm/año.")
      .replace("el balance del punto 9", "el balance de la ==sección 8=="))
p_bp2 = par(seg("El error del balance mezcla los errores de la P", "usando el píxel que contiene a cada estación."))
despues(p_bp, [p_bp2])
t14, t15 = P("Tabla 14. Balance hídrico en el cierre"), P("Tabla 15. Desempeño del balance")
tb14, tb15 = t14._p.getnext(), t15._p.getnext()
for r in list(doc.tables):
    if r._tbl is tb14:
        for row in list(r.rows):
            if "CHIRPS v3.0" in row.cells[0].text:
                row._tr.getparent().remove(row._tr)
leyenda(t14, "Tabla ==14==. Balance de largo plazo en el cierre (Hidroituango, 1981–2010) con cada producto de precipitación.")
leyenda(t15, "Tabla ==15==. Desempeño del balance en las nueve estaciones de caudal, sin incluir el cierre.")
cap15 = P("Figura 15. Escorrentía de largo plazo")
img15 = cap15._p.getprevious()
despues(p_bp2, [img15, cap15._p])                              # orden del equipo: figura 15 antes de las tablas
p_ch2 = P("Con CHIRPS v2.0 el balance cierra con un error")
texto(p_ch2, seg("Con CHIRPS, el error en el cierre es incluso menor", "lo que distingue a los productos es el sesgo.")
      .replace("(Tablas 16 y 17)", "(Tablas ==14 y 15==)"))
despues(cap15, [p_ch2._p])
texto(P("Para separar el error de la precipitación del error"), seg("La P necesaria muestra de dónde viene el error.",
                                                                    "con r ≈ 0.06."))

# ============================================================================= 11. ciclo anual (texto del equipo)
p_c = P("Para cada mes se interpoló la normal mensual")
texto(p_c, seg("Para el ciclo anual se interpoló la normal mensual", "la media mensual de la cuenca, 166 mm.")
      .replace("(Figura 17 y Tabla 18)", "(Figura 17 y Tabla ==16==)").replace("según quedará", "según ==quedara=="))
despues(p_c, [par(seg("En cada celda se identificaron además tres cosas", "índice de estacionalidad de Walsh y Lawler (1981):")
                  .replace("tres cosas (Figura 16)", "tres cosas (Figura ==18==)")),
              par("SI = (1/P_{a}) · Σ |P_{m} − P_{a}/12|", "eq"),
              par(seg("Aquí P_m es la lluvia de cada mes", "a medida que se concentra en pocos.").replace("P_m", "P_{m}").replace("P_a", "P_{a}"))])
leyenda(P("Tabla 16. Precipitación media mensual"), "Tabla 16. Precipitación media mensual de la cuenca (1981–2010).")
borrar(P("Mes húmedo: precipitación mayor que la media"))
leyenda(P("Figura 18. Mes de máxima lluvia"), "Figura 18. Mes de máxima lluvia, número de picos del ciclo anual e índice de estacionalidad "
                                               "==de Walsh y Lawler en cada celda.==")
texto(P("La cuenca tiene un régimen bimodal, con dos"), seg("La suma de los 12 meses (1998 mm)", "modulado por la topografía."))
texto(P("El régimen es bimodal en el 99.8 %"), seg("El régimen es casi uniforme en el espacio.", "el de julio–agosto es el más severo."))

# ============================================================================= 12. comparación entre productos
texto(P("Comparación del ciclo anual entre productos"), "Comparación entre productos")
p_t = P("El ciclo anual de cada producto, como promedio")
texto(p_t, seg("El ciclo anual de cada producto, promediado sobre la cuenca", "es el RMSE centrado normalizado."))
TAYLOR = [
    par("**Diagrama de Taylor.** Es un diagrama polar propuesto por Taylor (2001) para resumir en un solo punto qué tanto se parece "
        "una serie (el producto) a una de referencia (el IDEAM). Usa tres estadísticos: la correlación r, la desviación estándar de "
        "cada serie (σ_{f} del producto y σ_{r} de la referencia) y el error cuadrático medio centrado E′, que es el RMSE después de "
        "restar a cada serie su media, es decir, el error que queda sin contar el sesgo. Los tres están ligados por la ley de los "
        "cosenos:", hl=True),
    par("E′² = σ_{f}² + σ_{r}² − 2 · σ_{f} · σ_{r} · r", "eq", hl=True),
    par("Por eso pueden dibujarse en el mismo plano. Cada producto es un punto cuya distancia al origen es su desviación estándar "
        "normalizada (σ_{f}/σ_{r}) y cuyo ángulo respecto al eje horizontal es arccos(r). La referencia queda en el punto (1, 0) del "
        "eje horizontal, y la distancia de cada producto a ese punto es su E′ normalizado. Un producto perfecto cae sobre la "
        "referencia; si está sobre el arco σ = 1 tiene la variabilidad correcta; si está más lejos del origen exagera la amplitud del "
        "ciclo; y cuanto mayor es su ángulo, peor reproduce la forma del ciclo. Como E′ excluye el sesgo, el diagrama se lee junto "
        "con la Tabla 17, que sí lo incluye.", hl=True)]
despues(p_t, TAYLOR)
p_res = P("CHIRPS v2.0 es el mejor producto en todos los criterios")
cap19 = P("Figura 19. Ciclo anual")
img19 = cap19._p.getprevious()
texto(p_res, seg("CHIRPS reproduce el ciclo del IDEAM casi exactamente", "porque toma su precipitación de ERA5.")
      .replace("(Tabla 19 y Figuras 19 y 20)", "(Tabla ==17== y Figuras 19 y 20)"))
antes(img19, [p_res._p])
leyenda(P("Tabla 17. Métricas del ciclo anual"), "Tabla 17. Métricas del ciclo anual de cada producto frente al IDEAM (n = 12).")
texto(P("Una limitación de esta evaluación es que el ciclo"), seg("En conjunto, CHIRPS es el mejor producto para esta cuenca",
                                                                  "y en ella CHIRPS también cierra."))

# ============================================================================= decisiones: el equipo las dejó en los repositorios
h_dec = P("Decisiones metodológicas y análisis adicionales")
tab_dec = tabla_con("Quantile mapping")._tbl
borrar(*entre(h_dec, tab_dec), tab_dec, h_dec)

# ============================================================================= conclusiones y referencias (nuevas, en amarillo)
h_con = P("Conclusiones")
for e in entre(h_con, None):
    if e.tag == qn("w:p"):
        e.getparent().remove(e)
texto(h_con, "Conclusiones", hl=True, b=True)
CONC = [
    "La cuenca aportante a Hidroituango (35 992 km²) recibe 1985 mm/año de lluvia, evapora 1085 mm/año (55 %) y produce 900 mm/año de "
    "escorrentía, unos 1026 m³/s en la presa, valor consistente con el caudal observado transferido (1020–1084 m³/s) y con el que "
    "reporta el proyecto (1010–1100 m³/s).",
    "El balance Q = P − ETR, con kriging, Hargreaves-Samani y Budyko celda a celda, reproduce los caudales observados con errores de "
    "±7 % en las estaciones y de −5.3 % en el cierre, dentro de la incertidumbre de la medición de caudales, como en los balances "
    "nacionales de Poveda et al. (2007). La principal limitación es la falta de estaciones de lluvia en alta montaña.",
    "La temperatura depende casi solo de la elevación (R² > 0.96). Hargreaves sobrestima la ETP del IDEAM en un 22 %, como se ha "
    "reportado en la zona cafetera (Ramírez et al., 2011), pero conserva su patrón espacial (r = 0.92).",
    "Los caudales responden al ENSO con una variabilidad interanual 2.6 veces mayor que la de la lluvia, más de lo que predice la "
    "curva de Budyko, lo que confirma el papel de la humedad del suelo y la evapotranspiración (Poveda et al., 2001).",
    "CHIRPS v2.0 es el producto más adecuado para esta cuenca: +2 % de lluvia, cierre de −2.2 % y r = 0.998 en el ciclo anual. ERA5 y "
    "ERA5-Land triplican la lluvia, con máximos de hasta 20 000 mm/año que superan los registros más altos del país, porque su "
    "precipitación proviene de un modelo que no se calibra con estaciones y que no resuelve la topografía de dos cordilleras y un "
    "valle interandino. No deben usarse sin corregir su sesgo.",
    "La lluvia es bimodal en casi toda la cuenca, con la temporada principal en octubre-noviembre y el estiaje más severo en "
    "julio-agosto, lo que define dos periodos críticos al año para la operación del embalse."]
ancla = despues(h_con, [par(t, "bullet", hl=True) for t in CONC])
REFS = [
    "Alcaldía de Medellín. (s. f.). *Hidroituango es pura energía y confianza para Colombia*. https://www.medellin.gov.co/es/sala-de-"
    "prensa/noticias/hidroituango-es-pura-energia-y-confianza-para-colombia/",
    "Allen, R. G., Pereira, L. S., Raes, D. y Smith, M. (1998). *Crop evapotranspiration: Guidelines for computing crop water "
    "requirements* (FAO Irrigation and Drainage Paper 56). FAO.",
    "Barco, J., Cuartas, A., Mesa, O., Poveda, G., Vélez, J. I., Mantilla, R., Hoyos, C., Mejía, J. F., Botero, B. y Montoya, M. (2000). "
    "Estimación de la evaporación en Colombia. *Avances en Recursos Hidráulicos*, 7, 43–51.",
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
    "Posada-Marín, J. A., Rendón, A. M., Salazar, J. F., Mejía, J. F. y Villegas, J. C. (2019). WRF downscaling improves ERA-Interim "
    "representation of precipitation around a tropical Andean valley during El Niño: Implications for GCM-scale simulation of "
    "precipitation over complex terrain. *Climate Dynamics*, 52, 3609–3629.",
    "Poveda, G. (2004). La hidroclimatología de Colombia: una síntesis desde la escala inter-decadal hasta la escala diurna. *Revista de "
    "la Academia Colombiana de Ciencias Exactas, Físicas y Naturales*, 28(107), 201–221.",
    "Poveda, G., Álvarez, D. M. y Rueda, O. A. (2011). Hydro-climatic variability over the Andes of Colombia associated with ENSO: A "
    "review of climatic processes and their impact on one of the Earth's most important biodiversity hotspots. *Climate Dynamics*, 36, "
    "2233–2249.",
    "Poveda, G., Jaramillo, A., Gil, M. M., Quiceno, N. y Mantilla, R. I. (2001). Seasonality in ENSO-related precipitation, river "
    "discharges, soil moisture, and vegetation index in Colombia. *Water Resources Research*, 37(8), 2169–2178.",
    "Poveda, G. y Pineda, K. (2009). Reassessment of Colombia's tropical glaciers retreat rates: Are they bound to disappear during "
    "the 2010–2020 decade? *Advances in Geosciences*, 22, 107–116.",
    "Poveda, G. y Mesa, O. J. (2000). On the existence of Lloró (the rainiest locality on Earth): Enhanced ocean-land-atmosphere "
    "interaction by a low-level jet. *Geophysical Research Letters*, 27(11), 1675–1678.",
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
clave = lambda s: unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore")  # noqa: E731
despues(ancla, [par("Referencias", "title", hl=True)] + [par(r, "ref", hl=True) for r in sorted(REFS, key=clave)])

doc.save(SALIDA)
print(SALIDA)
