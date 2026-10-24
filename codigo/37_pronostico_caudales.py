"""
Extensión · pronóstico de caudales · paso 2: aporte diario a la presa de Hidroituango a 1, 3 y 7 días.

Entradas (en el día t): caudal de los 7 días anteriores (t−6 … t) en las 53 estaciones del grafo (36_grafo_estaciones.py) y en la
presa, en ln(1 + Q), estandarizado por estación; día del año (seno, coseno). Faltantes: interpolación de hasta 5 días y, si no,
climatología diaria de la estación, con una máscara que indica el dato rellenado.
Objetivo: ln(1 + Q_presa) en t+1, t+3 y t+7 (aporte de 33_aportes_presa_diarios.py).
Periodos: entrenamiento 1981–2000, validación 2001–2005 (parada temprana y elección de alfa), prueba 2006–2010 (sólo para evaluar).

Modelos:
  · Persistencia: Q(t+h) = Q(t).            · Climatología: media del día del año en entrenamiento.
  · Ridge: regresión lineal regularizada con todas las entradas.
  · MLP: red neuronal densa con las mismas entradas (sin estructura de grafo).
  · GNN: red de grafos con paso de mensajes dirigido aguas abajo (3 capas); la predicción sale del nodo de la presa.
MLP y GNN se entrenan con 5 semillas; se reporta la media y el rango.
Métricas en prueba (m³/s): NSE, KGE, RMSE, sesgo y habilidad frente a la persistencia (1 − MSE/MSE_persistencia).

Se ejecuta con trabajo1/.venv_ml. Salidas: resultados/19_pronostico/
"""
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.linear_model import Ridge

ROOT = Path(__file__).resolve().parents[1]
QD = ROOT / "datos" / "caudales_ideam" / "q_media_diaria"
OUT = ROOT / "resultados" / "19_pronostico"
LAGS, LEADS, SEMILLAS = 7, [1, 3, 7], [0, 1, 2, 3, 4]
IDX = pd.date_range("1981-01-01", "2010-12-31")
torch.set_num_threads(4)

nodos = pd.read_csv(OUT / "nodos.csv", dtype={"codigo": str, "destino": str})
codigos = nodos.codigo.tolist()
NOMBRES = codigos + ["PRESA"]
P = len(NOMBRES) - 1


def lee(c):
    d = pd.read_csv(QD / f"Q_MEDIA_D@{c}.data", sep="|")
    d.index = pd.DatetimeIndex(pd.to_datetime(d.Fecha)).normalize()
    return d.Valor.astype(float).groupby(level=0).mean().reindex(IDX)


Q = pd.DataFrame({c: lee(c) for c in codigos})
Q["PRESA"] = pd.read_csv(ROOT / "resultados" / "18_pywr" / "aportes_presa_diarios_1981_2010.csv", index_col=0, parse_dates=True)["Q_presa_m3s"]
ent = IDX.year <= 2000
val = (IDX.year >= 2001) & (IDX.year <= 2005)
pru = IDX.year >= 2006

# relleno de entradas y máscara
L = np.log1p(Q.clip(lower=0))
mask = L.isna().astype(float)
L = L.interpolate(limit=5, limit_area="inside")
clim = L[ent].groupby(L[ent].index.dayofyear).mean()
for c in L.columns:
    falta = L[c].isna()
    L.loc[falta, c] = clim[c].reindex(L.index.dayofyear[falta]).values
L = L.fillna(L[ent].mean())
mu, sd = L[ent].mean(), L[ent].std().replace(0, 1)
Z = ((L - mu) / sd).values.astype("float32")                     # (T, N)
M = mask.values.astype("float32")
doy = np.c_[np.sin(2 * np.pi * IDX.dayofyear / 365.25), np.cos(2 * np.pi * IDX.dayofyear / 365.25)].astype("float32")

