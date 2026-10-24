"""
Extensión del Trabajo 1 (pywr) · paso 1: serie diaria de aportes al embalse de Hidroituango, 1981–2010.

Mismo criterio del cierre del punto 8: Puerto Valdivia (26237040, 37 267 km², ~35 km aguas abajo) transferido por relación de
áreas a la presa (35 992 km²). Los días sin dato se rellenan con Cañafisto (26217050, 32 704 km²) por regresión log-lineal diaria con
el rezago de mejor ajuste y factor de Duan (como el relleno mensual del punto 8). Se valida dejando años fuera.

Salidas: resultados/18_pywr/aportes_presa_diarios_1981_2010.csv, resumen_aportes.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
QD = ROOT / "datos" / "caudales_ideam" / "q_media_diaria"
OUT = ROOT / "resultados" / "18_pywr"
OUT.mkdir(parents=True, exist_ok=True)
A_PRESA, A_PV = 35991.8, 37267.0
IDX = pd.date_range("1981-01-01", "2010-12-31")


def lee(c):
    d = pd.read_csv(QD / f"Q_MEDIA_D@{c}.data", sep="|")
    d.index = pd.DatetimeIndex(pd.to_datetime(d.Fecha)).normalize()
    return d.Valor.astype(float).groupby(level=0).mean()


pv, ca = lee("26237040").reindex(IDX), lee("26217050")
# rezago de mejor correlación (Cañafisto está aguas arriba)
r_lag = {k: np.corrcoef(*pd.concat([np.log(pv), np.log(ca.shift(k).reindex(IDX))], axis=1).dropna().T.values)[0, 1] for k in range(0, 4)}
lag = max(r_lag, key=r_lag.get)
x = np.log(ca.shift(lag).reindex(IDX))
ok = pv.notna() & x.notna()


def ajuste(m):
    b, a = np.polyfit(x[m], np.log(pv[m]), 1)
    duan = np.mean(np.exp(np.log(pv[m]) - (a + b * x[m])))
    return a, b, duan


a, b, duan = ajuste(ok)
# validación dejando un año fuera
pred, obs = [], []
for y in range(1981, 2011):
    m = ok & (IDX.year != y); t = ok & (IDX.year == y)
    if t.sum() < 30:
        continue
    aa, bb, dd = ajuste(m)
    pred.append(np.exp(aa + bb * x[t]) * dd); obs.append(pv[t])
pred, obs = pd.concat(pred), pd.concat(obs)
nse = 1 - ((pred - obs) ** 2).sum() / ((obs - obs.mean()) ** 2).sum()

relleno = np.exp(a + b * x) * duan
q_pv = pv.fillna(relleno)
q = q_pv * A_PRESA / A_PV
fuente = np.where(pv.notna(), "Puerto Valdivia", np.where(relleno.notna(), "Cañafisto (relleno)", "sin dato"))
falt = q.isna()
q = q.interpolate(limit=5)                                    # huecos de pocos días sin ninguna de las dos estaciones
df = pd.DataFrame({"Q_presa_m3s": q.round(2), "fuente": fuente}, index=IDX); df.index.name = "fecha"
df.loc[falt & q.notna(), "fuente"] = "interpolado"
df.to_csv(OUT / "aportes_presa_diarios_1981_2010.csv", encoding="utf-8-sig")

res = pd.Series({"rezago Cañafisto → Pto. Valdivia (días)": lag, "r(ln Q) con ese rezago": r_lag[lag],
                 "regresión": f"ln Q_PV = {a:.3f} + {b:.4f}·ln Q_Cañafisto(t−{lag})", "factor de Duan": duan,
                 "NSE validación (año fuera)": nse, "días observados (%)": 100 * pv.notna().mean(),
                 "días rellenados con Cañafisto (%)": 100 * (df.fuente == "Cañafisto (relleno)").mean(),
                 "días interpolados": int((df.fuente == "interpolado").sum()), "días sin dato": int(df.Q_presa_m3s.isna().sum()),
                 "Q medio presa 1981–2010 (m³/s)": q.mean(), "Q medio presa sólo días observados (m³/s)": (pv * A_PRESA / A_PV).mean(),
                 "Q mínimo diario (m³/s)": q.min(), "Q máximo diario (m³/s)": q.max(),
                 "Q95 (excedido 95 % del tiempo, m³/s)": q.quantile(0.05)})
res.to_csv(OUT / "resumen_aportes.csv", encoding="utf-8-sig", header=["valor"])
print(res.to_string())
