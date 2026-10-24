"""
Figura 22 del informe: ciclo anual de la cuenca con ERA5 y ERA5-Land sin corregir (a) y corregidos por mapeo de cuantiles (b),
frente al IDEAM y CHIRPS v2.0. Misma composición y colores que la gráfica de la página (pestaña 14), dibujada al ancho de página
(16 cm) con letra de tamaño de impresión.

Entrada: resultados/17_quantile_mapping/ciclos_qm.csv · Salida: ~/Downloads/Figura 22 - ciclo anual antes y despues del mapeo de cuantiles.png
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

RES = Path(__file__).resolve().parents[1] / "resultados"
c = pd.read_csv(RES / "17_quantile_mapping" / "ciclos_qm.csv", index_col=0)
SAL = [RES / "informe_figs" / "ciclo_qm.png", Path.home() / "Downloads" / "Figura 22 - ciclo anual antes y despues del mapeo de cuantiles.png"]
plt.rcParams.update({"font.size": 7, "axes.labelsize": 7, "xtick.labelsize": 6.5, "ytick.labelsize": 6.5, "legend.fontsize": 7,
                     "axes.linewidth": 0.6, "font.family": "DejaVu Sans"})
COL = {"IDEAM": "#1a1a1a", "CHIRPS": "#2a78d6", "ERA5-Land": "#eb6834", "ERA5": "#1baf7a"}
fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.3, 2.75), gridspec_kw=dict(wspace=0.18))
for ax, suf, tit in [(a1, "sin corregir", "a) Sin corregir"), (a2, "corregido", "b) Con mapeo de cuantiles")]:
    for k, col in COL.items():
        y = c[k] if k in ("IDEAM", "CHIRPS") else c[f"{k} {suf}"]
        ax.plot(range(12), y, color=col, lw=1.8 if k == "IDEAM" else 1.2, marker="o", ms=2.8, mec="white", mew=0.4, label=k,
                zorder=3 if k == "IDEAM" else 2)
    ax.set_xticks(range(12)); ax.set_xticklabels(["E", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    ax.set_ylim(0); ax.grid(color="0.9", lw=0.5); ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.set_title(tit, loc="left", fontsize=8, fontweight="bold", pad=4)
a1.set_ylabel("Precipitación media mensual (mm)")
h, l = a1.get_legend_handles_labels()
fig.legend(h, l, loc="upper left", bbox_to_anchor=(0.07, 1.06), ncol=4, frameon=False, handlelength=2.2)
for s in SAL:
    fig.savefig(s, dpi=600, bbox_inches="tight", pad_inches=0.04)
print("\n".join(map(str, SAL)))
