"""
Extensión pywr · figura para la página: cota del embalse y caudales diarios 1981–2010 con 8 y 4 unidades (caudal mínimo 450 m³/s).
Estilo de las figuras originales de la página. Salida: resultados/18_pywr/pywr_series.png
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "resultados" / "18_pywr"
s8 = pd.read_csv(OUT / "sim_8u_qmin450.csv", index_col=0, parse_dates=True)
s4 = pd.read_csv(OUT / "sim_4u_qmin450.csv", index_col=0, parse_dates=True)
fig, axs = plt.subplots(3, 1, figsize=(16, 11), sharex=True, gridspec_kw=dict(hspace=0.12, height_ratios=[1, 1.2, 1.2]))
ax = axs[0]
ax.plot(s8.index, s8.cota_msnm, color="#2a78d6", lw=0.8, label="8 unidades (2400 MW)")
ax.plot(s4.index, s4.cota_msnm, color="#eb6834", lw=0.8, label="4 unidades (1200 MW)")
ax.axhline(405, color="0.3", lw=0.8, ls="--"); ax.text(s8.index[200], 391, "línea punteada: curva guía, cota 405 (50 % del volumen útil)", fontsize=8.5, color="0.3")
ax.set_ylabel("Cota del embalse (m s.n.m.)"); ax.set_ylim(389, 421); ax.legend(loc="lower right", fontsize=9)
ax.set_title("Operación simulada del embalse de Hidroituango con pywr · caudales diarios 1981–2010 · caudal mínimo 450 m³/s",
             fontsize=11, fontweight="bold", loc="left")
for ax, s, tit in [(axs[1], s8, "8 unidades"), (axs[2], s4, "4 unidades")]:
    ax.plot(s.index, s.Q_aporte, color="0.55", lw=0.5, label="Aporte")
    ax.fill_between(s.index, 0, s.Q_turbinado, color="#2a78d6", alpha=0.55, lw=0, label="Turbinado")
    ax.fill_between(s.index, s.Q_turbinado, s.Q_turbinado + s.Q_vertido, color="#d7301f", alpha=0.6, lw=0, label="Vertido")
    ax.set_ylabel("Caudal (m³/s)"); ax.set_ylim(0, 5000); ax.legend(loc="upper left", fontsize=9, ncol=3)
    ax.text(0.995, 0.92, tit, transform=ax.transAxes, ha="right", fontsize=10, fontweight="bold")
for ax in axs:
    ax.grid(color="0.85", lw=0.5)
fig.savefig(OUT / "pywr_series.png", dpi=150, bbox_inches="tight"); plt.close(fig)
print("ok pywr_series.png")
