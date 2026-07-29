import pandas as pd
import numpy as np

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

NUMERIC_FIELDS = ["_valor", "_valor_sec", "_cantidad", "_cantidad_pen",
                  "_cantidad_com", "_margen", "_costo"]


def procesar(df):
    df = df.copy()
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype(str).str.strip().replace("nan", "").replace("None", "")

    if "_fecha" in df.columns:
        df["_fecha"] = pd.to_datetime(df["_fecha"], errors="coerce")

    for c in NUMERIC_FIELDS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    df["_anio"] = 0
    df["_mes"] = 0
    df["_nombre_mes"] = ""
    df["_trimestre"] = 0
    df["_semana"] = 0
    if "_fecha" in df.columns:
        f = df["_fecha"]
        mask = f.notna()
        df.loc[mask, "_anio"] = f.loc[mask].dt.year.astype(int)
        df.loc[mask, "_mes"] = f.loc[mask].dt.month.astype(int)
        df.loc[mask, "_nombre_mes"] = f.loc[mask].dt.month.map(MESES_ES).fillna("")
        df.loc[mask, "_trimestre"] = f.loc[mask].dt.quarter.astype(int)
        df.loc[mask, "_semana"] = f.loc[mask].dt.isocalendar().week.astype(int)

    df = df.dropna(how="all").reset_index(drop=True)
    return df
