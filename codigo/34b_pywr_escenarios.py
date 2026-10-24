"""
Extensión pywr · escenarios adicionales (central completa, 8 unidades), con el mismo modelo de 34_pywr_hidroituango.py:
  A. Sensibilidad climática: aportes diarios escalados ×0.8, ×0.9, ×1.1, ×1.2 (caudal mínimo 450 m³/s).
  B. Compromiso generación–caudal ambiental: caudal mínimo de 0 a 800 m³/s (aportes observados).
  C. Fuentes de caudal: aportes escalados por Q_est(producto)/Q_obs en el cierre (punto 12 y mapeo de cuantiles), es decir, el
     caudal que un planificador habría supuesto con cada fuente de precipitación. Conserva la secuencia observada: sólo mide el
     efecto del sesgo de cada fuente sobre la energía planificada.
Energía firme: energía anual excedida el 95 % de los años (percentil 5) y la del año más seco; se compara con la ENFICC verificada
(4467.6 GWh/año para 2 unidades, Superservicios 2021).

Se ejecuta con trabajo1/.venv_pywr. Salidas: resultados/18_pywr/escenarios_*.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

src = (Path(__file__).parent / "34_pywr_hidroituango.py").read_text(encoding="utf-8")
exec(compile(src.split("ESC = {")[0], "34_base", "exec"))
q_obs = q.copy()


def metricas(s, etiqueta, **extra):
    ea = (s.potencia_MW * 24 / 1000).groupby(s.index.year).sum()
    mens = (s.potencia_MW * 24 / 1000).resample("MS").sum()
    return {"escenario": etiqueta, **extra, "Energía media (GWh/año)": ea.mean(), "Energía firme 95 % (GWh/año)": ea.quantile(0.05),
            "Energía año más seco (GWh/año)": ea.min(), "Energía mes más seco (GWh/mes)": mens.min(),
            "Agua vertida (% del aporte)": 100 * s.Q_vertido.sum() / s.Q_aporte.sum(),
            "Días bajo la curva guía (%)": 100 * (s.V_util_hm3 < CURVA * V_UTIL).mean(), "Cota media (m s.n.m.)": s.cota_msnm.mean()}


def correr(factor, qmin):
    global q
    q = q_obs * factor
    try:
        return simular(8, qmin)
    finally:
        q = q_obs


A = [metricas(correr(f, 450), f"Aportes {100 * (f - 1):+.0f} %", factor=f) for f in [0.8, 0.9, 1.0, 1.1, 1.2]]
pd.DataFrame(A).round(2).to_csv(OUT / "escenarios_clima.csv", index=False, encoding="utf-8-sig")
B = [metricas(correr(1.0, qm), f"Qmín {qm}", q_min=qm) for qm in [0, 150, 300, 450, 600, 700, 800]]
pd.DataFrame(B).round(2).to_csv(OUT / "escenarios_qmin.csv", index=False, encoding="utf-8-sig")

bp = pd.read_csv(OUT.parent / "12_balance_productos" / "balance_productos.csv", dtype={"codigo": str})
h = bp[bp.codigo == "HIDRO"].set_index("producto")
bq = pd.read_csv(OUT.parent / "17_quantile_mapping" / "balance_qm.csv", dtype={"codigo": str})
hq = bq[bq.codigo == "HIDRO"].set_index("campo")
FU = {"Observado (IDEAM)": 1.0, "Balance IDEAM": h.loc["IDEAM", "Qest"] / h.loc["IDEAM", "Qobs"],
      "Balance CHIRPS v2.0": h.loc["CHIRPS", "Qest"] / h.loc["CHIRPS", "Qobs"],
      "Balance ERA5-Land corregido (QM)": hq.loc["ERA5-Land con mapeo de cuantiles", "Q_est"] / hq.loc["ERA5-Land con mapeo de cuantiles", "Q_obs"],
      "Balance ERA5 corregido (QM)": hq.loc["ERA5 con mapeo de cuantiles", "Q_est"] / hq.loc["ERA5 con mapeo de cuantiles", "Q_obs"],
      "Balance ERA5-Land sin corregir": h.loc["ERA5-Land", "Qest"] / h.loc["ERA5-Land", "Qobs"],
      "Balance ERA5 sin corregir": h.loc["ERA5", "Qest"] / h.loc["ERA5", "Qobs"]}
C = [metricas(correr(f, 450), k, factor=f, Q_medio=q_obs.mean() * f) for k, f in FU.items()]
pd.DataFrame(C).round(3).to_csv(OUT / "escenarios_fuentes.csv", index=False, encoding="utf-8-sig")
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 20)
for n, x in [("CLIMA", A), ("QMIN", B), ("FUENTES", C)]:
    print("==", n); print(pd.DataFrame(x).round(1).to_string(index=False))

# D. Comparación con la ENFICC verificada (2 unidades; Superservicios 2021)
s2 = simular(2, 450)
D_ = pd.DataFrame([metricas(s2, "2 unidades · Qmín 450", unidades=2)])
D_["ENFICC verificada (GWh/año)"] = 4467.6
D_.round(1).to_csv(OUT / "escenario_2u_enficc.csv", index=False, encoding="utf-8-sig")
print("== 2 UNIDADES"); print(D_.round(1).to_string(index=False))
