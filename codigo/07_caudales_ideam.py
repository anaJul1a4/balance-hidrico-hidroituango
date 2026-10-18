"""
Punto 8 - Caudales IDEAM del cauce principal del Cauca (archivo nacional HidrologiaNacionalDiaria.zip, 12/08/2026).

Insumo : trabajo1/datos/caudales_ideam/q_media_diaria/Q_MEDIA_D@<codigo>.data  (Fecha|Valor, m³/s)
Criterio de completitud:
    mes válido  = al menos 80 % de los días con dato  (el caudal mensual es el promedio de los días)
    año válido  = 12 meses válidos
    estación apta = al menos 15 años válidos dentro de 1981-2010
Salidas: trabajo1/datos/caudales_ideam/
    disponibilidad_caudales.csv        resumen por estación
    Q_mensual_1981_2010.csv            serie mensual (sólo meses válidos) de las estaciones aptas
    Q_mensual_completa.csv             serie mensual válida de todo el registro
y trabajo1/resultados/06_caudales/disponibilidad_caudales.png
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DAT = ROOT / "trabajo1" / "datos" / "caudales_ideam"
FIG = ROOT / "trabajo1" / "resultados" / "06_caudales"
FIG.mkdir(parents=True, exist_ok=True)
P0, P1 = "1981", "2010"
MIN_DIAS, MIN_ANOS = 0.8, 15

est = pd.read_csv(ROOT / "trabajo1" / "datos" / "estaciones_caudal_priorizacion.csv", dtype={"codigo_ideam": str})
est = est[est.datos_locales.str.lower() == "no"].copy()
est.loc[est.codigo_ideam == "26087140", "codigo_ideam"] = "26087050"   # Mediacanoa: serie bajo el código automático

filas, mensual = [], {}
for r in est.itertuples():
    f = DAT / "q_media_diaria" / f"Q_MEDIA_D@{r.codigo_ideam}.data"
    if not f.exists():
        filas.append({"codigo": r.codigo_ideam, "estacion": r.estacion, "rol": r.rol, "prioridad": r.prioridad,
                      "area_km2": r.area_km2, "observacion": "Sin serie Q_MEDIA_D en el archivo IDEAM"})
        continue
    d = pd.read_csv(f, sep="|", parse_dates=["Fecha"]).set_index("Fecha").Valor
    d = d[~d.index.duplicated()].astype(float)
    d[d < 0] = np.nan
    dias = d.resample("MS").count()
    ndias = dias.index.days_in_month
    q = d.resample("MS").mean().where(dias >= MIN_DIAS * ndias)
    mensual[r.codigo_ideam] = q
    anos_ok = q.groupby(q.index.year).count().pipe(lambda s: s[s == 12])
    per = anos_ok[(anos_ok.index >= int(P0)) & (anos_ok.index <= int(P1))]
    qp = q[P0:P1]
    filas.append({
        "codigo": r.codigo_ideam, "estacion": r.estacion, "rol": r.rol, "prioridad": r.prioridad,
        "area_km2": r.area_km2,
        "inicio": d.dropna().index.min().date(), "fin": d.dropna().index.max().date(),
        "% dias con dato (registro)": 100 * d.notna().sum() / ((d.index.max() - d.index.min()).days + 1),
        "anos validos (registro)": len(anos_ok),
        "anos validos 1981-2010": len(per),
        "% meses validos 1981-2010": 100 * qp.notna().sum() / 360,
        "Q medio 1981-2010 (m3/s)": qp.mean(),
        "Q medio registro (m3/s)": q.mean(),
        "apta (>=15 anos 1981-2010)": len(per) >= MIN_ANOS,
        "observacion": "",
    })
disp = pd.DataFrame(filas)
disp.to_csv(DAT / "disponibilidad_caudales.csv", index=False, encoding="utf-8-sig")
pd.set_option("display.width", 250)
print(disp.drop(columns=["observacion"]).round(1).to_string(index=False))

Q = pd.DataFrame(mensual)
Q.to_csv(DAT / "Q_mensual_completa.csv", encoding="utf-8-sig")
aptas = disp.loc[disp["apta (>=15 anos 1981-2010)"] == True, "codigo"]
Q.loc[P0:P1, list(aptas)].to_csv(DAT / "Q_mensual_1981_2010.csv", encoding="utf-8-sig")

# figura de disponibilidad (meses válidos)
orden = disp.dropna(subset=["inicio"]).sort_values("area_km2", ascending=False, na_position="last")
fig, ax = plt.subplots(figsize=(12, 0.45 * len(orden) + 1.5))
for i, (_, r) in enumerate(orden.iterrows()):
    s = Q[r.codigo].notna()
    apta = r["apta (>=15 anos 1981-2010)"]
    ax.scatter(s.index[s], np.full(s.sum(), i), marker="|", s=60, c="#1a9850" if apta else "#d73027")
ax.axvspan(pd.Timestamp(P0), pd.Timestamp(f"{P1}-12-31"), color="0.85", zorder=0, label="Periodo 1981–2010")
ax.set_yticks(range(len(orden)))
ax.set_yticklabels([f"{r.estacion.title()} ({r.codigo})  —  {r['anos validos 1981-2010']:.0f} años completos 1981–2010"
                    for _, r in orden.iterrows()], fontsize=8)
ax.invert_yaxis(); ax.grid(axis="x", alpha=0.3)
ax.set_title("Meses con caudal válido (≥ 80 % de días) — verde: apta (≥ 15 años completos en 1981–2010)",
             fontsize=10)
ax.legend(loc="lower left", fontsize=8)
fig.tight_layout(); fig.savefig(FIG / "disponibilidad_caudales.png", dpi=200)
