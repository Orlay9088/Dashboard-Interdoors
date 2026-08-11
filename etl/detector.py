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
        "Existencia", "Cant. disponible", "Cant. comprometida",
        "Cantidad disponible", "Cantidad comprometida", "Bodega",
        "Desc. bodega", "Nombre bodega", "Referencia", "Codigo", "Código",
        "Valor total", "Costo total", "Saldo", "Stock", "Disponible",
        "Comprometido", "LINEA", "ESTADO", "CANAL",
    ],
}


def detectar_tipo(ruta):
    xls = pd.ExcelFile(ruta)
    sheet_names = xls.sheet_names
    scores = {}
    for sheet in sheet_names:
        df = xls.parse(sheet, nrows=0)
        cols = [c.strip() for c in df.columns]
        normalized = {str(c).strip().casefold() for c in cols}
        for tipo, required in SIGNATURES.items():
            hits = sum(1 for r in required if r.casefold() in normalized)
            pct = hits / len(required) if required else 0
            if hits >= 3 or pct >= 0.3:
                scores[tipo] = scores.get(tipo, 0) + pct
    if not scores:
        return "generic", sheet_names[0]
    best = max(scores, key=scores.get)
    for sheet in sheet_names:
        df = xls.parse(sheet, nrows=0)
        cols = [c.strip() for c in df.columns]
        normalized = {str(c).strip().casefold() for c in cols}
        hits = sum(1 for r in SIGNATURES.get(best, []) if r.casefold() in normalized)
        if hits >= 3 or hits >= len(SIGNATURES.get(best, [])) * 0.3:
            return best, sheet
    return best, sheet_names[0]


def detectar_tipo_df(df):
    cols = {str(c).strip().casefold() for c in df.columns}
    scores = {
        tipo: sum(1 for required in signature if required.casefold() in cols)
        for tipo, signature in SIGNATURES.items()
    }
    if not scores:
        return "generic"
    best = max(scores, key=scores.get)
    return best if scores[best] >= 3 else "generic"
