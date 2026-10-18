"""
Modo informe: vuelve a guardar las figuras originales (mismos datos, misma resolución, mismos detalles) con el texto agrandado,
para que al insertarlas en el Word a un ancho dado la letra se imprima al tamaño con que se diseñó (≈ 7–10 pt).

INFORME_FIGS='{"mapas_temperatura_panel.png": 16}'   nombre del PNG → ancho (cm) al que se insertará en el informe
INFORME_OUT=<carpeta>                                 donde se guardan (las originales no se tocan)

Factor de letra K = ancho de la figura (cm) / ancho en el informe (cm). Las figuras no listadas no se guardan.
"""
import json
import os
from pathlib import Path

from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties

CFG = json.loads(os.environ.get("INFORME_FIGS", "{}"))
OUT = Path(os.environ.get("INFORME_OUT", "."))
OUT.mkdir(parents=True, exist_ok=True)
_K = [1.0]
_tam = FontProperties.get_size_in_points
FontProperties.get_size_in_points = lambda self: _tam(self) * _K[0]
_guardar = Figure.savefig


def _savefig(self, fname, *a, **kw):
    nombre = Path(str(fname)).name
    if nombre not in CFG:
        return                                    # las figuras originales no se reescriben
    _K[0] = self.get_figwidth() * 2.54 / CFG[nombre] * float(os.environ.get("INFORME_F", "1"))
    kw["bbox_inches"] = "tight"
    kw["dpi"] = max(kw.get("dpi") or 0, 200)
    _guardar(self, OUT / nombre, *a, **kw)
    print(f"informe: {nombre}  K = {_K[0]:.2f}")
    _K[0] = 1.0


Figure.savefig = _savefig
