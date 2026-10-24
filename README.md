# Balance hídrico de largo plazo · Río Cauca hasta Hidroituango

Trabajo 1 de Hidrometeorología, Facultad de Minas, Universidad Nacional de Colombia, sede Medellín (octubre de 2026).
Juliana Aguirre Lopera y David Moreno Yepes.

Este trabajo estima el balance hídrico de largo plazo (1981–2010) de la **cuenca aportante a Hidroituango**: el río Cauca desde el
Macizo Colombiano hasta la presa, que drena 35 992 km². Para estimarlo usa estaciones del IDEAM, el DEM Copernicus GLO-30 y tres
productos globales de precipitación (CHIRPS, ERA5-Land y ERA5).

- **Página interactiva:** https://anajul1a4.github.io/balance-hidrico-hidroituango/
- **Informe escrito:** [`informe/`](informe/) (Word y PDF; la versión 2 marca en amarillo lo agregado a la versión del equipo)
- **Metodología, decisiones y lecciones:** [`docs/METODOLOGIA_Y_DECISIONES.md`](docs/METODOLOGIA_Y_DECISIONES.md)
- **Cómo se habría corregido el sesgo de ERA5:** [`docs/CORRECCION_SESGO_ERA5.md`](docs/CORRECCION_SESGO_ERA5.md)

## Resultados principales

**Balance de la cuenca (1981–2010)**

| Variable | Lámina | Caudal equivalente |
|---|---|---|
| Precipitación P (kriging de 266 estaciones IDEAM) | 1985 mm/año | 2264 m³/s |
| ETP (Hargreaves-Samani) | 1409 mm/año | 1606 m³/s |
| ETR (Budyko celda a celda) | 1085 mm/año | 1238 m³/s |
| Escorrentía R = P − ETR | 900 mm/año | 1026 m³/s |
| Caudal observado (Puerto Valdivia transferido por áreas) | 950 mm/año | 1084 m³/s |

En el cierre, el balance difiere del caudal observado en −5,3 %. En las nueve estaciones de caudal del río, el error va de −7 % a +7 %
(error absoluto medio de 4,5 %).

**Productos de precipitación**

| Producto | P (mm/año) | Sesgo frente al IDEAM | r espacial | Error del balance en el cierre | r del ciclo anual |
|---|---|---|---|---|---|
| IDEAM (kriging) | 1985 | — | — | −5,3 % | — |
| CHIRPS v2.0 | 2026 | +2 % | 0,89 | −2,2 % | 0,998 |
| ERA5-Land | 5961 | +200 % | −0,06 | +390 % | 0,69 |
| ERA5 | 5976 | +201 % | −0,06 | +392 % | 0,62 |

CHIRPS v2.0 es el producto adecuado para esta cuenca. ERA5 y ERA5-Land triplican la lluvia, con máximos de hasta 20 000 mm/año,
porque no asimilan pluviómetros y su física no resuelve el valle interandino. No es un problema de resolución: el IDEAM degradado a
la celda de ERA5 sigue cerrando el balance (−5,6 %).

Con un mapeo de cuantiles (referencia CHIRPS, validado en 1996–2010), los dos reanálisis cierran el balance (+0,5 % y −2,7 %). Aun
así, su lluvia anual se correlaciona con el caudal mucho menos que CHIRPS (0,62–0,82 frente a 0,91–0,94). Ver
[`docs/CORRECCION_SESGO_ERA5.md`](docs/CORRECCION_SESGO_ERA5.md).

**Clima y caudales**

- La lluvia es bimodal en el 99,8 % del área, con máximos en abril (218 mm) y octubre (240 mm).
- Los caudales responden al ENSO con una variabilidad interanual 2,6 veces mayor que la de la lluvia.

## Extensión: operación del embalse con pywr

