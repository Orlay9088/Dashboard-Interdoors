import pandas as pd
import numpy as np
import requests
import time
from dash import html
from pages.components import fmt_p, fmt_pm


def generar_analisis(tipo, page, data):
    if data.empty:
        return html.Div("Sin datos para analizar.", className="text-muted")

    if tipo == "pedidos":
        return _analisis_pedidos(page, data)
    elif tipo == "facturas":
        return _analisis_facturas(page, data)
    elif tipo == "inventario":
        return _analisis_inventario(page, data)
    else:
        return _analisis_generico(data)


def _analisis_pedidos(page, data):
    vp = data["_valor"].sum()
    vc = data["_valor_sec"].sum()
    clientes = data["_cliente"].nunique()
    pedidos = data["_documento"].nunique()
    asesores = data["_vendedor"].nunique()
    cumpl = (vc / vp * 100) if vp else 0

    if page == "resumen":
        part_cnst = 0
        if "_canal" in data.columns:
            mask = data["_canal"] == "CNST - CONSTRUCCION"
            part_cnst = data.loc[mask, "_valor"].sum() / vp * 100 if vp else 0
        top3 = data.groupby("_cliente")["_valor"].sum().sort_values(ascending=False)
        top3_pct = top3.iloc[:3].sum() / vp * 100 if vp and len(top3) > 0 else 0
        meses = data["_fecha"].dt.to_period("M").nunique() if "_fecha" in data.columns else 0
        return html.Div([
            html.P([html.Strong("Resumen Ejecutivo - Hallazgos Clave")], className="fw-bold mb-2"),
            html.Ul([
                html.Li(f"Valor total de {fmt_p(vp)} en {pedidos:,} pedidos de {clientes} clientes, {asesores} asesores."),
                html.Li(f"Canal Construccion: {part_cnst:.1f}% del valor total."),
                html.Li(f"Top 3 clientes concentran {top3_pct:.1f}% del valor."),
                html.Li(f"Cumplimiento general: {cumpl:.1f}% ({fmt_p(vc)} de {fmt_p(vp)})."),
                html.Li(f"Periodo analizado: {meses} meses."),
            ], style={"paddingLeft": "1.2rem"}),
        ])
    elif page == "participacion":
        canales = data["_canal"].nunique() if "_canal" in data.columns else 0
        return html.Div([
            html.P([html.Strong("Participacion Comercial")], className="fw-bold mb-2"),
            html.Ul([
                html.Li(f"Distribucion en {canales} canales de venta."),
                html.Li(f"{asesores} asesores con actividad en el periodo."),
                html.Li(f"Valor promedio por asesor: {fmt_p(vp / asesores) if asesores else 0}."),
            ], style={"paddingLeft": "1.2rem"}),
        ])
    elif page == "pareto":
        pg = data.groupby("_cliente")["_valor"].sum().sort_values(ascending=False)
        pg_acum = (pg.cumsum() / vp * 100) if vp else pd.Series()
        hasta_80 = (pg_acum <= 80).sum()
        top3 = pg.head(3).sum() / vp * 100 if vp else 0
        return html.Div([
            html.P([html.Strong("Analisis Pareto")], className="fw-bold mb-2"),
            html.Ul([
                html.Li(f"{clientes} clientes activos en el periodo."),
                html.Li(f"Se requieren {hasta_80} clientes para alcanzar el 80%."),
                html.Li(f"Top 3 concentran {top3:.1f}% del valor."),
                html.Li(f"{'ALERTA: Alta concentracion.' if hasta_80 < 20 else 'Distribucion moderada.'}"),
            ], style={"paddingLeft": "1.2rem"}),
        ])
    elif page == "ranking":
        rank = data.groupby("_vendedor").agg(Valor=("_valor", "sum")).reset_index().sort_values("Valor", ascending=False)
        top = rank.iloc[0] if not rank.empty else None
        return html.Div([
            html.P([html.Strong("Ranking de Asesores")], className="fw-bold mb-2"),
            html.Ul([
                html.Li(f"#1 {top['_vendedor']}: {fmt_p(top['Valor'])}." if top is not None else "Sin datos."),
                html.Li(f"Total: {len(rank)} asesores activos."),
                html.Li(f"Promedio: {fmt_p(vp / asesores) if asesores else 0} por asesor."),
            ], style={"paddingLeft": "1.2rem"}),
        ])
    elif page == "embudo":
        return html.Div([
            html.P([html.Strong("Embudo de Pedidos")], className="fw-bold mb-2"),
            html.Ul([
                html.Li(f"Tasa de cierre: {cumpl:.1f}% del valor total."),
                html.Li(f"Valor pendiente: {fmt_p(vp - vc)} por comprometer."),
            ], style={"paddingLeft": "1.2rem"}),
        ])
    elif page == "heatmap":
        return html.Div([
            html.P([html.Strong("Heatmap de Rendimiento")], className="fw-bold mb-2"),
            html.Ul([
                html.Li(f"{asesores} asesores con desempeno registrado."),
                html.Li(f"Valor total distribuido: {fmt_p(vp)}."),
            ], style={"paddingLeft": "1.2rem"}),
        ])
    elif page == "proyeccion":
        evol = data.groupby(data["_fecha"].dt.to_period("M")).agg(Valor=("_valor", "sum")).reset_index()
        coef = np.polyfit(range(len(evol)), evol["Valor"], 1) if len(evol) >= 3 else [0, 0]
        proy = np.polyval(coef, len(evol)) if len(evol) >= 3 else 0
        direction = "creciente" if coef[0] > 0 else "decreciente"
        return html.Div([
            html.P([html.Strong("Proyeccion de Cierre")], className="fw-bold mb-2"),
            html.Ul([
                html.Li(f"Tendencia {direction} (pendiente: {coef[0]/1e6:.1f}M/mes)."),
                html.Li(f"Proyeccion proximo mes: {fmt_p(proy)}."),
            ], style={"paddingLeft": "1.2rem"}),
        ])
    return html.Div("Analisis no disponible.", className="text-muted")


