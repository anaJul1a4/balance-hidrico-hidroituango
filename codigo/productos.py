"""
Lectura homogénea de los productos de precipitación mensual (mm/mes) con dimensiones (time, lat, lon).

    "CHIRPS"      → CHIRPS v2.0 (Funk et al., 2015), IRI Data Library, recorte de la cuenca 1981-2025  [producto principal]
    "CHIRPS v3.0" → CHIRPS v3.0 del Drive del curso (Colombia 1981-2025)                                [sensibilidad]
    "ERA5-Land", "ERA5" → archivos del Drive del curso (Colombia 1981-2025)
"""
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[2]
CURSO = ROOT / "PRECIPITACION_COLOMBIA-20261003T131021Z-1-001" / "PRECIPITACION_COLOMBIA"
V2 = ROOT / "PRECIPITACION_COLOMBIA_CHIRPS_v2" / "CHIRPS_v2p0_mensual_cuenca_1981_2025.nc"
FUENTE = {"CHIRPS": "CHIRPS v2.0 (IRI Data Library)", "CHIRPS v3.0": "CHIRPS v3.0 (Drive del curso)",
          "ERA5-Land": "ERA5-Land (Drive del curso)", "ERA5": "ERA5 (Drive del curso)"}
RESOL = {"CHIRPS": "0.05°", "CHIRPS v3.0": "0.05°", "ERA5-Land": "0.1°", "ERA5": "0.25°"}


def abrir(nombre):
    """Dataset con la variable 'precip' (mm/mes) y dimensiones time (inicio de mes), lat, lon."""
    if nombre == "CHIRPS":
        ds = xr.open_dataset(V2, decode_times=False)
        t = pd.date_range("1960-01-01", periods=int(ds["T"].values.max()) + 1, freq="MS")[np.floor(ds["T"].values).astype(int)]
        p = ds.precipitation.rename({"T": "time", "Y": "lat", "X": "lon"}).assign_coords(time=t)
    else:
        f, la, lo = {"CHIRPS v3.0": ("CHIRPS/CHIRPS_mensual_Colombia_1981_2025.nc", "lat", "lon"),
                     "ERA5-Land": ("ERA5_LAND/ERA5_Land_precipitacion_mensual_Colombia_1981_2025.nc", "latitude", "longitude"),
                     "ERA5": ("ERA5/ERA5_precipitacion_mensual_Colombia_1981_2025.nc", "latitude", "longitude")}[nombre]
        ds = xr.open_dataset(CURSO / f)
        p = ds.precip.rename({la: "lat", lo: "lon"})
        p = p.assign_coords(time=pd.to_datetime(p.time.values).to_period("M").to_timestamp())
        p = p.drop_vars([c for c in p.coords if c not in ("time", "lat", "lon")])
    p = p.where(p >= 0)                                   # CHIRPS v3.0 trae relleno negativo sobre el mar
    p.attrs = {"units": "mm/month", "source": FUENTE[nombre]}
    return p.to_dataset(name="precip")
