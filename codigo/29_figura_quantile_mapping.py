"""
Figura «antes y después» de la corrección por mapeo de cuantiles (28_quantile_mapping.py): precipitación media anual (fila superior)
y escorrentía de largo plazo R = P − ETR con la ETP de Hargreaves y Budyko celda a celda (fila inferior), para ERA5 y ERA5-Land sin
corregir y corregidos. Mismas escalas de color por variable que el resto del trabajo (escalas.py) y mismo estilo que las figuras
del informe (base cartográfica de 24_figuras_informe.py).

Salidas: resultados/informe_figs/panel_QM_P_R.png (informe) y resultados/17_quantile_mapping/resumen_QM.csv
"""
from pathlib import Path

S = Path(__file__).parent
_src = (S / "24_figuras_informe.py").read_text(encoding="utf-8")
exec(compile(_src.split("# ============================================================================= paneles de mapas")[0], "base24", "exec"))

QMD = RES / "17_quantile_mapping"
ETP = leer(RES / "08_etp_etr" / "ETP_anual_hargreaves_90m_3116.tif")[0]
COLS = [("ERA5", "sin corregir", "P_ERA5_sin_corregir_90m_3116.tif"),
        ("ERA5", "mapeo de cuantiles", "P_ERA5_con_mapeo_de_cuantiles_90m_3116.tif"),
        ("ERA5-Land", "sin corregir", "P_ERA5_Land_sin_corregir_90m_3116.tif"),
        ("ERA5-Land", "mapeo de cuantiles", "P_ERA5_Land_con_mapeo_de_cuantiles_90m_3116.tif")]
media = lambda a: np.nanmean(a[mask])  # noqa: E731
fig, axs = plt.subplots(2, 4, figsize=(W, 5.7), gridspec_kw=dict(wspace=0.75, hspace=0.08))
filas = []
for j, (prod, estado, f) in enumerate(COLS):
    p = leer(QMD / f)[0]
    r = p - budyko(p, ETP)
    for i, (a, esc, et, nom) in enumerate([(p, E.P, "P (mm/año)", "P"), (r, E.R, "R (mm/año)", "R")]):
        ax = axs[i, j]
        tit = (f"{prod}\n{estado}\n" if i == 0 else "") + f"{nom} media {media(a):,.0f} mm/año".replace(",", " ")
        mapa(ax, a, esc["cmap"], esc["norm"], tit,
             caja=f"{np.nanmin(a[mask]):,.0f}–{np.nanmax(a[mask]):,.0f} mm".replace(",", " "))
        ax.title.set_fontsize(7)
        barra(fig, esc, a[mask], ax, et)
        if j:
            ax.set_yticklabels([])
        else:
            ax.set_ylabel("Norte (km)", fontsize=6.5, labelpad=1)
        if i == 1:
            ax.set_xlabel("Este (km)", fontsize=6.5, labelpad=1)
        else:
            ax.set_xticklabels([])
        filas.append({"producto": prod, "estado": estado, "variable": nom, "media (mm/año)": media(a),
                      "mín": np.nanmin(a[mask]), "máx": np.nanmax(a[mask])})
norte(axs[0, -1]); pie_crs(fig, 0.07)
guardar(fig, "panel_QM_P_R.png")
pd.DataFrame(filas).round(0).to_csv(QMD / "resumen_QM.csv", index=False, encoding="utf-8-sig")
print(pd.DataFrame(filas).round(0).to_string(index=False))