Simulación diaria 1981–2010 de la operación de Hidroituango con [pywr](https://pywr.github.io/pywr/) (pestaña 15 de la página):

| Escenario | Energía media (GWh/año) | Año más seco | Agua vertida |
|---|---|---|---|
| 8 unidades (2400 MW), caudal mínimo 450 m³/s | 15 218 | 10 089 (1992) | 6 % |
| 4 unidades (1200 MW), caudal mínimo 450 m³/s | 10 315 | 9 535 (1987) | 36 % |

- Con 8 unidades la energía cae 13 % en años El Niño y sube 25 % en años La Niña.
- Pasar el caudal mínimo de 300 a 450 m³/s casi no cambia la energía anual, pero sí la del mes más seco.
- Los datos técnicos están verificados en EPM (2024) y en la Resolución 155 de 2009 de la ANLA.
- Supuestos principales: curva cota–volumen lineal y regla de operación de curva guía.
- Scripts: `codigo/33_aportes_presa_diarios.py`, `codigo/34_pywr_hidroituango.py` y `codigo/35_figura_pywr.py`. El 34 se ejecuta con
  `pip install pywr==1.31.1` en un entorno aparte.
- Resultados en `memorias/pywr/`.

## Extensión: pronóstico de caudales

Pronóstico del aporte diario a la presa con 1 a 30 días de anticipación (pestaña 16 de la página), prueba en 2006–2010:

- Grafo de 53 estaciones IDEAM más la presa, construido con las direcciones de flujo D8 del DEM (`codigo/36_grafo_estaciones.py`).
- Modelos: persistencia, climatología, regresión ridge, red densa (MLP), red de grafos (GNN) y análogos (KNN)
  (`codigo/37_pronostico_caudales.py`, `codigo/38_horizonte_knn.py`; requieren `torch` y `scikit-learn`).
- La GNN no supera a la regresión lineal (NSE a 1 día: 0.89 frente a 0.91). El pronóstico es útil hasta unos 7 días (NSE ≈ 0.6);
  a más de 10 días la mejora sobre la persistencia es casi nula y sólo el KNN conserva algo de habilidad. Los intervalos del 80 %
  del KNN contienen el caudal observado sólo el 56–72 % de las veces.
- Resultados en `memorias/pronostico/`.

## Contenido del repositorio

| Carpeta | Contenido |
|---|---|
| `index.html`, `img/` | Página interactiva (GitHub Pages) |
| `informe/` | Informe escrito (Word y PDF) |
| `docs/` | Memorias: metodología, decisiones, análisis adicionales y lecciones; corrección del sesgo de ERA5 |
| `memorias/excel/` | Libros de cálculo con fórmulas vivas: puntos 4, 8 (caracterización y relleno, en libros separados), 9 y 12 |
| `memorias/tablas/` | Tablas de resultados en CSV (morfometría, validación cruzada, regresiones, balances, métricas) |
| `datos/` | Caudales mensuales del IDEAM procesados (1981–2010 y registro completo) y priorización de estaciones |
| `figuras/` | Figuras del informe en alta resolución |
| `codigo/` | Scripts de Python, numerados en el orden de ejecución (01 a 30) |

## Cómo reproducir

1. Instalar las dependencias: `pip install -r requirements.txt` (Python 3.13).
2. Organizar los datos de entrada, que no están en el repositorio por su tamaño y su origen:
   - DEM Copernicus GLO-30 (OpenTopography o AWS Open Data).
   - Promedios climatológicos 1981–2010 y caudales medios diarios del IDEAM (HidrologiaNacionalDiaria).
   - Catálogo Nacional de Estaciones (datos.gov.co).
   - CHIRPS v2.0 (IRI Data Library).
   - ERA5 y ERA5-Land (Copernicus Climate Data Store).
3. Los scripts esperan esta estructura: `HIDROITUANGO/trabajo1/{scripts,datos,resultados}`, con los datos del curso en
   `HIDROITUANGO/`. Se ejecutan en orden: 01 (delimitación) … 21 (figuras complementarias) y 27–29 (corrección de ERA5). El 13 genera la
   página; del 22 al 26 y el 30 generan el informe, sus figuras y el documento de cambios.

| Scripts | Paso |
|---|---|
| 01–02, 19 | Delimitación con GLO-30 a 90 m, Priority-Flood + ε, mapa y verificación del cierre |
| 03–05 | Estaciones e interpolación de la precipitación (kriging e IDW con validación cruzada) |
| 06, 10 | Regresiones temperatura–elevación y mapas de temperatura |
| 07–09 | Caudales: descarga, caracterización y relleno |
| 11–12 | ETP (Hargreaves-Samani), ETR (Budyko) y balance por área de drenaje |
| 14–18, 20 | Productos de precipitación: cobertura, mapas, balance, climatología y comparación de ciclos; sensibilidad CHIRPS v2/v3 |
| 21 | Figuras complementarias (pisos térmicos, punto a píxel, estacionalidad, P necesaria) |
| 27–29 | Sensibilidad a la resolución y corrección del sesgo de ERA5 por mapeo de cuantiles |
| `escalas.py` | Escalas de color por variable, comunes a todos los mapas |
| `productos.py` | Lectura homogénea de CHIRPS, ERA5 y ERA5-Land |
| `priority_flood.py` | Relleno de depresiones Priority-Flood + ε (Barnes et al., 2014), en numba |

## Fuentes de datos

- IDEAM: promedios climatológicos 1981–2010, caudales medios diarios y Catálogo Nacional de Estaciones.
- European Space Agency (2021): Copernicus GLO-30.
- Funk et al. (2015): CHIRPS v2.0.
- Hersbach et al. (2020): ERA5.
- Muñoz-Sabater et al. (2021): ERA5-Land.

Las referencias completas están en el informe.