def _analisis_facturas(page, data):
    ventas = data["_valor"].sum()
    facturas = data["_documento"].nunique()
    clientes = data["_cliente"].nunique()
    vendedores = data["_vendedor"].nunique()
    costo = data["_costo"].sum() if "_costo" in data.columns else 0
    margen_pct = (ventas - costo) / ventas * 100 if ventas else 0
    ticket = ventas / facturas if facturas else 0

    return html.Div([
        html.P([html.Strong("Analisis de Facturacion")], className="fw-bold mb-2"),
        html.Ul([
            html.Li(f"Ventas totales: {fmt_p(ventas)} en {facturas:,} facturas ({clientes} clientes)."),
            html.Li(f"Ticket promedio: {fmt_p(ticket)}. Margen global: {margen_pct:.1f}%."),
            html.Li(f"Equipo de {vendedores} vendedores activos."),
            html.Li(f"Costo total: {fmt_p(costo)} ({100-margen_pct:.1f}% de las ventas)."),
        ], style={"paddingLeft": "1.2rem"}),
    ])


def _analisis_inventario(page, data):
    valor_total = data["_valor"].sum()
    productos = data["_referencia"].nunique()
    bodegas = data["_bodega"].nunique() if "_bodega" in data.columns else 0
    existencia = data["_cantidad"].sum() if "_cantidad" in data.columns else 0
    disponible = data["_cantidad_com"].sum() if "_cantidad_com" in data.columns else 0
    comprometido = data["_cantidad_pen"].sum() if "_cantidad_pen" in data.columns else 0

    return html.Div([
        html.P([html.Strong("Analisis de Inventario")], className="fw-bold mb-2"),
        html.Ul([
            html.Li(f"Valor total inventariado: {fmt_p(valor_total)} en {productos:,} referencias."),
            html.Li(f"Distribuido en {bodegas} bodegas con {existencia:,.0f} unidades."),
            html.Li(f"Disponible: {disponible:,.0f} und. Comprometido: {comprometido:,.0f} und."),
            html.Li(f"Valor promedio por producto: {fmt_p(valor_total / productos) if productos else 0}."),
        ], style={"paddingLeft": "1.2rem"}),
    ])


def _analisis_generico(data):
    n = len(data)
    cols = [c for c in data.columns if not c.startswith("_")]
    return html.Div([
        html.P([html.Strong("Analisis Exploratorio")], className="fw-bold mb-2"),
        html.Ul([
            html.Li(f"Dataset con {n:,} registros y {len(cols)} columnas."),
            html.Li(f"Columnas: {', '.join(cols[:10])}"),
        ], style={"paddingLeft": "1.2rem"}),
    ])


def generar_con_gemini(tipo, page, data, api_key):
    if not api_key or data.empty:
        return None
    ventas = data["_valor"].sum()
    prompt = f"""Eres un analista de datos comerciales. Genera un analisis conciso en 3-4 puntos clave para la seccion '{page}' del tipo '{tipo}'.
Metricas principales:
- Valor total: ${ventas:,.0f}
- Registros: {len(data):,}
- Columnas: {', '.join([c for c in data.columns if c.startswith('_')][:10])}
Responde con una lista usando * al inicio de cada linea. Se breve."""
    for attempt in range(3):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
            resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
            if resp.ok:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                text = text.replace("```html", "").replace("```", "").strip()
                return html.Div([
                    html.P([html.Strong("Analisis con Gemini AI")], className="fw-bold mb-2",
                           style={"color": "#1e3a5f"}),
                    html.Div(text, className="small"),
                ])
            elif resp.status_code == 429 and attempt < 2:
                time.sleep(2 ** attempt)
        except Exception:
            if attempt < 2:
                time.sleep(2 ** attempt)
    return None
