import unicodedata
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

_MIN_HITS = 3
_MIN_PCT = 0.3
_MAX_HEADER_SCAN_ROWS = 40


def _norm(value):
    """Normaliza texto: quita acentos, espacios, y pasa a minusculas."""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.strip().casefold()


def _find_header_row(xls, sheet):
    """Busca la fila donde estan los titulos de columnas (el header real)."""
    raw = xls.parse(sheet, header=None, nrows=_MAX_HEADER_SCAN_ROWS)
    best_row = 0
    best_score = -1
    for i in range(min(_MAX_HEADER_SCAN_ROWS, len(raw))):
        values = raw.iloc[i].tolist()
        non_empty = [v for v in values if pd.notna(v) and str(v).strip()]
        # Un header real tiene varias celdas de texto y poca data numerica
        text_count = sum(1 for v in non_empty if not _looks_numeric(v))
        if text_count >= 2 and text_count > best_score:
            best_score = text_count
            best_row = i
    return best_row


def _looks_numeric(value):
    text = str(value).strip()
    if not text:
        return False
    try:
        float(text.replace(",", "").replace("$", "").replace("%", ""))
        return True
    except ValueError:
        return False


def _columns_at_header(xls, sheet, header_row):
    df = xls.parse(sheet, header=header_row, nrows=1)
    return [str(c) for c in df.columns]


def _score_type(normalized_cols, required):
    hits = sum(1 for r in required if _norm(r) in normalized_cols)
    pct = hits / len(required) if required else 0
    return hits, pct


def detectar_tipo(ruta):
    """Detecta el tipo de modulo y la hoja/header correctos.

    Devuelve (tipo, sheet, header_row). Si no reconoce nada, tipo="generic".
    """
    xls = pd.ExcelFile(ruta)
    sheet_names = xls.sheet_names
    scores = {}
    sheet_for = {}

    for sheet in sheet_names:
        header_row = _find_header_row(xls, sheet)
        normalized = {_norm(c) for c in _columns_at_header(xls, sheet, header_row)}
        for tipo, required in SIGNATURES.items():
            hits, pct = _score_type(normalized, required)
            if hits >= _MIN_HITS or pct >= _MIN_PCT:
                if tipo not in scores or pct > scores[tipo]:
                    scores[tipo] = pct
                    sheet_for[tipo] = (sheet, header_row)

    if not scores:
        return "generic", sheet_names[0], 0

    best = max(scores, key=scores.get)
    sheet, header_row = sheet_for.get(best, (sheet_names[0], 0))
    return best, sheet, header_row


def detectar_tipo_df(df):
    cols = {_norm(c) for c in df.columns}
    scores = {}
    for tipo, signature in SIGNATURES.items():
        hits = sum(1 for required in signature if _norm(required) in cols)
        scores[tipo] = hits
    if not scores:
        return "generic"
    best = max(scores, key=scores.get)
    return best if scores[best] >= _MIN_HITS else "generic"