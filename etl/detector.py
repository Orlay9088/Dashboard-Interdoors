import pandas as pd

SIGNATURES = {
    "pedidos": [
        "Nro documento", "Valor pendiente subtotal", "Cant. pendiente",
        "Nombre vendedor", "Estado movto.", "CANAL DISTRIBUCION",
    ],
    "facturas": [
        "Valor subtotal local", "Margen promedio", "Costo promedio total",
        "GRUPO", "Nro documento",
    ],
    "inventario": [
        "Existencia", "Cant. disponible", "Bodega",
        "Referencia", "Valor total",
    ],
}


def detectar_tipo(ruta):
    xls = pd.ExcelFile(ruta)
    sheet_names = xls.sheet_names
    scores = {}
    for sheet in sheet_names:
        df = xls.parse(sheet, nrows=0)
        cols = [c.strip() for c in df.columns]
        for tipo, required in SIGNATURES.items():
            hits = sum(1 for r in required if r in cols)
            pct = hits / len(required) if required else 0
            if pct >= 0.5:
                scores[tipo] = scores.get(tipo, 0) + pct
    if not scores:
        return "generic", sheet_names[0]
    best = max(scores, key=scores.get)
    for sheet in sheet_names:
        df = xls.parse(sheet, nrows=0)
        cols = [c.strip() for c in df.columns]
        hits = sum(1 for r in SIGNATURES.get(best, []) if r in cols)
        if hits >= len(SIGNATURES.get(best, [])) * 0.5:
            return best, sheet
    return best, sheet_names[0]


def detectar_tipo_df(df):
    cols = [c.strip() for c in df.columns]
    if not scores:
        return "generic"
    best = max(scores, key=scores.get)
    return best if scores[best] >= 0.4 else "generic"
