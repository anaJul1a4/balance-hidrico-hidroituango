"""
Extensión · pronóstico de caudales · paso 3: horizonte de pronóstico (1–30 días) y KNN (método de análogos).

Mismas entradas, periodos y objetivo de 37_pronostico_caudales.py (aporte diario a la presa). Para cada anticipación h:
  · Persistencia, climatología (día del año) y Ridge (alfa elegido en validación).
  · KNN: los k días de entrenamiento más parecidos al de hoy (distancia euclidiana en las entradas estandarizadas, reducidas por
    PCA al 95 % de la varianza); pronóstico = mediana de lo que ocurrió h días después de esos análogos; k elegido en validación.
    Los análogos dan además un intervalo del 80 % (percentiles 10 y 90), cuya cobertura se evalúa en prueba.
Métricas en prueba 2006–2010: NSE, habilidad frente a persistencia y frente a climatología, cobertura y ancho del intervalo.

Se ejecuta con trabajo1/.venv_ml. Salida: resultados/19_pronostico/horizonte.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.neighbors import NearestNeighbors

src = (Path(__file__).parent / "37_pronostico_caudales.py").read_text(encoding="utf-8")
base = src.split("# muestras:")[0]
exec(compile(base, "37_base", "exec"))                        # lee datos, relleno, estandarización (Z, M, doy, Q, IDX, ...)

H = [1, 2, 3, 5, 7, 10, 15, 20, 30]
Tn = len(IDX)
ts = np.arange(LAGS - 1, Tn - max(H))
X = np.concatenate([np.concatenate([Z[ts - k] for k in range(LAGS)], 1), np.concatenate([M[ts - k] for k in range(LAGS)], 1),
                    doy[ts]], 1)
qp = Q["PRESA"].values
iE, iV, iP = ent[ts], val[ts], pru[ts]
fechas = IDX[ts]
cq = pd.Series(qp, index=IDX)[ent].groupby(IDX[ent].dayofyear).mean()
pca = PCA(0.95).fit(X[iE]); Xp = pca.transform(X)


def nse(s, o):
    return 1 - np.sum((s - o) ** 2) / np.sum((o - o.mean()) ** 2)


filas = []
for h in H:
    y = qp[ts + h]; yl = np.log1p(y)
    obs = y[iP]
    per = qp[ts][iP]
    cli = cq.reindex((fechas[iP] + pd.Timedelta(days=h)).dayofyear).values
    # ridge
    mejor = min(((np.mean((Ridge(alpha=a).fit(X[iE], yl[iE]).predict(X[iV]) - yl[iV]) ** 2), a) for a in [1, 10, 100, 1000]))
    rid = np.expm1(Ridge(alpha=mejor[1]).fit(X[iE | iV], yl[iE | iV]).predict(X[iP]))
    # knn (análogos)
    nn_e = NearestNeighbors().fit(Xp[iE])
    def knn(k, consulta, base_idx=np.where(iE)[0], nn=nn_e):
        _, ind = nn.kneighbors(consulta, n_neighbors=k)
        vec = yl[base_idx][ind]
        return np.expm1(np.median(vec, 1)), np.expm1(np.percentile(vec, 10, 1)), np.expm1(np.percentile(vec, 90, 1))
    ks = [5, 10, 20, 40, 80]
    kbest = min(ks, key=lambda k: np.mean((np.log1p(knn(k, Xp[iV])[0]) - yl[iV]) ** 2))
    base_idx = np.where(iE | iV)[0]
    nn_ev = NearestNeighbors().fit(Xp[base_idx])
    kn, k10, k90 = knn(kbest, Xp[iP], base_idx, nn_ev)
    for nom, s in [("Persistencia", per), ("Climatología", cli), ("Ridge (lineal)", rid), (f"KNN (análogos)", kn)]:
        f = {"anticipación (días)": h, "modelo": nom, "NSE": nse(s, obs),
             "Habilidad vs persistencia": 1 - np.mean((s - obs) ** 2) / np.mean((per - obs) ** 2),
             "Habilidad vs climatología": 1 - np.mean((s - obs) ** 2) / np.mean((cli - obs) ** 2),
             "RMSE (m³/s)": np.sqrt(np.mean((s - obs) ** 2))}
        if nom.startswith("KNN"):
            f.update({"k": kbest, "Cobertura intervalo 80 % (%)": 100 * np.mean((obs >= k10) & (obs <= k90)),
                      "Ancho medio intervalo 80 % (m³/s)": np.mean(k90 - k10)})
        filas.append(f)
    print(f"h={h:2d} listo (k={kbest})", flush=True)
r = pd.DataFrame(filas)
r.round(4).to_csv(OUT / "horizonte.csv", index=False, encoding="utf-8-sig")
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 20)
print(r.round(3).to_string(index=False))
