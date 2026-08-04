import pandas as pd

MAPPINGS = {
    "pedidos": {
        "_fecha": ["Fecha"],
        "_valor": ["Valor pendiente subtotal"],
        "_valor_sec": ["V.COMPROMETIDO"],
        "_cliente": ["Razon social cliente factura"],
        "_vendedor": ["Nombre vendedor"],
        "_canal": ["CANAL DISTRIBUCION"],
        "_linea": ["LINEA"],
        "_sublinea": ["SUB-LINEA"],
        "_documento": ["Nro documento"],
        "_cantidad": ["Cant. pedida"],
        "_cantidad_pen": ["Cant. pendiente"],
        "_cantidad_com": ["Cant. comprom."],
        "_estado": ["Estado movto."],
        "_referencia": ["Referencia"],
        "_bodega": [],
    },
    "facturas": {
        "_fecha": ["Fecha"],
        "_valor": ["Valor subtotal local"],
        "_valor_sec": [],
        "_cliente": ["Razon social cliente factura"],
        "_vendedor": ["Nombre vendedor"],
        "_canal": ["CANAL DISTRIBUCION"],
        "_linea": ["LINEA"],
        "_sublinea": ["SUB-LINEA"],
        "_documento": ["Nro documento"],
        "_cantidad": ["Cantidad"],
        "_cantidad_pen": [],
        "_cantidad_com": [],
        "_estado": ["Estado"],
        "_referencia": [],
        "_grupo": ["GRUPO"],
        "_margen": ["Margen promedio"],
        "_costo": ["Costo promedio total"],
        "_bodega": [],
    },
    "inventario": {
        "_fecha": [],
        "_valor": ["Valor total"],
        "_valor_sec": [],
        "_cliente": ["Cliente"],
        "_vendedor": [],
        "_canal": ["CANAL"],
        "_linea": ["LINEA"],
        "_sublinea": ["SUB-LINEA"],
        "_documento": [],
        "_cantidad": ["Existencia"],
        "_cantidad_pen": ["Cant. comprometida"],
        "_cantidad_com": ["Cant. disponible"],
        "_estado": ["ESTADO"],
        "_referencia": ["Referencia"],
        "_bodega": ["Bodega", "Desc. bodega"],
        "_ubicacion": ["Desc. ubicacion", "Ubicacion"],
        "_costo": ["Costo prom. total"],
        "_margen": ["Margen"],
    },
}


def normalizar(df, tipo):
    if tipo not in MAPPINGS:
        tipo = "pedidos"
    mapping = MAPPINGS[tipo]
    df_out = pd.DataFrame(index=df.index)
    for canon, sources in mapping.items():
        found = None
        for s in sources:
            if s in df.columns:
                found = s
                break
        if found:
            df_out[canon] = df[found]
        else:
            df_out[canon] = pd.NaT if canon == "_fecha" else (
                "" if canon in ("_cliente", "_vendedor", "_canal", "_linea",
                                "_sublinea", "_documento", "_estado",
                                "_referencia", "_bodega", "_ubicacion",
                                "_grupo") else 0)
    df_out["_tipo"] = tipo
    return df_out
