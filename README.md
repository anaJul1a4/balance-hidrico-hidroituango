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

CHIRPS v2.0 es el producto adecuado para esta cuenca. ERA5 y ERA5-Land triplican la lluvia, con máximos de hasta 20 000 mm/año, por
dos razones: no asimilan pluviómetros y su resolución no representa el valle interandino.

**Clima y caudales**

- La lluvia es bimodal en el 99,8 % del área, con máximos en abril (218 mm) y octubre (240 mm).
- Los caudales responden al ENSO con una variabilidad interanual 2,6 veces mayor que la de la lluvia.

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
| `codigo/` | Scripts de Python, numerados en el orden de ejecución (01 a 26) |

## Cómo reproducir

1. Instalar las dependencias: `pip install -r requirements.txt` (Python 3.13).
2. Organizar los datos de entrada, que no están en el repositorio por su tamaño y su origen:
   - DEM Copernicus GLO-30 (OpenTopography o AWS Open Data).
   - Promedios climatológicos 1981–2010 y caudales medios diarios del IDEAM (HidrologiaNacionalDiaria).
   - Catálogo Nacional de Estaciones (datos.gov.co).
   - CHIRPS v2.0 (IRI Data Library).
   - ERA5 y ERA5-Land (Copernicus Climate Data Store).
3. Los scripts esperan esta estructura: `HIDROITUANGO/trabajo1/{scripts,datos,resultados}`, con los datos del curso en
   `HIDROITUANGO/`. Se ejecutan en orden: 01 (delimitación) … 21 (figuras complementarias). El 13 genera la página; del 22 al 26
   generan el informe y sus figuras.

| Scripts | Paso |
|---|---|
| 01–02, 19 | Delimitación con GLO-30 a 90 m, Priority-Flood + ε, mapa y verificación del cierre |
| 03–05 | Estaciones e interpolación de la precipitación (kriging e IDW con validación cruzada) |
| 06, 10 | Regresiones temperatura–elevación y mapas de temperatura |
| 07–09 | Caudales: descarga, caracterización y relleno |
| 11–12 | ETP (Hargreaves-Samani), ETR (Budyko) y balance por área de drenaje |
| 14–18, 20 | Productos de precipitación: cobertura, mapas, balance, climatología y comparación de ciclos; sensibilidad CHIRPS v2/v3 |
| 21 | Figuras complementarias (pisos térmicos, punto a píxel, estacionalidad, P necesaria) |
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
