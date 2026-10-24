"""
Extensión del Trabajo 1 · paso 2: simulación de la operación del embalse de Hidroituango con pywr (planeación energética).

Aportes: serie diaria 1981–2010 a la presa (33_aportes_presa_diarios.py; media 1041 m³/s).
Datos técnicos (verificados en las fuentes originales):
  · volumen total 2720 hm³; útil 900 hm³ entre las cotas 390 y 420 m s.n.m.; vertedero en la cota 403 (EPM, PGRD 2024, Tabla 5 y p.185)
  · 8 turbinas Francis: 168,8 m³/s y 306,8 MW cada una, salto neto de diseño 197,3 m; 1350 m³/s en total (ANLA, Res. 155/2009)
  · caudal mínimo aguas abajo: 450 m³/s (vigente según EPM y BID) y 300 m³/s (licencia 2009) como sensibilidad
Supuestos (no publicados): curva cota–volumen lineal en el volumen útil; volumen muerto = 2720 − 900 = 1820 hm³; salto neto = 197,3 m
con el embalse en la cota media útil (405) y variando con la cota; eficiencia global 0,918 (= 300 MW del generador / ρ·g·168,8·197,3).

Regla de operación (curva guía): con el volumen útil por encima del 50 %, turbinas a plena capacidad; por debajo, sólo el caudal
mínimo, para recuperar nivel. El vertedero se usa sólo con el embalse lleno. Escenarios: 4 y 8 unidades × caudal mínimo 450 y 300.

Se ejecuta con el entorno trabajo1/.venv_pywr. Salidas: resultados/18_pywr/
"""
from pathlib import Path

import numpy as np
import pandas as pd
from pywr.model import Model
from pywr.nodes import Catchment, Link, Output, Storage
from pywr.parameters import ArrayIndexedParameter, ControlCurveParameter
from pywr.recorders import NumpyArrayNodeRecorder, NumpyArrayStorageRecorder

OUT = Path(__file__).resolve().parents[1] / "resultados" / "18_pywr"
D = 86400 / 1e6                                  # m³/s → hm³/día
V_UTIL, V_MUERTO, COTA_MIN, COTA_MAX = 900.0, 1820.0, 390.0, 420.0
Q_UNIDAD, P_UNIDAD, H_DIS = 168.8, 300.0, 197.3          # potencia del generador (8 × 300 = 2400 MW)
ETA = P_UNIDAD * 1e6 / (1000 * 9.81 * Q_UNIDAD * H_DIS)   # eficiencia global turbina–generador ≈ 0,918
CURVA = 0.5

q = pd.read_csv(OUT / "aportes_presa_diarios_1981_2010.csv", index_col=0, parse_dates=True)["Q_presa_m3s"]


def cota(v_util):
    return COTA_MIN + (COTA_MAX - COTA_MIN) * np.clip(v_util, 0, V_UTIL) / V_UTIL


def simular(n_unid, q_min):
    m = Model(start=q.index[0], end=q.index[-1])
    aporte = Catchment(m, "aporte", flow=ArrayIndexedParameter(m, (q * D).values))
    emb = Storage(m, "embalse", max_volume=V_UTIL, min_volume=0.0, initial_volume=V_UTIL, initial_volume_pc=1.0, cost=-1.0)
    q_turb_max = n_unid * Q_UNIDAD
    turb = Link(m, "turbinas", cost=-100.0,
                max_flow=ControlCurveParameter(m, emb, [CURVA], [q_turb_max * D, min(q_min, q_turb_max) * D]))
    vert = Link(m, "vertedero", cost=50.0)                           # sólo se usa cuando el embalse está lleno
    rio = Output(m, "cauca_aguas_abajo")
    aporte.connect(emb); emb.connect(turb); emb.connect(vert); turb.connect(rio); vert.connect(rio)
    r_t, r_v, r_s = NumpyArrayNodeRecorder(m, turb), NumpyArrayNodeRecorder(m, vert), NumpyArrayStorageRecorder(m, emb)
    m.run()
    qt, qv = r_t.data[:, 0] / D, r_v.data[:, 0] / D
    vol = r_s.data[:, 0]
    c = cota(vol)
    h = H_DIS + (c - (COTA_MIN + COTA_MAX) / 2)
    p = np.minimum(ETA * 1000 * 9.81 * h * qt / 1e6, n_unid * P_UNIDAD)       # MW, con tope en la potencia instalada
    return pd.DataFrame({"Q_aporte": q.values, "Q_turbinado": qt, "Q_vertido": qv, "Q_rio": qt + qv, "V_util_hm3": vol,
                         "cota_msnm": c, "salto_m": h, "potencia_MW": p}, index=q.index)


ESC = {"8 unidades · Qmín 450": (8, 450), "8 unidades · Qmín 300": (8, 300), "4 unidades · Qmín 450": (4, 450),
       "4 unidades · Qmín 300": (4, 300)}
res, anual = [], {}
for nom, (n, qm) in ESC.items():
    s = simular(n, qm)
    s.to_csv(OUT / f"sim_{n}u_qmin{qm}.csv", encoding="utf-8-sig")
    ea = (s.potencia_MW * 24 / 1000).groupby(s.index.year).sum()          # GWh/año
    anual[nom] = ea
    mens = (s.potencia_MW * 24 / 1000).resample("MS").sum()
    res.append({"escenario": nom, "unidades": n, "Q mínimo (m³/s)": qm, "Potencia instalada (MW)": n * P_UNIDAD,
                "Energía media (GWh/año)": ea.mean(), "Energía año más seco (GWh/año)": ea.min(),
                "Año más seco": int(ea.idxmin()), "Energía anual excedida 95 % (GWh/año)": ea.quantile(0.05),
                "Factor de planta (%)": 100 * s.potencia_MW.mean() / (n * P_UNIDAD),
                "Caudal turbinado medio (m³/s)": s.Q_turbinado.mean(), "Caudal vertido medio (m³/s)": s.Q_vertido.mean(),
                "Agua vertida (% del aporte)": 100 * s.Q_vertido.sum() / s.Q_aporte.sum(),
                "Días con caudal al río < Qmín (%)": 100 * (s.Q_rio < qm - 0.5).mean(),
                "Cota media (m s.n.m.)": s.cota_msnm.mean(), "Días bajo la curva guía (%)": 100 * (s.V_util_hm3 < CURVA * V_UTIL).mean(),
                "Energía mensual mínima (GWh/mes)": mens.min()})
res = pd.DataFrame(res).set_index("escenario")
res.round(2).to_csv(OUT / "resumen_escenarios.csv", encoding="utf-8-sig")
pd.DataFrame(anual).round(1).to_csv(OUT / "energia_anual.csv", encoding="utf-8-sig")

# energía en años ENSO (mismos años del punto 8)
NINO, NINA = [1983, 1987, 1992, 1998, 2003, 2010], [1989, 1999, 2000, 2008, 2011]
an = pd.DataFrame(anual)
enso = pd.DataFrame({"El Niño (% vs media)": 100 * (an.loc[an.index.isin(NINO)].mean() / an.mean() - 1),
                     "La Niña (% vs media)": 100 * (an.loc[an.index.isin(NINA)].mean() / an.mean() - 1)})
enso.round(1).to_csv(OUT / "energia_enso.csv", encoding="utf-8-sig")
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
print(res.round(1).T.to_string()); print(); print(enso.round(1).to_string())
