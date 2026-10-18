# Memoria metodológica: decisiones, análisis adicionales y lecciones

Este documento resume, punto por punto, cómo se hizo cada paso, qué decisiones propias se tomaron y por qué. También recoge los
problemas que aparecieron en el camino. Las cifras salen de [`memorias/tablas/`](../memorias/tablas/) y de los libros de
[`memorias/excel/`](../memorias/excel/).

## 1–2. Selección y delimitación

| Decisión | Justificación |
|---|---|
| Cuenca hasta la presa de Hidroituango, no la cuenca completa del Cauca | Es la cuenca que alimenta la central (2400 MW). La cuenca completa la estudió otro equipo. |
| DEM Copernicus GLO-30 remuestreado a 90 m (EPSG:3116) | El DEM de 930 m del curso suaviza el relieve y escalona el límite. A 30 m serían unos 40 millones de celdas sin cambio apreciable en el límite. |
| Relleno Priority-Flood + ε propio (Barnes et al., 2014) | El relleno de planos de pysheds cortaba el flujo en la planicie del Valle y dejaba la cuenca en ≈ 20 000 km². |
| Red de drenaje con umbral de 25 km² | Da una red legible (orden de Strahler 5) sin cauces espurios. |

**Verificación del cierre:**
- El punto queda a 178 m de la coordenada publicada de la presa.
- Incluye el río San Andrés, que desemboca 7 km aguas arriba, y excluye el río Ituango, que entra 0,5 km aguas abajo.
- El área (35 992 km²) difiere en 0,4 % de la de HydroSHEDS (35 841 km²).

La delimitación del equipo en QGIS (DEM de 930 m) dio 35 283 km² (−2 %).

## 3. Precipitación (IDEAM)

| Decisión | Justificación |
|---|---|
| 266 estaciones: 259 dentro de la cuenca o a menos de 20 km, y 7 de la zona hidrográfica 26 | Cubren los bordes sin traer estaciones de otras vertientes (Pacífico y Magdalena), que tienen otro régimen. |
| Se excluyó Briceño (6455 mm/año) | Duplica a sus vecinas y crea un núcleo de lluvia que ninguna otra estación respalda. |
| Kriging ordinario con variograma gaussiano | Menor RMSE en la validación cruzada (363 mm frente a 364–377 de IDW), y además da la varianza de estimación. |
| Variograma ajustado con los pesos de Cressie (1985) | El ajuste sin pesos daba pepita nula. |
| Sin deriva por elevación | La relación P–Z es débil: r = 0,18 (Pearson) y ρ = 0,30 (Spearman). |
| Sensibilidad con las 358 estaciones del vecindario | La media casi no cambia (+0,4 %), pero el RMSE sube a 560 mm. |

## 4–5. Temperatura

| Decisión | Justificación |
|---|---|
| Las mismas 47 estaciones para Tmax, Tmin y Tmed | Las ecuaciones son comparables y la amplitud Tmax − Tmin es coherente. |
| Una sola regresión para toda la cuenca; atípicos (residuo estudentizado mayor de 2,5) marcados pero conservados | R² > 0,96; con 47 estaciones no hay soporte para regresiones por subregión. |
| 12 regresiones mensuales para la ETP | Hargreaves se calcula mes a mes. |

**Resultados:**
- Gradientes de 7,28 (Tmax), 6,40 (Tmed) y 5,65 °C/km (Tmin).
- La amplitud diaria se reduce con la altura.
- No hay inversión térmica persistente en las medias anuales. Bajo 1000 m, la Tmax queda 0,4 °C sobre la recta y la Tmin 0,2 °C
  bajo ella, lo que indica un efecto de valle.

## 6–7. Evapotranspiración

| Decisión | Justificación |
|---|---|
| Hargreaves-Samani mensual, celda a celda, con Ra por latitud y día juliano representativo | Es el método del enunciado (Anexos 2 y 3). |
| ETP sin escalar al IDEAM | Hargreaves sobrestima en 22 % frente al IDEAM (r = 0,92). Al escalarla (× 0,822), el error del cierre empeora a +9,3 %. |
| Budyko aplicado celda a celda | La curva no es lineal: con el φ medio, la escorrentía es 4 % menor y el error llega a −9,2 %. |

## 8. Caudales

| Decisión | Justificación |
|---|---|
| Mes válido con al menos 80 % de días; año válido con 12 meses; al menos 15 años válidos en 1981–2010 | Criterio del enunciado, aplicado al mismo periodo de P y T. |
| Dato faltante = fecha ausente | Se verificó que no hay ceros ni negativos usados como código de faltante. |
| Cierre con Puerto Valdivia transferido por áreas (1084 m³/s) | No hay estación validada en la presa: Puente Pescadero y Olaya tienen solo 10 años completos. |
| La Pintada ubicada aguas arriba del río Arma | Entre Irra y La Pintada el caudal solo sube 26 m³/s, menos de lo que aporta el Arma. |
| Relleno en un libro aparte | Regresión log-lineal entre estaciones con corrección de Duan. Validación dejando un año fuera: NSE de 0,80 a 0,98. Las medias cambian 2 % o menos. |

