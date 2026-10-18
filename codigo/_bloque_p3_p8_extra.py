# Figuras complementarias de los puntos 3 a 8 (se insertan en 13_informe_html.py antes del punto 9).
C15 = RES / "15_complementarias"
_cv = pd.read_csv(RES / "04_precipitacion_interpolada" / "validacion_cruzada_estaciones.csv")
DATA["cv"] = {"n": _cv.nombre.tolist(), "obs": _cv["P observada"].tolist(),
              "kri": _cv["P estimada Kriging ordinario (gaussiano)"].tolist(), "idw": _cv["P estimada IDW p=1.5"].tolist()}
S["p3"] = (S["p3"][0], S["p3"][1] + ancho(
    "s_cv", "<p><b>Precipitación observada frente a estimada en la validación cruzada.</b> Cada punto es una estación: su lluvia se estimó "
            "con las demás y se comparó con la medida. Sobre la línea 1:1 la estimación es exacta. Los puntos más alejados son núcleos "
            "lluviosos aislados (El Tambo, la ladera occidental) que ninguna estación vecina representa. Se muestran juntos kriging e IDW; el cursor muestra "
            "cada estación.</p>"))

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
             "diferencia entre la elevación del DEM y la del catálogo. Se muestran las tres variables; el cursor indica la estación.</p>"))

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
            "secos de El Niño (1992, 2015–2016) en todas las estaciones a la vez, y ningún salto sospechoso en una sola.</p>"))