# muestras: t con historia completa y objetivo t+7 dentro de 1981–2010
T = len(IDX)
ts = np.arange(LAGS - 1, T - max(LEADS))
Xn = np.stack([Z[ts - k] for k in range(LAGS)], axis=-1)          # (S, N, LAGS)
Xm = np.stack([M[ts - k] for k in range(LAGS)], axis=-1)
Xnode = np.concatenate([Xn, Xm], axis=-1)                           # (S, N, 2·LAGS)
Xdoy = doy[ts]
yl = np.stack([np.log1p(Q["PRESA"].values[ts + h]) for h in LEADS], axis=1).astype("float32")
ymu, ysd = yl[ent[ts]].mean(0), yl[ent[ts]].std(0)
Y = (yl - ymu) / ysd
q_obs = np.stack([Q["PRESA"].values[ts + h] for h in LEADS], axis=1)
q_hoy = Q["PRESA"].values[ts]
fechas = IDX[ts]
iE, iV, iP = ent[ts], val[ts], pru[ts]
print(f"muestras: entrenamiento {iE.sum()}, validación {iV.sum()}, prueba {iP.sum()} · nodos {P} + presa")


def a_q(yz):
    return np.expm1(yz * ysd + ymu)


def metr(sim, obs, ref=None):
    nse = 1 - np.sum((sim - obs) ** 2) / np.sum((obs - obs.mean()) ** 2)
    r = np.corrcoef(sim, obs)[0, 1]; a = sim.std() / obs.std(); b = sim.mean() / obs.mean()
    kge = 1 - np.sqrt((r - 1) ** 2 + (a - 1) ** 2 + (b - 1) ** 2)
    out = {"NSE": nse, "KGE": kge, "RMSE (m³/s)": np.sqrt(np.mean((sim - obs) ** 2)), "Sesgo (%)": 100 * (b - 1)}
    if ref is not None:
        out["Habilidad vs persistencia"] = 1 - np.mean((sim - obs) ** 2) / np.mean((ref - obs) ** 2)
    return out


pred = {}
# persistencia y climatología
pred["Persistencia"] = np.repeat(q_hoy[:, None], len(LEADS), 1)
cq = pd.Series(Q["PRESA"].values, index=IDX)[ent].groupby(IDX[ent].dayofyear).mean()
pred["Climatología"] = np.stack([cq.reindex((fechas + pd.Timedelta(days=h)).dayofyear).values for h in LEADS], 1)

# ridge
Xflat = np.concatenate([Xnode.reshape(len(ts), -1), Xdoy], axis=1)
pr = np.zeros_like(Y)
alfas = {}
for j in range(len(LEADS)):
    mejor = None
    for a in [0.1, 1, 10, 100, 1000]:
        m = Ridge(alpha=a).fit(Xflat[iE], Y[iE, j])
        e = np.mean((m.predict(Xflat[iV]) - Y[iV, j]) ** 2)
        if mejor is None or e < mejor[0]:
            mejor = (e, a)
    alfas[LEADS[j]] = mejor[1]
    m = Ridge(alpha=mejor[1]).fit(Xflat[iE | iV], Y[iE | iV, j])
    pr[:, j] = m.predict(Xflat)
pred["Ridge (lineal)"] = a_q(pr)


# ----------------------------------------------------------------------------- redes neuronales
class MLP(nn.Module):
    def __init__(self, d, h=128):
        super().__init__()
        self.f = nn.Sequential(nn.Linear(d, h), nn.ReLU(), nn.Dropout(0.1), nn.Linear(h, h), nn.ReLU(), nn.Linear(h, len(LEADS)))

    def forward(self, xn, xd):
        return self.f(torch.cat([xn.flatten(1), xd], 1))


# grafo dirigido aguas abajo: A[destino, origen] = 1, normalizado por el número de afluentes
idx = {n: i for i, n in enumerate(NOMBRES)}
Adj = torch.zeros(len(NOMBRES), len(NOMBRES))
for n in nodos.itertuples():
    Adj[idx[n.destino], idx[n.codigo]] = 1.0
Adj = Adj / Adj.sum(1, keepdim=True).clamp(min=1)