## 9. Balance

- El error va de −7 % a +7 % en nueve estaciones y es de −5,3 % en el cierre (+0,6 % con el caudal rellenado).
- El signo del error depende de la zona:
  - En el alto Cauca y el Valle el balance sobrestima, porque el caudal observado está reducido por Salvajina y el riego.
  - En La Virginia e Irra subestima, posiblemente por falta de estaciones en alta montaña.

## 10–12. Productos de precipitación

| Decisión | Justificación |
|---|---|
| CHIRPS v2.0 (IRI Data Library) como producto principal | Es la versión publicada y más citada. El archivo del curso era la v3.0, que se evaluó como sensibilidad (+11 % de P, +14 % de error en el cierre). |
| Productos llevados a 90 m por vecino más cercano | Para no suavizar su resolución original. |
| Verificación de la lectura con lugares de referencia | En Quibdó ERA5 da 8081 mm/año y en Manizales 15 164 mm/año, lo que descarta un error de unidades. |
| «P necesaria» por inversión de Budyko (método de Brent) | Separa el error de la lluvia del de la ETP y la curva. IDEAM y CHIRPS necesitarían una corrección de −5 % a +4 %; ERA5, de −47 % a −74 %. |

ERA5 y ERA5-Land dan hasta 20 000 mm/año. Es una vez y media lo de Lloró (13 473 mm/año, Poveda y Mesa, 2000), el sitio más
lluvioso del país. Ver [`CORRECCION_SESGO_ERA5.md`](CORRECCION_SESGO_ERA5.md).

## 13–14. Ciclo anual

- **Climatología:** kriging mensual con un variograma por mes.
- **Clasificación de los meses:** un mes es húmedo si su lluvia supera la media mensual de la cuenca (166 mm).
- **Estacionalidad:** índice de Walsh y Lawler, de 0,17 a 0,42.
- **Comparación entre productos:** sesgo, RMSE, correlación (n = 12) y diagrama de Taylor.

## Análisis adicionales

| Análisis | ¿Aplicado? | Resultado o razón |
|---|---|---|
| Relleno log-lineal con corrección de Duan | Sí | NSE de 0,80 a 0,98 |
| Validación cruzada (estación fuera y año fuera) | Sí | Elección del interpolador y verificación del relleno |
| Correlaciones de Pearson y de Spearman | Sí | Relaciones T–Z y P–Z, correlación espacial y ciclos |
| Intervalos de confianza del 95 % y residuos estudentizados | Sí | Gradientes T–Z |
| Índice de estacionalidad de Walsh y Lawler | Sí | De 0,17 a 0,42 |
| Diagrama de Taylor | Sí | Comparación de ciclos |
| Compuestos ENSO y elasticidad de Budyko | Sí | Amplificación de ≈ 2,6 frente a 1,9 teórica |
| Sensibilidades | Sí | Método de P, red de estaciones, ETP, Budyko agregado, CHIRPS v3, caudal rellenado |
| Escalamiento lineal de ERA5 (prueba posterior) | Sí | Corrige la media, no la variabilidad interanual |
| EOF/ACP, análisis espectral singular, Fourier, ondículas | No | Se trabaja con climatologías de 30 años; el ENSO se evaluó con compuestos |
| Correlación no lineal, regresión logística, KNN | No | Spearman bastó para P–Z; no hay variable binaria; el relleno ya tenía NSE ≥ 0,80 |
| Mapeo de cuantiles | No | El enunciado pide evaluar los productos sin corregir |

## Lecciones y problemas resueltos

- **pysheds 0.5** necesita el alias `np.in1d = np.isin` con numpy 2. Su `resolve_flats` falla en planicies extensas; por eso se
  implementó Priority-Flood + ε.
- **Catálogo de estaciones (datos.gov.co):** el campo `ubicaci_n` trae la latitud y la longitud intercambiadas. Hay que usar los
  campos `latitud` y `longitud`.
- **Caudales del IDEAM:** el dato faltante es la ausencia de la fecha, no un 0 ni un −999.
- **CHIRPS v3.0** trae valores de relleno negativos sobre el mar; hay que filtrarlos antes de promediar.
- **CHIRPS v2.0 de la IRI** usa el tiempo en «meses desde 1960» con calendario de 360 días.
- **Mapas:** cada variable usa una escala de color fija por valor (`escalas.py`), con la barra cortada en el máximo de cada mapa.
  Las figuras del informe se redibujaron con letra de tamaño de impresión, a resolución completa.
