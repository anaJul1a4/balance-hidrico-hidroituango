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
    figura("informe_figs/panel_P_productos.png", "p11_panel", "Precipitación media anual multianual 1981–2010",
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
      ("Escala de color común por variable", "cada valor tiene el mismo color en todos los mapas de P (rojo en lo seco, amarillo y azul en lo lluvioso): 1000 mm es el mismo tono en IDEAM, CHIRPS y ERA5. Cada barra llega sólo hasta el máximo de su mapa")])}
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
                   "El cursor muestra el valor de cada producto.</p>") +
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
                   "El cursor muestra el valor de cada región.</p>") +
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
    ancho("s_p14", "<p><b>Ciclo anual de la cuenca por producto</b> (media mensual 1981–2010 promediada sobre la cuenca). El cursor "
                   "muestra la lluvia de cada mes y su porcentaje del total anual, que compara sólo la estacionalidad.</p>",
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
                  "para que la comparación sea justa. Se muestran los cuatro productos; el cursor indica la estación.</p>") + f"""
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