class GNN(nn.Module):
    """Paso de mensajes aguas abajo: h_v ← ReLU(W_s h_v + W_a · media de h_u de los afluentes u). Tras K capas, la presa
    resume la información de toda la red aguas arriba (hasta K saltos), y una capa final da los pronósticos."""

    def __init__(self, d_in, h=32, capas=3):
        super().__init__()
        self.emb = nn.Linear(d_in, h)
        self.ws = nn.ModuleList([nn.Linear(h, h) for _ in range(capas)])
        self.wa = nn.ModuleList([nn.Linear(h, h, bias=False) for _ in range(capas)])
        self.salida = nn.Sequential(nn.Linear(h + 2, h), nn.ReLU(), nn.Linear(h, len(LEADS)))

    def forward(self, xn, xd):
        h = torch.relu(self.emb(xn))                                 # (B, N, h)
        for ws, wa in zip(self.ws, self.wa):
            h = torch.relu(ws(h) + wa(torch.einsum("ij,bjh->bih", Adj, h)))
        return self.salida(torch.cat([h[:, idx["PRESA"]], xd], 1))


def entrenar(modelo, semilla, max_ep=200, paciencia=15):
    torch.manual_seed(semilla); np.random.seed(semilla)
    xn, xd, y = torch.tensor(Xnode), torch.tensor(Xdoy), torch.tensor(Y)
    opt = torch.optim.Adam(modelo.parameters(), lr=1e-3, weight_decay=1e-5)
    tr = np.where(iE)[0]; mejor, sin_mejora, estado = np.inf, 0, None
    for ep in range(max_ep):
        modelo.train(); np.random.shuffle(tr)
        for k in range(0, len(tr), 128):
            b = tr[k:k + 128]
            opt.zero_grad(); loss = nn.functional.mse_loss(modelo(xn[b], xd[b]), y[b]); loss.backward(); opt.step()
        modelo.eval()
        with torch.no_grad():
            ev = nn.functional.mse_loss(modelo(xn[iV], xd[iV]), y[iV]).item()
        if ev < mejor - 1e-5:
            mejor, sin_mejora, estado = ev, 0, {k: v.clone() for k, v in modelo.state_dict().items()}
        else:
            sin_mejora += 1
            if sin_mejora >= paciencia:
                break
    modelo.load_state_dict(estado); modelo.eval()
    with torch.no_grad():
        return a_q(modelo(xn, xd).numpy()), ep + 1


por_semilla = {"MLP (sin grafo)": [], "GNN (grafo de la cuenca)": []}
for s in SEMILLAS:
    t0 = time.time()
    p_mlp, e1 = entrenar(MLP(Xnode.shape[1] * Xnode.shape[2] + 2), s)
    p_gnn, e2 = entrenar(GNN(Xnode.shape[2]), s)
    por_semilla["MLP (sin grafo)"].append(p_mlp); por_semilla["GNN (grafo de la cuenca)"].append(p_gnn)
    print(f"semilla {s}: MLP {e1} épocas, GNN {e2} épocas, {time.time() - t0:.0f} s")
for k, v in por_semilla.items():
    pred[k] = np.mean(v, axis=0)                                       # media del conjunto de semillas

# ----------------------------------------------------------------------------- evaluación en prueba (2006–2010)
filas = []
for j, h in enumerate(LEADS):
    obs = q_obs[iP, j]; ref = pred["Persistencia"][iP, j]
    for nom, p in pred.items():
        filas.append({"modelo": nom, "anticipación (días)": h, **metr(p[iP, j], obs, ref)})
    for nom, lista in por_semilla.items():                             # dispersión entre semillas
        nses = [metr(p[iP, j], obs)["NSE"] for p in lista]
        filas[-(len(pred)) + list(pred).index(nom)]["NSE min–max semillas"] = f"{min(nses):.3f}–{max(nses):.3f}"
met = pd.DataFrame(filas)
met.round(4).to_csv(OUT / "metricas_prueba.csv", index=False, encoding="utf-8-sig")
serie = pd.DataFrame({"fecha": fechas[iP]})
for j, h in enumerate(LEADS):
    serie[f"obs_t+{h}"] = q_obs[iP, j]
    for nom, p in pred.items():
        serie[f"{nom}_t+{h}"] = p[iP, j]
serie.round(1).to_csv(OUT / "series_prueba.csv", index=False, encoding="utf-8-sig")
pd.Series(alfas).to_csv(OUT / "ridge_alfas.csv", encoding="utf-8-sig")
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 20)
print(met.round(3).to_string(index=False))
