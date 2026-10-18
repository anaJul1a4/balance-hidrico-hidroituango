"""
Figuras del informe escrito a partir de las ORIGINALES: vuelve a correr cada script en modo informe (modo_informe.py), que sólo
agranda la letra según el ancho al que la figura irá en el Word. Se conservan la resolución, los rásteres de 90 m, las isolíneas,
las cajas de texto y demás detalles. Salida: resultados/informe_figs_hd/.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

S = Path(__file__).parent
OUT = S.parent / "resultados" / "informe_figs_hd"

# script → {figura: ancho en el informe (cm)}
FIGS = {
    "04_mapa_estaciones_precipitacion.py": {"mapa_estaciones_precipitacion.png": 12},
    "05_interpolacion_precipitacion.py": {"variograma_validacion_cruzada.png": 16, "mapa_precipitacion_media_anual.png": 12},
    "06_temperatura_elevacion.py": {"diagramas_T_Z.png": 16},
    "11_etp_etr_budyko.py": {"ETP_mensual.png": 14, "curva_budyko.png": 11},
    "08_excel_caudales.py": {"mapa_estaciones_caudal_validadas.png": 12},
    "07_caudales_ideam.py": {"disponibilidad_caudales.png": 16},
    "12_balance_subcuencas.py": {"balance_Q_est_vs_obs.png": 16},
    "17_climatologia_precipitacion.py": {"ciclo_anual.png": 14},
    "18_ciclo_productos.py": {"ciclos_productos.png": 16, "taylor.png": 10},
}
ANCHOS = {f: cm for d in FIGS.values() for f, cm in d.items()}

if __name__ == "__main__":
    sel = sys.argv[1:] or list(FIGS)
    for script in sel:
        env = os.environ | {"INFORME_FIGS": json.dumps(FIGS[script]), "INFORME_OUT": str(OUT), "PYTHONIOENCODING": "utf-8",
                            "MPLBACKEND": "Agg"}
        cod = f"import sys, runpy, modo_informe; sys.argv=[{script!r}]; runpy.run_path({script!r}, run_name='__main__')"
        r = subprocess.run([sys.executable, "-c", cod], cwd=S, env=env, capture_output=True, text=True, encoding="utf-8")
        print(f"== {script}: " + " | ".join(l for l in r.stdout.splitlines() if l.startswith("informe:")))
        if r.returncode:
            print(r.stderr[-1500:])
