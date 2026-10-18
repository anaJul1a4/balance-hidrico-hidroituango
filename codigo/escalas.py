"""
Escalas de color por variable. Cada variable tiene una paleta y unas clases fijas: un mismo valor (p. ej. 1000 mm/año) tiene el
mismo tono en todos los mapas de esa variable. La barra de color de cada mapa se corta en la clase máxima de sus datos (no se
dibujan colores que el mapa no usa) y empieza siempre en 0 (blanco en ETP, ETR y R).

    P anual (mm/año)      naranja → amarillo → verde → azul pizarra (Balances 1999)   puntos 3, 11, 12 y CHIRPS v2/v3
    P mensual (mm/mes)    la misma paleta, clases en mm/mes                       punto 13
    ETP (mm/año)          blanco → amarillo → rojo (YlOrRd)                        punto 6
    ETR (mm/año)          blanco → verdes (YlGn), mismas clases que la ETP         punto 7
    R = P − ETR (mm/año)  blanco → verde-azul (GnBu)                               puntos 7 y 12
    T (°C)                RdYlBu_r, −6 a 36 °C (divergente, convención usual)      punto 5
"""
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.cm import ScalarMappable
from matplotlib.ticker import FuncFormatter
from matplotlib.colors import BoundaryNorm, LinearSegmentedColormap, ListedColormap


def _desde_blanco(cmap, n, gamma=1.0):
    """n colores de una paleta de matplotlib, el primero blanco. gamma < 1 da más contraste a las clases bajas."""
    c = plt.get_cmap(cmap)(0.15 + 0.85 * np.linspace(0, 1, n - 1) ** gamma)
    return ListedColormap(np.vstack([[1, 1, 1, 1], c]))


# precipitación: paleta de los mapas de "Balances hidrológicos de Colombia" (Mejía et al., 1999):
# naranja (seco) → amarillo → verde → azul pizarra (muy lluvioso)
_P_ANCLAS = ["#e8862a", "#f2a320", "#f5c81a", "#f2e51c", "#cfe027", "#a3cc37", "#73b046", "#5a9a55", "#5c7f62",
             "#5b6a6c", "#505872", "#45456e"]


def _balances(n):
    return ListedColormap(LinearSegmentedColormap.from_list("balances", _P_ANCLAS)(np.linspace(0, 1, n)))


def _esc(cm, clases):
    return dict(cmap=cm, norm=BoundaryNorm(clases, cm.N), ticks=clases)


# cada 500 mm donde está la lluvia observada y clases gruesas para los extremos de los reanálisis
P_CL = [0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 6000, 10000, 15000, 21000]
PM_CL = [0, 25, 50, 75, 100, 125, 150, 175, 200, 250, 300, 350, 400, 500]
ET_CL = [0, 300, 500, 700, 900, 1100, 1300, 1500, 1700, 1900, 2100]
R_CL = [0, 250, 500, 750, 1000, 1500, 2000, 2500, 3000, 5000, 8000, 12000, 20000]

P = _esc(_balances(len(P_CL) - 1), P_CL)
PM = _esc(_balances(len(PM_CL) - 1), PM_CL)
ETP = _esc(_desde_blanco("YlOrRd", len(ET_CL) - 1), ET_CL)
ETR = _esc(_desde_blanco("YlGn", len(ET_CL) - 1), ET_CL)
R = _esc(_desde_blanco("GnBu", len(R_CL) - 1), R_CL)         # escorrentía: verde-azul, distinta de la lluvia
T_VMIN, T_VMAX, T_CMAP = -6, 36, "RdYlBu_r"


def clases_hasta(esc, *datos):
    """Clases de la escala desde 0 hasta la primera que cubre el máximo de los datos."""
    b = np.asarray(esc["ticks"], float)
    vmax = max(float(np.nanmax(np.asarray(d, float))) for d in datos)
    k = int(np.searchsorted(b, vmax))           # primer límite >= vmax
    return list(b[: min(k, len(b) - 1) + 1])


def barra(fig, im, esc, *datos, ticks=None, **kw):
    """Barra de color cortada en el máximo de los datos del mapa (mismos colores por valor que en los demás mapas)."""
    b = clases_hasta(esc, *datos)
    n = len(b) - 1   # mismos colores (y mismos límites) que la escala completa, sólo las n primeras clases
    sm = ScalarMappable(norm=BoundaryNorm(b, n), cmap=ListedColormap(esc["cmap"](np.arange(n))))
    kw.pop("orientation", None)  # barras verticales: todas las etiquetas caben sin rotar
    cb = fig.colorbar(sm, ticks=ticks if ticks is not None else b, spacing="uniform", **kw)
    cb.ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " ")))
    cb.ax.tick_params(labelsize=7.5)
    return cb
