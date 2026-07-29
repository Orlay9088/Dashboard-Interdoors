"""
DASHBOARD EJECUTIVO DE PEDIDOS SIESA
Dash + dash-bootstrap-components + Plotly

Misma tabla maestra (Base_Maestra_Pedidos.parquet)
Mismas 7 secciones de analisis
"""

import base64
import json
import re
import requests
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
import sys

import dash
from dash import dcc, html, Input, Output, State, callback, no_update, dash_table
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from config import ARCHIVO_BASE, CARPETA_ENTRADA, RUTA_PRESUPUESTO

# ============================================================
# DATA LOADING
# ============================================================
def cargar_base():
    if ARCHIVO_BASE.exists():
        df = pd.read_parquet(ARCHIVO_BASE)
        for c in ["Cant. pedida", "Cant. pendiente", "Cant. comprom.",
                  "Valor pendiente subtotal", "V.COMPROMETIDO"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        if "Fecha" in df.columns:
            df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
        return df
    return pd.DataFrame()

df_global = cargar_base()

# ============================================================
# PRESUPUESTO
# ============================================================

def cargar_presupuesto():
    if not RUTA_PRESUPUESTO.exists():
        return {}
    df = pd.read_excel(RUTA_PRESUPUESTO, sheet_name=0, header=None)
    advisors = {0:"Mateo Posada",3:"Eliana Gonzalez",6:"Leonardo Zuleta",
                9:"Ines Maria Sanchez",12:"Laura Ochoa",15:"Karol",18:"Yudi"}
    presupuesto = {}
    for col_mes, name in advisors.items():
        total = 0
        for r in range(4, 16):
            if pd.isna(df.iloc[r, col_mes]):
                continue
            v = df.iloc[r, col_mes+1]
            if pd.isna(v):
                continue
            m = re.search(r'[\d.]+', str(v))
            if m:
                try:
                    val = float(m.group().replace(".", ""))
                    if val > 0:
                        total += val
                except (ValueError, TypeError, AttributeError):
                    pass
        if total > 0:
            presupuesto[name] = total
    return presupuesto

def mapear_asesor_presupuesto(nombre_db, presupuesto):
    if not presupuesto:
        return None
    palabras_db = set(nombre_db.upper().split())
    for nom_budget in presupuesto:
        palabras_budget = set(nom_budget.upper().split())
        if palabras_budget.issubset(palabras_db):
            return nom_budget
    return None

# ============================================================
# APP SETUP
# ============================================================
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dmc.styles.DATES],
    title="Dashboard Ejecutivo - Pedidos",
    suppress_callback_exceptions=True,
)
server = app.server

NAVY = "#1e3a5f"
BLUE = "#3b82f6"
AMBER = "#f59e0b"
GREEN = "#10b981"
RED = "#ef4444"
GRAY = "#64748b"
COLORS = px.colors.qualitative.Set2

HEX_TO_RGB = {
    "#1e3a5f": (30, 58, 95),
    "#3b82f6": (59, 130, 246),
    "#10b981": (16, 185, 129),
    "#f59e0b": (245, 158, 11),
    "#ef4444": (239, 68, 68),
    "#64748b": (100, 116, 139),
}

def rgba(color, alpha):
    rgb = HEX_TO_RGB.get(color)
    if rgb:
        return f"rgba({rgb[0]},{rgb[1]},{rgb[2]},{alpha})"
    return color

PLOTLY_TEMPLATE = dict(
    layout=dict(
        paper_bgcolor="#f8fafc", plot_bgcolor="#f8fafc",
        font=dict(family="Segoe UI, Arial, sans-serif", color="#334155"),
        hoverlabel=dict(bgcolor=NAVY, font_color="white", font_size=12),
        xaxis=dict(gridcolor="#e2e8f0", zeroline=False, showline=True, linecolor="#cbd5e1"),
        yaxis=dict(gridcolor="#e2e8f0", zeroline=False, showline=True, linecolor="#cbd5e1"),
    )
)

# ============================================================
# HELPERS
# ============================================================
def build_podium(rank_df, title, value_col, pct_col, extra_col=None):
    top3 = rank_df.head(3).reset_index(drop=True)
    labels = ["#1", "#2", "#3"]
    colors = ["#FFD700", "#C0C0C0", "#CD7F32"]
    badges = ["#B8860B", "#696969", "#8B4513"]
    heights = ["180px", "140px", "110px"]
    offsets = ["0px", "40px", "70px"]

    cols = []
    for i in range(3):
        r = top3.iloc[i]
        cols.append(dbc.Col([
            html.Div([
                html.Div(labels[i], style={
                    "fontSize": "1.6rem", "fontWeight": "bold",
                    "color": "white", "background": badges[i],
                    "borderRadius": "50%", "width": "44px", "height": "44px",
                    "display": "flex", "alignItems": "center", "justifyContent": "center",
                    "margin": "0 auto 4px auto",
                }),
                html.Div(r["Nombre vendedor"], className="fw-bold small",
                         style={"wordBreak": "break-word", "lineHeight": "1.1"}),
                html.Div(fmt_p(r[value_col]), className="fw-bold",
                         style={"color": NAVY, "fontSize": "1rem"}),
                html.Div(f"{r[pct_col]:.1f}%", className="text-muted small"),
                html.Div(f"Comp: {r['% Cumpl']:.1f}%" if extra_col and pd.notna(r.get(extra_col)) else "",
                         className="text-muted small"),
            ], style={
                "background": f"linear-gradient(180deg, {colors[i]}22, white)",
                "borderTop": f"4px solid {colors[i]}",
                "borderRadius": "12px 12px 0 0",
                "height": heights[i], "marginTop": offsets[i],
                "display": "flex", "flexDirection": "column",
                "alignItems": "center", "justifyContent": "flex-start",
                "padding": "0.75rem 0.5rem", "textAlign": "center",
            })
        ], width=4, className="px-1"))

    return html.Div([
        html.H6(title, className="fw-bold text-center mb-2", style={"color": NAVY}),
        dbc.Row([cols[1], cols[0], cols[2]], className="g-0", style={"alignItems": "flex-end"}),
    ], className="mb-3")

def fig_layout(title="", height=400, **overrides):
    layout = dict(
        title=dict(text=title, font=dict(size=14, color=NAVY), x=0.02, y=0.97),
        height=height, margin=dict(t=36, b=40, l=10, r=10),
        hovermode="x unified",
    )
    layout.update(PLOTLY_TEMPLATE["layout"])
    layout.update(overrides)
    return layout

def kpi_card(label, value, sub=""):
    return dmc.Card([
        dmc.CardSection([
            html.Div(label, className="text-center text-uppercase small text-muted fw-semibold"),
            html.Div(value, className="text-center fw-bold", style={"fontSize": "1.5rem", "color": NAVY}),
            html.Div(sub, className="text-center small text-muted mt-1") if sub else "",
        ]),
    ], withBorder=True, shadow="sm", padding="lg", radius="md", className="h-100")

def fmt_p(valor):
    if pd.isna(valor) or valor == 0:
        return "$ 0"
    s = f"{abs(valor):,.0f}".replace(",", ".")
    return f"$ {s}"

def fmt_pm(valor):
    if pd.isna(valor) or valor == 0:
        return "$ 0"
    v = valor / 1e6
    s = f"{abs(v):,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"$ {s}M"

def apply_filters(data, filters_dict):
    if data.empty:
        return data
    d = data.copy()
    rango = filters_dict.get("rango", [])
    if len(rango) == 2 and rango[0] and rango[1]:
        try:
            inicio = pd.Timestamp(rango[0]).date()
            fin = pd.Timestamp(rango[1]).date()
            mask = d["Fecha"].notna() & (d["Fecha"].dt.date >= inicio) & (d["Fecha"].dt.date <= fin)
            d = d[mask]
        except (ValueError, TypeError, AttributeError):
            print(f"Advertencia: filtro de fecha invalido: {rango}")
    asesor = filters_dict.get("asesor", "Todos")
    if asesor and asesor != "Todos":
        d = d[d["Nombre vendedor"] == asesor]
    canal = filters_dict.get("canal", "Todos")
    if canal and canal != "Todos":
        d = d[d["CANAL DISTRIBUCION"] == canal]
    estado = filters_dict.get("estado", "Todos")
    if estado and estado != "Todos":
        d = d[d["Estado movto."] == estado]
    return d

# ============================================================
# ANALISIS AUTOMATICO POR SECCION
# ============================================================
def generar_analisis(page, data):
    if data.empty:
        return html.Div("Sin datos para analizar.", className="text-muted")

    vp = data["Valor pendiente subtotal"].sum()
    vc = data["V.COMPROMETIDO"].sum()

    if page == "resumen":
        total_pedidos = data["Nro documento"].nunique()
        total_clientes = data["Razon social cliente factura"].nunique()
        num_asesores = data["Nombre vendedor"].nunique()
        cant_pedida = data["Cant. pedida"].sum()
        part_const = (data[data["CANAL DISTRIBUCION"]=="CNST - CONSTRUCCION"]["Valor pendiente subtotal"].sum()/vp*100) if vp else 0
        top3 = data.groupby("Razon social cliente factura")["Valor pendiente subtotal"].sum().sort_values(ascending=False)
        top3_pct = (top3.iloc[:3].sum()/vp*100) if vp else 0
        cumpl = (vc/vp*100) if vp else 0
        meses = data["Fecha"].dt.to_period("M").nunique()
        return html.Div([
            html.P([html.Strong("Resumen Ejecutivo - Hallazgos Clave")], className="fw-bold mb-2"),
            html.Ul([
                html.Li(f"Valor total de {fmt_p(vp)} distribuido en {total_pedidos:,} pedidos de {total_clientes} clientes, gestionados por {num_asesores} asesores."),
                html.Li(f"El canal Construccion representa el {part_const:.1f}% del valor total."),
                html.Li(f"Los 3 principales clientes concentran el {top3_pct:.1f}% del valor (indicador de concentracion)."),
                html.Li(f"El cumplimiento general es del {cumpl:.1f}% — {fmt_p(vc)} comprometido de {fmt_p(vp)} total."),
                html.Li(f"Se analizaron {meses} meses de actividad comercial."),
            ], style={"paddingLeft": "1.2rem"}),
        ])

    elif page == "participacion":
        num_canales = data["CANAL DISTRIBUCION"].nunique()
        num_lineas = data["LINEA"].nunique()
        top_canal = data.groupby("CANAL DISTRIBUCION")["Valor pendiente subtotal"].sum().idxmax()
        top_canal_pct = data.groupby("CANAL DISTRIBUCION")["Valor pendiente subtotal"].sum().max()/vp*100
        top_asesor = data.groupby("Nombre vendedor")["Valor pendiente subtotal"].sum().idxmax()
        top_asesor_pct = data.groupby("Nombre vendedor")["Valor pendiente subtotal"].sum().max()/vp*100
        return html.Div([
            html.P([html.Strong("Analisis de Participacion Comercial")], className="fw-bold mb-2"),
            html.Ul([
                html.Li(f"Distribucion en {num_canales} canales de venta y {num_lineas} lineas de producto."),
                html.Li(f"Canal lider: {top_canal} con {top_canal_pct:.1f}% del valor total."),
                html.Li(f"Asesor con mayor participacion: {top_asesor} con {top_asesor_pct:.1f}% del valor."),
            ], style={"paddingLeft": "1.2rem"}),
        ])

    elif page == "pareto":
        pg = data.groupby("Razon social cliente factura")["Valor pendiente subtotal"].sum().sort_values(ascending=False).reset_index()
        pg["% Acum"] = (pg["Valor pendiente subtotal"] / vp * 100).cumsum()
        num_clientes = len(pg)
        hasta_80 = (pg["% Acum"] <= 80).sum()
        top3 = pg.head(3)["Valor pendiente subtotal"].sum()/vp*100
        return html.Div([
            html.P([html.Strong("Analisis Pareto - Concentracion de Clientes")], className="fw-bold mb-2"),
            html.Ul([
                html.Li(f"Base de {num_clientes} clientes activos en el periodo."),
                html.Li(f"Se requieren {hasta_80} clientes para alcanzar el 80% del valor total (principio Pareto)."),
                html.Li(f"Los 3 principales clientes concentran el {top3:.1f}% del valor total."),
                html.Li(f"{'ALERTA: Alta concentracion en pocos clientes.' if hasta_80 < 20 else 'Distribucion moderada de clientes.'}"),
            ], style={"paddingLeft": "1.2rem"}),
        ])

    elif page == "ranking":
        rank = data.groupby("Nombre vendedor").agg(Valor=("Valor pendiente subtotal", "sum")).reset_index().sort_values("Valor", ascending=False)
        presupuesto = cargar_presupuesto()
        rank["Presupuesto"] = rank["Nombre vendedor"].apply(lambda x: presupuesto.get(mapear_asesor_presupuesto(x, presupuesto), 0))
        rank["% Presup"] = rank.apply(lambda r: round(r["Valor"]/r["Presupuesto"]*100, 2) if r["Presupuesto"]>0 else 0, axis=1)
        top = rank.iloc[0]
        cnst = data[data["CANAL DISTRIBUCION"]=="CNST - CONSTRUCCION"]
        vp_cnst = cnst["Valor pendiente subtotal"].sum()
        return html.Div([
            html.P([html.Strong("Analisis de Ranking de Asesores")], className="fw-bold mb-2"),
            html.Ul([
                html.Li(f"#{1} {top['Nombre vendedor']}: {fmt_p(top['Valor'])} — {top['% Presup']:.1f}% del presupuesto."),
                html.Li(f"Canal Construccion: {fmt_p(vp_cnst)} distribuido entre {cnst['Nombre vendedor'].nunique()} asesores."),
                html.Li(f"Total de {len(rank)} asesores con actividad en el periodo."),
            ], style={"paddingLeft": "1.2rem"}),
        ])

    elif page == "embudo":
        funnel = data.groupby("Estado movto.").agg(Valor=("Valor pendiente subtotal", "sum"), Pedidos=("Nro documento", "nunique")).reset_index()
        total = funnel["Valor"].sum()
        comprometido = funnel[funnel["Estado movto."].str.contains("Comprometido", na=False)]["Valor"].sum() if not funnel.empty else 0
        en_proc = funnel[funnel["Estado movto."].isin(["En elaboracion", "Aprobado"])]["Valor"].sum() if not funnel.empty else 0
        retenido = funnel[funnel["Estado movto."]=="Retenido"]["Valor"].sum() if not funnel.empty else 0
        tasa_cierre = comprometido/total*100 if total else 0
        return html.Div([
            html.P([html.Strong("Analisis del Embudo de Pedidos")], className="fw-bold mb-2"),
            html.Ul([
                html.Li(f"Tasa de cierre: {tasa_cierre:.1f}% del valor total logra estado Comprometido."),
                html.Li(f"Valor en proceso (Elaboracion + Aprobado): {fmt_p(en_proc)} ({en_proc/total*100:.1f}%)."),
                html.Li(f"Valor retenido: {fmt_p(retenido)} ({retenido/total*100:.1f}%) — {'requiere atencion' if retenido/total*100 > 10 else 'gestion normal'}."),
            ], style={"paddingLeft": "1.2rem"}),
        ])

    elif page == "heatmap":
        heat = data.copy()
        heat["Mes_Anio"] = heat["Fecha"].dt.to_period("M").astype(str)
        pivot = heat.pivot_table(index="Nombre vendedor", columns="Mes_Anio", values="Valor pendiente subtotal", aggfunc="sum").fillna(0)
        if pivot.empty:
            return html.Div("Datos insuficientes para analisis de calor.", className="text-muted")
        total_asesor = pivot.sum(axis=1).sort_values(ascending=False)
        meses_ranking = pivot.sum(axis=0).sort_values(ascending=False)
        top_asesor_name = total_asesor.index[0]
        top_asesor_val = total_asesor.iloc[0]
        mejor_mes = meses_ranking.index[0]
        mejor_mes_val = meses_ranking.iloc[0]
        prom = pivot.values.mean()
        return html.Div([
            html.P([html.Strong("Analisis del Heatmap de Rendimiento")], className="fw-bold mb-2"),
            html.Ul([
                html.Li(f"Asesor lider: {top_asesor_name} con {fmt_p(top_asesor_val)} en {len(pivot.columns)} meses."),
                html.Li(f"Mes de mayor actividad: {mejor_mes} con {fmt_p(mejor_mes_val)}."),
                html.Li(f"Promedio mensual por asesor: {fmt_p(prom)}."),
            ], style={"paddingLeft": "1.2rem"}),
        ])

    elif page == "proyeccion":
        evol = data.groupby(data["Fecha"].dt.to_period("M")).agg(Valor=("Valor pendiente subtotal", "sum")).reset_index()
        if len(evol) < 3:
            return html.Div("Se requieren al menos 3 meses para proyectar.", className="text-muted")
        evol["Periodo"] = range(len(evol))
        coef = np.polyfit(evol["Periodo"], evol["Valor"], 1)
        trend = np.poly1d(coef)
        r2 = np.corrcoef(evol["Periodo"], evol["Valor"])[0,1]**2
        proy = trend(len(evol))
        direccion = "CREciente" if coef[0] > 0 else "DEcreciente"
        presupuesto = cargar_presupuesto()
        total_budget = sum(presupuesto.values()) if presupuesto else 0
        vs_budget = proy/total_budget*100 if total_budget else 0
        return html.Div([
            html.P([html.Strong("Analisis de Proyeccion de Cierre")], className="fw-bold mb-2"),
            html.Ul([
                html.Li(f"Tendencia {direccion} con R²={r2:.3f} ({'ajuste aceptable' if r2>0.5 else 'ajuste debil'})."),
                html.Li(f"Proyeccion de cierre: {fmt_p(proy)}."),
                html.Li(f"Vs presupuesto total: {vs_budget:.1f}%."),
            ], style={"paddingLeft": "1.2rem"}),
        ])

    return html.Div("Pagina no reconocida.", className="text-muted")


# ============================================================
# GEMINI INTEGRATION
# ============================================================
def generar_con_gemini(page, data, api_key):
    if not api_key:
        return None
    prompt = f"""
Eres un analista de datos comerciales. Genera un analisis conciso en 3-4 puntos clave (formato HTML con <ul><li>) para la seccion '{page}' del dashboard con estos datos:

Metricas principales:
- Valor total pendiente: ${data['Valor pendiente subtotal'].sum():,.0f}
- Valor comprometido: ${data['V.COMPROMETIDO'].sum():,.0f}
- Total pedidos: {data['Nro documento'].nunique()}
- Total clientes: {data['Razon social cliente factura'].nunique()}
- Asesores: {data['Nombre vendedor'].nunique()}
- Periodo: {data['Fecha'].min().date()} a {data['Fecha'].max().date()}

Responde SOLO con Markdown: una lista con viñetas usando * al inicio de cada linea.
"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
            resp = requests.post(url, json={"contents":[{"parts":[{"text":prompt}]}]}, timeout=30)
            if resp.ok:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                text = text.replace("```html","").replace("```","").strip()
                return html.Div([
                    html.P([html.Strong(" Analisis con Gemini AI")], className="fw-bold mb-2", style={"color": NAVY}),
                    html.Div(dcc.Markdown(text), className="small"),
                ])
            elif resp.status_code == 429 and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            else:
                return html.Div([
                    html.P([html.Strong(" Gemini no disponible"), html.Span(f" ({resp.status_code})", className="text-muted")],
                            className="fw-bold mb-2", style={"color": AMBER}),
                    html.P("Usando analisis local como respaldo.", className="small text-muted"),
                ])
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return None
    return None


# API verification callback
@callback(
    Output("api-status", "children"),
    Output("store-api-key", "data"),
    Input("btn-verify-api", "n_clicks"),
    State("api-key-input", "value"),
    prevent_initial_call=True,
)
def verify_api(n, key):
    if not key:
        return html.Span("Ingresa una API key primero.", style={"color": AMBER}), ""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
        resp = requests.post(url, json={"contents":[{"parts":[{"text":"OK"}]}]}, timeout=10)
        if resp.ok:
            return html.Span("Conexion exitosa", style={"color": GREEN}), key
        elif resp.status_code == 429:
            return html.Span("Limite de tasa excedido. Key guardada, reintentara automaticamente.", style={"color": AMBER}), key
        else:
            return html.Span(f"Error: {resp.status_code}. Verifica tu API key.", style={"color": RED}), ""
    except Exception as e:
        return html.Span(f"Error de conexion: {e}", style={"color": RED}), ""

SIDEBAR_STYLE = {
    "position": "fixed", "top": 0, "left": 0, "bottom": 0,
    "width": "280px", "padding": "1.2rem 1rem",
    "background": NAVY, "color": "white",
    "overflowY": "auto", "zIndex": 1000,
}
CONTENT_STYLE = {
    "marginLeft": "280px", "padding": "2rem 2.5rem",
    "maxWidth": "1400px",
}

# ============================================================
# NAVIGATION CONFIG
# ============================================================
NAV_ITEMS = [
    ("resumen", " Resumen Ejecutivo"),
    ("participacion", " Participacion"),
    ("pareto", " Pareto"),
    ("ranking", " Ranking"),
    ("embudo", " Embudo"),
    ("heatmap", " Heatmap"),
    ("proyeccion", " Proyeccion"),
]

# ============================================================
# LAYOUT
# ============================================================
def build_sidebar():
    children = [
        html.Div([
            html.H5(" Dashboard Ejecutivo", className="fw-bold", style={"color": "white"}),
            html.Small(f'{df_global["Nro documento"].nunique():,} pedidos' if not df_global.empty else "Sin datos",
                       style={"color": "#94a3b8"}),
        ], className="mb-4"),
        html.H6("Filtros", className="text-uppercase small fw-semibold mb-2 mt-3",
                style={"color": "#94a3b8"}),
    ]

    if not df_global.empty:
        f_min = df_global["Fecha"].min().date()
        f_max = df_global["Fecha"].max().date()
        children.append(html.Div([
            html.Label("Periodo", className="form-label small", style={"color": "white"}),
            dcc.DatePickerRange(
                id="date-range",
                min_date_allowed=f_min,
                max_date_allowed=f_max,
                start_date=f_min,
                end_date=f_max,
                display_format="YYYY-MM-DD",
                className="w-100",
                style={"color": "#333"},
            ),
        ], className="mb-2"))

        asesores = ["Todos"] + sorted(df_global["Nombre vendedor"].dropna().unique())
        canales = ["Todos"] + sorted(df_global["CANAL DISTRIBUCION"].dropna().unique())
        estados = ["Todos"] + sorted(df_global["Estado movto."].dropna().unique())

        children.extend([
            html.Div([
                html.Label("Asesor", className="form-label small", style={"color": "white"}),
                dcc.Dropdown(id="dropdown-asesor", options=[{"label": a, "value": a} for a in asesores],
                             value="Todos", clearable=False, className="small"),
            ], className="mb-2"),
            html.Div([
                html.Label("Canal", className="form-label small", style={"color": "white"}),
                dcc.Dropdown(id="dropdown-canal", options=[{"label": c, "value": c} for c in canales],
                             value="Todos", clearable=False, className="small"),
            ], className="mb-2"),
            html.Div([
                html.Label("Estado", className="form-label small", style={"color": "white"}),
                dcc.Dropdown(id="dropdown-estado", options=[{"label": e, "value": e} for e in estados],
                             value="Todos", clearable=False, className="small"),
            ], className="mb-3"),
        ])

    children.append(html.Hr(style={"borderColor": "rgba(255,255,255,0.15)"}))
    children.append(html.H6("Navegacion", className="text-uppercase small fw-semibold mb-2",
                            style={"color": "#94a3b8"}))

    for key, label in NAV_ITEMS:
        children.append(
            dbc.Button(label, id=f"nav-{key}", color="light",
                       className="text-start w-100 mb-1 rounded-3",
                       style={"fontSize": "0.85rem", "--bs-btn-padding-y": "0.4rem",
                              "--bs-btn-color": NAVY, "--bs-btn-bg": "white",
                              "--bs-btn-hover-bg": "#e2e8f0", "--bs-btn-active-bg": "#cbd5e1"})
        )

    children.append(html.Hr(style={"borderColor": "rgba(255,255,255,0.15)"}))

    # Upload section
    children.extend([
        html.H6(" Cargar archivo SIESA", className="text-uppercase small fw-semibold mb-2",
                style={"color": "#94a3b8"}),
        dcc.Upload(
            id="upload-data",
            children=html.Div(["Arrastra o ", html.A("selecciona .xlsx", style={"color": "#93c5fd"})]),
            className="border border-2 border-dashed rounded-3 p-2 text-center small mb-2",
            style={"cursor": "pointer", "borderColor": "rgba(255,255,255,0.3)", "color": "white"},
        ),
        html.Div(id="file-name", className="small", style={"color": "#93c5fd"}),
        dbc.Button(" Procesar archivo", id="btn-process", color="primary",
                   size="sm", className="w-100 mb-1"),
        html.Div(id="upload-status", style={"fontSize": "0.8rem", "minHeight": "2rem"}),
        html.Hr(style={"borderColor": "rgba(255,255,255,0.15)"}),
        dbc.Button(" Refrescar datos", id="refresh-data", color="light",
                   size="sm", className="w-100 mb-1 text-dark"),
        dbc.Button(" Limpiar datos", id="clear-data", color="danger",
                   size="sm", className="w-100 mb-1"),
        html.Div(id="clear-status", style={"fontSize": "0.8rem", "minHeight": "1.5rem"}),
        html.Hr(style={"borderColor": "rgba(255,255,255,0.15)"}),
        html.H6(" Gemini AI", className="text-uppercase small fw-semibold mb-2",
                style={"color": "#94a3b8"}),
        dbc.Input(id="api-key-input", type="password", placeholder="API Key Gemini",
                  size="sm", className="mb-1", style={"fontSize": "0.8rem"}),
        dbc.Button(" Verificar API", id="btn-verify-api", color="success",
                   size="sm", className="w-100 mb-1"),
        html.Div(id="api-status", style={"fontSize": "0.75rem", "color": "#94a3b8", "minHeight": "1.2rem"}),
        dcc.Store(id="store-api-key", data=""),
        html.Hr(style={"borderColor": "rgba(255,255,255,0.15)"}),
        html.Div(id="sidebar-info", className="small", style={"color": "#94a3b8"}),
    ])

    return html.Div(children, style=SIDEBAR_STYLE)

app.layout = html.Div([
    dcc.Store(id="store-page", data="resumen"),
    dcc.Store(id="store-filters", data={}),
    dcc.Store(id="store-refresh", data=0),
    dcc.Store(id="store-clear", data=0),
    build_sidebar(),
    html.Div(id="page-content", style=CONTENT_STYLE),
])

# ============================================================
# CALLBACKS
# ============================================================

# ── Navigation ──
@callback(
    Output("store-page", "data"),
    [Input(f"nav-{key}", "n_clicks") for key, _ in NAV_ITEMS],
    prevent_initial_call=True,
)
def navigate(*args):
    ctx = dash.ctx
    if not ctx.triggered:
        return no_update
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    return triggered_id.replace("nav-", "")

# ── Filters ──
@callback(
    Output("store-filters", "data"),
    Input("date-range", "start_date"),
    Input("date-range", "end_date"),
    Input("dropdown-asesor", "value"),
    Input("dropdown-canal", "value"),
    Input("dropdown-estado", "value"),
)
def update_filters(start, end, asesor, canal, estado):
    return {
        "rango": [start, end] if start and end else [],
        "asesor": asesor or "Todos",
        "canal": canal or "Todos",
        "estado": estado or "Todos",
    }

# ── Upload + Process ──
@callback(
    Output("file-name", "children"),
    Input("upload-data", "filename"),
)
def show_file_name(filename):
    if filename:
        return f" Archivo: {filename}"
    return ""

@callback(
    Output("upload-status", "children"),
    Output("store-refresh", "data"),
    Input("btn-process", "n_clicks"),
    State("upload-data", "contents"),
    State("upload-data", "filename"),
    State("store-refresh", "data"),
    prevent_initial_call=True,
)
def process_upload(n, contents, filename, refresh_count):
    if not contents or not filename:
        return html.Div("Selecciona un archivo .xlsx primero.", style={"color": AMBER}), no_update
    if not filename.endswith(".xlsx"):
        return html.Div("Solo archivos .xlsx son soportados.", style={"color": RED}), no_update
    try:
        content_type, content_string = contents.split(",")
        decoded = base64.b64decode(content_string)
        CARPETA_ENTRADA.mkdir(parents=True, exist_ok=True)
        ruta = CARPETA_ENTRADA / filename
        with open(ruta, "wb") as f:
            f.write(decoded)
        import main as _main
        _main.procesar(str(ruta))
        if not ARCHIVO_BASE.exists():
            return html.Div("Error: No se genero la base de datos.", style={"color": RED}), no_update
        global df_global
        df_global = cargar_base()
        nreg = len(df_global)
        return html.Div([
            html.Div(f"OK: {filename}", style={"color": "#93c5fd"}),
            html.Div(f"{nreg:,} registros en base", style={"color": GREEN, "fontWeight": "bold"}),
        ]), refresh_count + 1
    except Exception as e:
        detalle = traceback.format_exc()
        print(detalle)
        return html.Div([
            html.Div("Error procesando archivo", style={"color": RED, "fontWeight": "bold"}),
            html.Div(str(e), className="small", style={"color": "#f87171"}),
        ]), no_update

# ── Clear data ──
@callback(
    Output("clear-status", "children"),
    Output("store-clear", "data"),
    Input("clear-data", "n_clicks"),
    State("store-clear", "data"),
    prevent_initial_call=True,
)
def clear_data(n, clear_count):
    global df_global
    if ARCHIVO_BASE.exists():
        ARCHIVO_BASE.unlink()
    df_global = pd.DataFrame()
    return html.Div("Base limpiada. Carga un nuevo archivo.", style={"color": AMBER}), (clear_count or 0) + 1

# ── Sidebar info ──
@callback(
    Output("sidebar-info", "children"),
    Input("refresh-data", "n_clicks"),
    Input("store-refresh", "data"),
    Input("store-clear", "data"),
    Input("store-filters", "data"),
)
def update_sidebar_info(n, _refresh, _clear, filters):
    global df_global
    if df_global.empty:
        df_global = cargar_base()
    if df_global.empty:
        return "Sin datos"
    d = apply_filters(df_global, filters)
    ts = datetime.fromtimestamp(ARCHIVO_BASE.stat().st_mtime).strftime("%Y-%m-%d %H:%M") if ARCHIVO_BASE.exists() else "N/A"
    return html.Div([
        html.Div(f"Base: {len(df_global):,} registros"),
        html.Div(f"Mostrando: {len(d):,}"),
        html.Div(f"Actualizada: {ts}", style={"color": GREEN}),
    ])

# ── Update dropdown options on data refresh ──
@callback(
    Output("dropdown-asesor", "options"),
    Output("dropdown-canal", "options"),
    Output("dropdown-estado", "options"),
    Input("store-refresh", "data"),
    Input("store-clear", "data"),
)
def update_dropdowns(_refresh, _clear):
    global df_global
    if df_global.empty:
        df_global = cargar_base()
    if df_global.empty:
        return [{"label": "Sin datos", "value": "Todos"}], [{"label": "Sin datos", "value": "Todos"}], [{"label": "Sin datos", "value": "Todos"}]
    asesores = [{"label": a, "value": a} for a in sorted(df_global["Nombre vendedor"].dropna().unique())]
    canales = [{"label": c, "value": c} for c in sorted(df_global["CANAL DISTRIBUCION"].dropna().unique())]
    estados = [{"label": e, "value": e} for e in sorted(df_global["Estado movto."].dropna().unique())]
    return asesores, canales, estados

# ── Page content ──
@callback(
    Output("page-content", "children"),
    Input("store-page", "data"),
    Input("store-filters", "data"),
    Input("refresh-data", "n_clicks"),
    Input("store-refresh", "data"),
    Input("store-clear", "data"),
)
def render_page(page, filters, _n, _refresh, _clear):
    global df_global
    if df_global.empty:
        df_global = cargar_base()
    data = apply_filters(df_global, filters)
    if data.empty:
        return dmc.Alert("Procesa un archivo con el upload del sidebar.", title="Sin datos", color="yellow", withCloseButton=True)
    page_map = {
        "resumen": pagina_resumen,
        "participacion": pagina_participacion,
        "pareto": pagina_pareto,
        "ranking": pagina_ranking,
        "embudo": pagina_embudo,
        "heatmap": pagina_heatmap,
        "proyeccion": pagina_proyeccion,
    }
    fn = page_map.get(page)
    if not fn:
        return html.Div("Pagina no encontrada.")
    try:
        return fn(data)
    except Exception as e:
        print(f"Error en pagina_{page}: {traceback.format_exc()}")
        return dmc.Alert([
            html.Div(f"Error al renderizar pagina: {str(e)}", style={"fontWeight": "bold"}),
            html.Div("Revisa la consola para mas detalles.", className="small text-muted mt-1"),
        ], title=f"Error en {page}", color="red", withCloseButton=True)

# ============================================================
# PAGE FUNCTIONS
# ============================================================

def section_title(title, sub=""):
    return html.Div([
        html.H4(title, className="fw-bold", style={"color": NAVY,
                 "borderBottom": f"3px solid {BLUE}", "display": "inline-block"}),
        html.P(sub, className="text-muted small") if sub else "",
    ], className="mb-3")

# ============================================================
# CALLBACKS - ANALISIS AUTOMATICO
# ============================================================
PAGE_KEYS = [key for key, _ in NAV_ITEMS]

@callback(
    [Output(f"analisis-{key}", "children") for key in PAGE_KEYS],
    [Input(f"btn-analisis-{key}", "n_clicks") for key in PAGE_KEYS],
    State("store-filters", "data"),
    State("store-api-key", "data"),
    prevent_initial_call=True,
)
def generate_analysis(*args):
    try:
        filters = args[-2]
        api_key = args[-1]
        ctx = dash.ctx
        if not ctx.triggered:
            return [no_update] * len(PAGE_KEYS)
        triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
        page = triggered_id.replace("btn-analisis-", "")
        global df_global
        data = apply_filters(df_global, filters)
        if data.empty:
            result = html.Div("Sin datos para analizar.", className="text-muted")
        else:
            if api_key:
                gemini_result = generar_con_gemini(page, data, api_key)
                result = gemini_result if gemini_result else generar_analisis(page, data)
            else:
                result = generar_analisis(page, data)
        outputs = [no_update] * len(PAGE_KEYS)
        idx = PAGE_KEYS.index(page)
        outputs[idx] = result
        return outputs
    except Exception as e:
        print(f"Error en generate_analysis: {traceback.format_exc()}")
        outputs = [no_update] * len(PAGE_KEYS)
        outputs[0] = html.Div(f"Error: {e}", style={"color": RED})
        return outputs

# ============================================================
# PAGE FUNCTIONS
# ============================================================

def pagina_resumen(data):
    vp = data["Valor pendiente subtotal"].sum()
    vc = data["V.COMPROMETIDO"].sum()
    total_pedidos = data["Nro documento"].nunique()
    total_clientes = data["Razon social cliente factura"].nunique()
    cant_pedida = data["Cant. pedida"].sum()
    cant_pendiente = data["Cant. pendiente"].sum()
    pct_pend = (cant_pendiente / cant_pedida * 100) if cant_pedida else 0
    num_asesores = data["Nombre vendedor"].nunique()
    promedio_cliente = vp / total_clientes if total_clientes else 0
    promedio_pedido = vp / total_pedidos if total_pedidos else 0

    children = [section_title(" Resumen Ejecutivo", "Indicadores principales y tendencia general")]

    # KPI cards (first row)
    kpi_row = dbc.Row([
        dbc.Col(kpi_card("Valor Total", fmt_p(vp), fmt_pm(vp)), width=3),
        dbc.Col(kpi_card("Pedidos", f"{total_pedidos:,}", f"{cant_pedida:,.0f} unidades"), width=3),
        dbc.Col(kpi_card("Clientes Activos", f"{total_clientes}", f"{num_asesores} asesores"), width=3),
        dbc.Col(kpi_card("Valor Pendiente", fmt_p(vp), f"{pct_pend:.2f}% del pedido"), width=3),
    ], className="mb-4 g-3")
    children.append(kpi_row)

    # Second row: 4 KPI cards with more detail
    kpi2 = dbc.Row([
        dbc.Col(kpi_card("Promedio x Cliente", fmt_p(promedio_cliente), fmt_pm(promedio_cliente)), width=3),
        dbc.Col(kpi_card("Promedio x Pedido", fmt_p(promedio_pedido), fmt_pm(promedio_pedido)), width=3),
        dbc.Col(kpi_card("Cumplimiento", f"{vc/vp*100:.2f}%" if vp else "0%", f"{fmt_p(vc)} comprometido"), width=3),
        dbc.Col(kpi_card("Construccion", f"{data[data['CANAL DISTRIBUCION']=='CNST - CONSTRUCCION']['Valor pendiente subtotal'].sum()/vp*100:.2f}%" if vp else "0%", "% del total"), width=3),
    ], className="mb-4 g-3")
    children.append(kpi2)

    # Evolucion mensual
    evol = data.groupby(data["Fecha"].dt.to_period("M")).agg(
        Valor_pendiente=("Valor pendiente subtotal", "sum"),
        Comprometido=("V.COMPROMETIDO", "sum"),
        Pedidos=("Nro documento", "nunique"),
    ).reset_index()
    evol["Fecha"] = evol["Fecha"].astype(str)

    fig_evol = go.Figure()
    fig_evol.add_trace(go.Scatter(x=evol["Fecha"], y=evol["Valor_pendiente"]/1e6,
        mode="lines+markers", name="Valor Pendiente",
        line=dict(width=3, color=BLUE), marker=dict(size=6, color=BLUE)))
    fig_evol.add_trace(go.Scatter(x=evol["Fecha"], y=evol["Comprometido"]/1e6,
        mode="lines+markers", name="Comprometido",
        line=dict(width=3, color=GREEN), marker=dict(size=6, color=GREEN)))
    fig_evol.update_layout(**fig_layout("Evolucion Mensual (millones $)", height=380))
    fig_evol.update_layout(legend=dict(orientation="h", y=1.1, x=0.7))
    fig_evol.update_xaxes(tickangle=-45)

    # Top asesores bar chart
    top_asesores = data.groupby("Nombre vendedor").agg(
        Valor=("Valor pendiente subtotal", "sum"),
    ).reset_index().sort_values("Valor", ascending=True).tail(10)

    fig_asesores = go.Figure()
    fig_asesores.add_trace(go.Bar(x=top_asesores["Valor"]/1e6, y=top_asesores["Nombre vendedor"],
        orientation="h", marker_color=BLUE,
        text=[fmt_pm(v) for v in top_asesores["Valor"]], textposition="outside"))
    fig_asesores.update_layout(**fig_layout("Top 10 Asesores (millones $)", height=380))
    fig_asesores.update_xaxes(title="$ millones")

    # Right card with indicators + monthly table
    part_const = (data[data["CANAL DISTRIBUCION"]=="CNST - CONSTRUCCION"]["Valor pendiente subtotal"].sum()/vp*100) if vp else 0
    top3 = data.groupby("Razon social cliente factura")["Valor pendiente subtotal"].sum().sort_values(ascending=False)
    top3_pct = (top3.iloc[:3].sum()/vp*100) if vp else 0
    cumpl_val = (vc/vp*100) if vp else 0

    evol_table = dash_table.DataTable(
        columns=[{"name": c, "id": c} for c in ["Mes", "Valor", "Comprometido", "Pedidos"]],
        data=[{
            "Mes": r["Fecha"],
            "Valor": fmt_p(r["Valor_pendiente"]),
            "Comprometido": fmt_p(r["Comprometido"]),
            "Pedidos": f"{int(r['Pedidos']):,}",
        } for _, r in evol.tail(12).iterrows()],
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.8rem"},
        style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
        page_size=6,
    )

    right_card = dmc.Card([
        dmc.CardSection([
            html.H6("Evolucion Mensual", className="fw-bold"),
            evol_table,
            html.Hr(),
            html.H6("Indicadores Clave", className="fw-bold"),
            html.Div([html.Span("% Canal Construccion: ", className="text-muted"), html.Strong(f"{part_const:.2f}%")]),
            html.Div([html.Span("Top 3 Clientes concentran: ", className="text-muted"), html.Strong(f"{top3_pct:.2f}%")]),
            html.Div([html.Span("% Cumplimiento: ", className="text-muted"), html.Strong(f"{cumpl_val:.2f}%")]),
            html.Div([html.Span("Asesores: ", className="text-muted"), html.Strong(str(num_asesores))]),
            html.Div([html.Span("Lineas de producto: ", className="text-muted"), html.Strong(str(data["LINEA"].nunique()))]),
        ])
    ], withBorder=True, shadow="sm", padding="lg", radius="md", className="h-100")

    children.append(dbc.Row([
        dbc.Col(dcc.Graph(figure=fig_evol, style={"height": "420px"}), width=7),
        dbc.Col(right_card, width=5),
    ], className="mb-4 g-3"))

    # Top 10 Clientes + Top Asesores
    top10 = data.groupby("Razon social cliente factura").agg(
        Valor=("Valor pendiente subtotal", "sum"),
    ).reset_index().sort_values("Valor", ascending=False).head(10)
    top10["% Participacion"] = (top10["Valor"] / vp * 100).round(2)
    top10["% Acumulado"] = top10["% Participacion"].cumsum()
    top10.insert(0, "Ranking", range(1, len(top10)+1))

    top10_table = dash_table.DataTable(
        columns=[{"name": c, "id": c} for c in ["Ranking", "Razon social cliente factura", "Valor", "% Participacion", "% Acumulado"]],
        data=top10.to_dict("records"),
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.8rem"},
        style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
        style_data_conditional=[
            {"if": {"filter_query": "{Ranking} = 1"}, "backgroundColor": "#FFF8DC"},
            {"if": {"filter_query": "{Ranking} = 2"}, "backgroundColor": "#F0F0F0"},
            {"if": {"filter_query": "{Ranking} = 3"}, "backgroundColor": "#FFF0E0"},
        ],
        page_size=10,
    )

    # Distribucion por canal
    dist = data.groupby("CANAL DISTRIBUCION").agg(
        Valor=("Valor pendiente subtotal", "sum"),
        Pedidos=("Nro documento", "nunique"),
        Clientes=("Razon social cliente factura", "nunique"),
    ).reset_index()
    dist["% Participacion"] = (dist["Valor"] / vp * 100).round(2)
    dist = dist.sort_values("Valor", ascending=False)

    dist_table = dash_table.DataTable(
        columns=[{"name": c, "id": c} for c in ["CANAL DISTRIBUCION", "Valor", "% Participacion", "Pedidos", "Clientes"]],
        data=dist.to_dict("records"),
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.8rem"},
        style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
        page_size=10,
    )

    children.append(html.H6("Top 10 Clientes y Distribucion", className="fw-bold mt-4", style={"color": NAVY}))
    children.append(dbc.Row([
        dbc.Col(top10_table, width=7),
        dbc.Col(dmc.Card([
            dmc.CardSection([
                html.H6("Distribucion por Canal", className="fw-bold"),
                dist_table,
            ])
        ], withBorder=True, shadow="sm", padding="lg", radius="md"), width=5),
    ], className="mb-4 g-3"))

    # Radar chart: perfil multidimensional de top asesores
    top_n_radar = 5
    asesor_metrics = data.groupby("Nombre vendedor").agg(
        Valor=("Valor pendiente subtotal", "sum"),
        Comprometido=("V.COMPROMETIDO", "sum"),
        Pedidos=("Nro documento", "nunique"),
        Clientes=("Razon social cliente factura", "nunique"),
    ).reset_index()
    asesor_metrics["% Cumpl"] = (asesor_metrics["Comprometido"] / asesor_metrics["Valor"] * 100).round(2)
    cnst_asesor = data[data["CANAL DISTRIBUCION"]=="CNST - CONSTRUCCION"].groupby("Nombre vendedor").agg(
        Valor_cnst=("Valor pendiente subtotal", "sum"),
    ).reset_index()
    asesor_metrics = asesor_metrics.merge(cnst_asesor, on="Nombre vendedor", how="left").fillna(0)
    asesor_metrics["% Construccion"] = (asesor_metrics["Valor_cnst"] / asesor_metrics["Valor"] * 100).round(2)
    presupuesto = cargar_presupuesto()
    asesor_metrics["Presupuesto"] = asesor_metrics["Nombre vendedor"].apply(
        lambda x: presupuesto.get(mapear_asesor_presupuesto(x, presupuesto), 0)
    )
    asesor_metrics["% Presupuesto"] = asesor_metrics.apply(
        lambda r: round(r["Valor"] / r["Presupuesto"] * 100, 2) if r["Presupuesto"] > 0 else 0, axis=1
    )
    top_asesores_radar = asesor_metrics.sort_values("Valor", ascending=False).head(top_n_radar)

    # Normalize metrics to 0-100 for radar
    def norm(s):
        mx = s.max()
        return (s / mx * 100).round(1) if mx else s
    radar_data = top_asesores_radar.copy()
    radar_data["Valor_norm"] = norm(radar_data["Valor"])
    radar_data["Pedidos_norm"] = norm(radar_data["Pedidos"])
    radar_data["Clientes_norm"] = norm(radar_data["Clientes"])

    categories = ["Valor", "Cumplimiento", "Pedidos", "Clientes", "% Presupuesto", "% Construccion"]
    cat_map = {
        "Valor": "Valor_norm", "Cumplimiento": "% Cumpl",
        "Pedidos": "Pedidos_norm", "Clientes": "Clientes_norm",
        "% Presupuesto": "% Presupuesto", "% Construccion": "% Construccion",
    }

    radar_fig = go.Figure()
    for _, r in radar_data.iterrows():
        vals = [r[cat_map[c]] for c in categories]
        vals += vals[:1]
        radar_fig.add_trace(go.Scatterpolar(r=vals, theta=categories + [categories[0]],
            fill="toself", name=r["Nombre vendedor"],
            line=dict(width=2)))
    radar_fig.update_layout(**fig_layout("Perfil Multidimensional - Top 5 Asesores", height=420),
        polar=dict(radialaxis=dict(visible=True, range=[0, 100], gridcolor="#e2e8f0")),
        legend=dict(orientation="h", y=1.08, font=dict(size=9)))

    # Insight cards for alta gerencia
    mes_actual_name = data["Fecha"].max().strftime("%B %Y") if not data.empty else ""
    mes_anterior_date = data["Fecha"].max() - pd.DateOffset(months=1) if not data.empty else None
    if mes_anterior_date is not None:
        data_mes_ant = data[data["Fecha"].dt.to_period("M") == mes_anterior_date.to_period("M")]
        vp_mes_ant = data_mes_ant["Valor pendiente subtotal"].sum()
    else:
        vp_mes_ant = 0
    vp_mes_act = evol.iloc[-1]["Valor_pendiente"] if len(evol) > 0 else 0
    cambio_mensual = ((vp_mes_act - vp_mes_ant) / vp_mes_ant * 100) if vp_mes_ant else 0

    top_cliente = data.groupby("Razon social cliente factura")["Valor pendiente subtotal"].sum().idxmax()
    top_cliente_val = data.groupby("Razon social cliente factura")["Valor pendiente subtotal"].sum().max()
    top_asesor_nombre = top_asesores_radar.iloc[0]["Nombre vendedor"]
    top_asesor_cumpl = top_asesores_radar.iloc[0]["% Cumpl"]

    # Insight icons - using solo BMP characters for orjson compatibility
    insight_icon_up = html.Span("\u25B3", style={"fontSize": "1.2rem", "marginRight": "6px"})  # △
    insight_icon_down = html.Span("\u25BD", style={"fontSize": "1.2rem", "marginRight": "6px"})  # ▽
    insight_icon_target = html.Span("\u25C6", style={"fontSize": "1.2rem", "marginRight": "6px"})  # ◆
    insight_icon_star = html.Span("\u2605", style={"fontSize": "1.2rem", "marginRight": "6px"})  # ★

    insight_cards = dmc.Card([
        dmc.CardSection([
            html.H6("Insights para Alta Gerencia", className="fw-bold mb-3",
                    style={"color": NAVY, "borderBottom": f"2px solid {BLUE}", "paddingBottom": "8px"}),
            *[
                dmc.Card([
                    dmc.CardSection([
                        html.Div([icon, html.Strong(title, style={"fontSize": "0.85rem"})],
                                 style={"display": "flex", "alignItems": "center", "marginBottom": "4px"}),
                        html.Div(body, className="small text-muted"),
                    ])
                ], withBorder=True, shadow="xs", padding="sm", radius="md",
                   style={"marginBottom": "8px", "borderLeft": f"4px solid {color}"})
                for icon, title, body, color in [
                    (insight_icon_up, "Tendencia Mensual",
                     f"{'+' if cambio_mensual>0 else ''}{cambio_mensual:.1f}% vs mes anterior. "
                     f"Valor del mes: {fmt_pm(vp_mes_act)}",
                     GREEN if cambio_mensual >= 0 else RED),
                    (insight_icon_star, "Cliente Estrella",
                     f"{top_cliente[:45]} concentra {fmt_pm(top_cliente_val)} "
                     f"({top_cliente_val/vp*100:.1f}% del total)",
                     AMBER),
                    (insight_icon_target, "Mejor Asesor",
                     f"{top_asesor_nombre}: {fmt_pm(top_asesores_radar.iloc[0]['Valor'])} "
                     f"con {top_asesor_cumpl:.1f}% de cumplimiento",
                     BLUE),
                    (insight_icon_down, "Oportunidad Construccion",
                     f"Canal CNST representa {part_const:.1f}% del valor total. "
                     f"{data[data['CANAL DISTRIBUCION']=='CNST - CONSTRUCCION']['Nombre vendedor'].nunique()} asesores activos.",
                     NAVY),
                ]
            ],
        ])
    ], withBorder=True, shadow="sm", padding="md", radius="md", className="h-100",
       style={"backgroundColor": "#ffffff"})

    children.append(html.H6("Analisis Multidimensional", className="fw-bold mt-4", style={"color": NAVY}))
    children.append(dbc.Row([
        dbc.Col(dcc.Graph(figure=radar_fig, style={"height": "460px"}), width=7),
        dbc.Col(insight_cards, width=5),
    ], className="mb-4 g-3"))

    # -- Analisis Automatico --
    children.append(html.Hr())
    children.append(html.Div([
        html.H6(" Analisis Automatico", className="fw-bold", style={"color": NAVY}),
        dbc.Button(" Generar Analisis", id="btn-analisis-resumen", color="secondary", size="sm", className="mb-2"),
        html.Div(id="analisis-resumen", className="small p-3",
                 style={"backgroundColor": "#f8fafc", "borderRadius": "8px", "border": "1px solid #e2e8f0", "minHeight": "60px"}),
    ], className="mt-4"))

    return children

def pagina_participacion(data):
    children = [section_title(" Participacion Comercial",
                 "Distribucion del valor por asesor, canal y estructura")]

    # Asesor
    asesor = data.groupby("Nombre vendedor").agg(
        Valor=("Valor pendiente subtotal", "sum")
    ).reset_index().sort_values("Valor", ascending=False)
    fig_asesor = go.Figure()
    fig_asesor.add_trace(go.Bar(x=asesor["Valor"]/1e6, y=asesor["Nombre vendedor"],
        orientation="h", marker_color=COLORS,
        text=[fmt_pm(v) for v in asesor["Valor"]], textposition="outside"))
    fig_asesor.update_layout(**fig_layout("Por Asesor (millones $)", height=360))
    fig_asesor.update_xaxes(title="$ millones")

    # Canal
    canal = data.groupby("CANAL DISTRIBUCION").agg(Valor=("Valor pendiente subtotal", "sum")).reset_index()
    canal = canal[canal["Valor"] > 0]
    fig_canal = px.pie(canal, values="Valor", names="CANAL DISTRIBUCION",
                       hole=0.45, color_discrete_sequence=COLORS)
    fig_canal.update_traces(textinfo="label+percent", textposition="outside")
    fig_canal.update_layout(**fig_layout("Por Canal", height=360), showlegend=False)

    children.append(dbc.Row([
        dbc.Col(dcc.Graph(figure=fig_asesor, style={"height": "400px"}), width=6),
        dbc.Col(dcc.Graph(figure=fig_canal, style={"height": "400px"}), width=6),
    ], className="mb-3 g-3"))

    # Estructura
    linea = data.groupby("LINEA").agg(Valor=("Valor pendiente subtotal", "sum")).reset_index()
    linea = linea[linea["Valor"] > 0].sort_values("Valor", ascending=True).tail(15)
    fig_linea = go.Figure()
    fig_linea.add_trace(go.Bar(x=linea["Valor"]/1e6, y=linea["LINEA"],
        orientation="h", marker_color=BLUE,
        text=[fmt_pm(v) for v in linea["Valor"]], textposition="outside"))
    fig_linea.update_layout(**fig_layout("Por Linea de Producto (millones $)", height=400))
    fig_linea.update_xaxes(title="$ millones")

    # Tabla
    resumen = data.groupby("CANAL DISTRIBUCION").agg(
        Valor=("Valor pendiente subtotal", "sum"),
        Comprometido=("V.COMPROMETIDO", "sum"),
        Pedidos=("Nro documento", "nunique"),
        Clientes=("Razon social cliente factura", "nunique"),
    ).reset_index()
    resumen["% Participacion"] = (resumen["Valor"] / resumen["Valor"].sum() * 100).round(2)
    resumen = resumen.sort_values("Valor", ascending=False)

    canal_table = dash_table.DataTable(
        columns=[{"name": c, "id": c} for c in ["CANAL DISTRIBUCION", "Valor", "Comprometido", "% Participacion", "Pedidos", "Clientes"]],
        data=resumen.to_dict("records"),
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.8rem"},
        style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
        page_size=10,
    )

    asesor_resumen = data.groupby("Nombre vendedor").agg(
        Valor=("Valor pendiente subtotal", "sum"),
        Pedidos=("Nro documento", "nunique"),
        Clientes=("Razon social cliente factura", "nunique"),
    ).reset_index().sort_values("Valor", ascending=False)
    asesor_resumen["% Participacion"] = (asesor_resumen["Valor"] / asesor_resumen["Valor"].sum() * 100).round(2)

    asesor_table = dash_table.DataTable(
        columns=[{"name": c, "id": c} for c in ["Nombre vendedor", "Valor", "% Participacion", "Pedidos", "Clientes"]],
        data=asesor_resumen.to_dict("records"),
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.8rem"},
        style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
        page_size=10,
    )

    right_card = dmc.Card([
        dmc.CardSection([
            html.H6("Resumen por Canal", className="fw-bold"),
            canal_table,
            html.Hr(),
            html.H6("Resumen por Asesor", className="fw-bold"),
            asesor_table,
        ])
    ], withBorder=True, shadow="sm", padding="lg", radius="md", className="h-100")

    children.append(dbc.Row([
        dbc.Col(dcc.Graph(figure=fig_linea, style={"height": "440px"}), width=7),
        dbc.Col(right_card, width=5),
    ], className="mb-4 g-3"))

    # -- Analisis Automatico --
    children.append(html.Hr())
    children.append(html.Div([
        html.H6(" Analisis Automatico", className="fw-bold", style={"color": NAVY}),
        dbc.Button(" Generar Analisis", id="btn-analisis-participacion", color="secondary", size="sm", className="mb-2"),
        html.Div(id="analisis-participacion", className="small p-3",
                 style={"backgroundColor": "#f8fafc", "borderRadius": "8px", "border": "1px solid #e2e8f0", "minHeight": "60px"}),
    ], className="mt-4"))

    return children

def pagina_pareto(data):
    children = [section_title(" Pareto de Clientes",
                 "Analisis de concentracion por cliente y por canal")]

    canales = ["TODOS LOS CANALES"] + sorted(data["CANAL DISTRIBUCION"].dropna().unique())

    children.append(html.Div([
        html.Label("Canal:", className="fw-semibold small me-2"),
        dcc.RadioItems(
            id="pareto-canal",
            options=[{"label": c, "value": c} for c in canales],
            value="TODOS LOS CANALES", inline=True,
            inputClassName="me-1", labelClassName="me-3 small",
        ),
    ], className="mb-2"))

    children.append(html.Div([
        html.Label("Top N clientes:", className="fw-semibold small me-2"),
        dcc.Slider(id="pareto-top", min=5, max=50, step=5, value=15,
                   marks={i: str(i) for i in range(5, 55, 5)},
                   className="w-50"),
    ], className="mb-3"))

    children.append(html.Div(id="pareto-content"))
    # -- Analisis Automatico --
    children.append(html.Hr())
    children.append(html.Div([
        html.H6(" Analisis Automatico", className="fw-bold", style={"color": NAVY}),
        dbc.Button(" Generar Analisis", id="btn-analisis-pareto", color="secondary", size="sm", className="mb-2"),
        html.Div(id="analisis-pareto", className="small p-3",
                 style={"backgroundColor": "#f8fafc", "borderRadius": "8px", "border": "1px solid #e2e8f0", "minHeight": "60px"}),
    ], className="mt-4"))
    return children

@callback(
    Output("pareto-content", "children"),
    Input("pareto-canal", "value"),
    Input("pareto-top", "value"),
    Input("store-filters", "data"),
)
def update_pareto(canal, top_n, filters):
    try:
        global df_global
        data = apply_filters(df_global, filters)
        if data.empty:
            return dmc.Alert("Sin datos", title="Aviso", color="yellow", withCloseButton=True)

        if canal == "TODOS LOS CANALES":
            filtro = data
            titulo = "Pareto General"
        else:
            filtro = data[data["CANAL DISTRIBUCION"] == canal]
            titulo = f"Pareto - {canal}"

        if filtro.empty:
            return dmc.Alert(f"No hay datos para {canal}", title="Aviso", color="yellow", withCloseButton=True)

        vp_total = filtro["Valor pendiente subtotal"].sum()
        pg = filtro.groupby("Razon social cliente factura").agg(
            Valor=("Valor pendiente subtotal", "sum"),
        ).reset_index().sort_values("Valor", ascending=False).reset_index(drop=True)
        if pg.empty:
            return dmc.Alert("Sin clientes", title="Aviso", color="yellow", withCloseButton=True)

        pg["% Participacion"] = (pg["Valor"] / vp_total * 100).round(2)
        pg["% Acumulado"] = pg["% Participacion"].cumsum()
        pg.insert(0, "Ranking", range(1, len(pg)+1))
        data_top = pg.head(top_n)

        fig = go.Figure()
        fig.add_trace(go.Bar(x=data_top["Razon social cliente factura"], y=data_top["Valor"],
            marker_color=BLUE, name="Valor Pendiente",
            text=[fmt_pm(v) for v in data_top["Valor"]], textposition="outside"))
        fig.add_trace(go.Scatter(x=data_top["Razon social cliente factura"], y=data_top["% Acumulado"],
            name="% Acumulado", yaxis="y2", marker_color=RED, mode="lines+markers", line=dict(width=3)))
        fig.add_hline(y=80, line_dash="dash", line_color=AMBER, annotation_text="80%", annotation_position="left")
        fig.update_layout(**fig_layout(titulo, height=420,
            yaxis=dict(title="$", gridcolor="#f1f5f9", zeroline=False),
            yaxis2=dict(title="%", overlaying="y", side="right", range=[0, 105])))
        fig.update_xaxes(tickangle=-45)

        top3_sum = pg.head(3)["% Participacion"].sum()
        hasta_80 = (pg["% Acumulado"] <= 80).sum()

        top10 = html.Div([
            html.H6("Top 10 Clientes", className="fw-bold"),
            *[html.Div([
                html.Strong(f"{r['Ranking']}. {r['Razon social cliente factura'][:50]}"),
                html.Div(f"{fmt_p(r['Valor'])} | {r['% Participacion']:.2f}% acum: {r['% Acumulado']:.2f}%",
                         className="text-muted small"),
            ], className="mb-1") for _, r in pg.head(10).iterrows()],
            html.Hr(),
            dbc.Row([
                dbc.Col(dmc.Card([
                    dmc.CardSection([
                        html.Small("Top 3 concentran", className="text-muted d-block"),
                        html.Strong(f"{top3_sum:.2f}%"),
                    ])
                ], withBorder=True, shadow="sm", padding="md", radius="sm", className="text-center mb-2")),
                dbc.Col(dmc.Card([
                    dmc.CardSection([
                        html.Small("Clientes hasta 80%", className="text-muted d-block"),
                        html.Strong(str(hasta_80)),
                    ])
                ], withBorder=True, shadow="sm", padding="md", radius="sm", className="text-center mb-2")),
            ]),
            dmc.Card([
                dmc.CardSection([
                    html.Small("Total Clientes", className="text-muted d-block"),
                    html.Strong(str(len(pg))),
                ])
            ], withBorder=True, shadow="sm", padding="md", radius="sm", className="text-center"),
        ])

        table = dash_table.DataTable(
            columns=[{"name": c, "id": c} for c in ["Ranking", "Razon social cliente factura", "Valor", "% Participacion", "% Acumulado"]],
            data=pg.head(50).to_dict("records"),
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.8rem"},
            style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
            page_size=10,
    )

        return html.Div([
            dbc.Row([
                dbc.Col(dcc.Graph(figure=fig, style={"height": "460px"}), width=8),
                dbc.Col(top10, width=4),
            ], className="mb-3 g-3"),
            html.Div(table, className="mb-4"),
            html.Hr(),
            section_title(" Comparativo por Canal", "Top 10 clientes de cada canal"),
            dbc.Tabs([
                dbc.Tab([
                    build_canal_tab(data, c)
                ], label=c) for c in sorted(data["CANAL DISTRIBUCION"].dropna().unique())
            ]),
        ])
    except Exception as e:
        print(f"Error en update_pareto: {traceback.format_exc()}")
        return dmc.Alert(f"Error: {e}", title="Error", color="red", withCloseButton=True)

def build_canal_tab(data, canal):
    d_canal = data[data["CANAL DISTRIBUCION"] == canal]
    vp_c = d_canal["Valor pendiente subtotal"].sum()
    if vp_c == 0:
        return html.P("Sin datos", className="text-muted")
    pc = d_canal.groupby("Razon social cliente factura").agg(
        Valor=("Valor pendiente subtotal", "sum"),
    ).reset_index().sort_values("Valor", ascending=False).head(10)
    pc["%"] = (pc["Valor"] / vp_c * 100).round(2)

    fig = go.Figure()
    fig.add_trace(go.Bar(x=pc["Razon social cliente factura"], y=pc["Valor"],
        marker_color=COLORS[0], text=[fmt_pm(v) for v in pc["Valor"]], textposition="outside"))
    fig.add_trace(go.Scatter(x=pc["Razon social cliente factura"], y=pc["%"],
        name="%", yaxis="y2", marker_color=RED, mode="lines+markers", line=dict(width=3)))
    fig.update_layout(**fig_layout(f"Top 10 - {canal}", height=350,
        yaxis=dict(title="$", gridcolor="#f1f5f9", zeroline=False),
        yaxis2=dict(title="%", overlaying="y", side="right", range=[0, 105])))
    fig.update_xaxes(tickangle=-45)

    return html.Div([
        dcc.Graph(figure=fig, style={"height": "380px"}),
        dash_table.DataTable(
            columns=[{"name": c, "id": c} for c in ["Razon social cliente factura", "Valor", "%"]],
            data=pc.head(10).to_dict("records"),
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.8rem"},
            style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
        ),
    ])

def pagina_ranking(data):
    children = [section_title(" Ranking de Asesores",
                 "Rendimiento general y participacion en Construccion")]

    rank = data.groupby("Nombre vendedor").agg(
        Valor=("Valor pendiente subtotal", "sum"),
        Comprometido=("V.COMPROMETIDO", "sum"),
        Pedidos=("Nro documento", "nunique"),
        Clientes=("Razon social cliente factura", "nunique"),
    ).reset_index()
    rank["% Cumpl"] = (rank["Comprometido"] / rank["Valor"] * 100).round(2)

    presupuesto = cargar_presupuesto()
    rank["Presupuesto"] = rank["Nombre vendedor"].apply(
        lambda x: presupuesto.get(mapear_asesor_presupuesto(x, presupuesto), 0)
    )
    rank["% Presupuesto"] = rank.apply(
        lambda r: round(r["Valor"] / r["Presupuesto"] * 100, 2) if r["Presupuesto"] > 0 else 0, axis=1
    )

    rank = rank.sort_values("Valor", ascending=False)
    rank.index = range(1, len(rank) + 1)
    rank_display = rank.copy()
    rank_display["#"] = rank_display.index
    rank_display["Valor"] = rank_display["Valor"].apply(fmt_p)
    rank_display["Comprometido"] = rank_display["Comprometido"].apply(fmt_p)
    rank_display["Presupuesto"] = rank_display["Presupuesto"].apply(fmt_p)
    rank_display["% Presupuesto"] = rank_display["% Presupuesto"].apply(lambda x: f"{x:.2f}%")
    rank_display["% Cumpl"] = rank_display["% Cumpl"].apply(lambda x: f"{x:.2f}%")

    rank_table = dash_table.DataTable(
        columns=[{"name": c, "id": c} for c in ["#", "Nombre vendedor", "Valor", "Presupuesto", "% Presupuesto", "% Cumpl", "Pedidos", "Clientes"]],
        data=rank_display.to_dict("records"),
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.8rem"},
        style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
        style_data_conditional=[
            {"if": {"filter_query": "{#} = 1"}, "backgroundColor": "#FFF8DC"},
            {"if": {"filter_query": "{#} = 2"}, "backgroundColor": "#F0F0F0"},
            {"if": {"filter_query": "{#} = 3"}, "backgroundColor": "#FFF0E0"},
        ],
    )

    fig_rank = go.Figure()
    fig_rank.add_trace(go.Bar(x=[v/1e6 for v in rank["Valor"]], y=rank["Nombre vendedor"],
        orientation="h", marker_color=COLORS[:len(rank)],
        text=[fmt_pm(v) for v in rank["Valor"]], textposition="outside"))
    fig_rank.update_layout(**fig_layout("Ranking General - Valor Total (millones $)", height=360))
    fig_rank.update_xaxes(title="$ millones")
    fig_rank.update_yaxes(categoryorder="total descending")

    children.append(build_podium(rank, " Podio General", "Valor", "% Presupuesto"))
    children.append(dbc.Row([
        dbc.Col(dcc.Graph(figure=fig_rank, style={"height": "400px"}), width=7),
        dbc.Col(dmc.Card([
            dmc.CardSection([html.H6("Resumen por Asesor", className="fw-bold"), rank_table])
        ], withBorder=True, shadow="sm", padding="lg", radius="md", className="h-100"), width=5),
    ], className="mb-4 g-3"))

    # Ranking Construccion
    children.append(html.Hr())
    children.append(section_title(" Ranking Canal Construccion",
         "Participacion de cada asesor en CNST - CONSTRUCCION con variacion"))

    cnst = data[data["CANAL DISTRIBUCION"] == "CNST - CONSTRUCCION"].copy()
    vp_cnst = cnst["Valor pendiente subtotal"].sum()

    if vp_cnst > 0 and not cnst.empty:
        cnst_rank = cnst.groupby("Nombre vendedor").agg(
            Valor=("Valor pendiente subtotal", "sum"),
            Comprometido=("V.COMPROMETIDO", "sum"),
        ).reset_index()
        cnst_rank["% Participacion"] = (cnst_rank["Valor"] / vp_cnst * 100).round(2)
        cnst_rank["% Cumpl"] = (cnst_rank["Comprometido"] / cnst_rank["Valor"] * 100).round(2)
        cnst_rank = cnst_rank.sort_values("Valor", ascending=False).reset_index(drop=True)
        cnst_rank.index = cnst_rank.index + 1

        mes_actual = cnst["Fecha"].max()
        if pd.notna(mes_actual):
            inicio_mes = mes_actual.replace(day=1)
            mes_anterior = inicio_mes - timedelta(days=1)
            inicio_anterior = mes_anterior.replace(day=1)
            cnst_actual = cnst[cnst["Fecha"] >= inicio_mes]
            cnst_anterior = cnst[(cnst["Fecha"] >= inicio_anterior) & (cnst["Fecha"] < inicio_mes)]
            if not cnst_anterior.empty:
                actual_agg = cnst_actual.groupby("Nombre vendedor")["Valor pendiente subtotal"].sum().reset_index()
                ant_agg = cnst_anterior.groupby("Nombre vendedor")["Valor pendiente subtotal"].sum().reset_index()
                actual_agg.columns = ["Nombre vendedor", "Valor_actual"]
                ant_agg.columns = ["Nombre vendedor", "Valor_anterior"]
                var_df = actual_agg.merge(ant_agg, on="Nombre vendedor", how="outer").fillna(0)
                var_df["Var%"] = var_df.apply(
                    lambda r: ((r["Valor_actual"]-r["Valor_anterior"])/r["Valor_anterior"]*100)
                    if r["Valor_anterior"]>0 else (100 if r["Valor_actual"]>0 else 0), axis=1)
                cnst_rank = cnst_rank.merge(var_df[["Nombre vendedor", "Var%"]], on="Nombre vendedor", how="left")

        fig_cnst = go.Figure()
        fig_cnst.add_trace(go.Bar(x=[v/1e6 for v in cnst_rank["Valor"]], y=cnst_rank["Nombre vendedor"],
            orientation="h", marker_color=BLUE,
            text=[fmt_pm(v) for v in cnst_rank["Valor"]], textposition="outside"))
        fig_cnst.update_layout(**fig_layout("Valor en Construccion (millones $)", height=320))
        fig_cnst.update_xaxes(title="$ millones")
        fig_cnst.update_yaxes(categoryorder="total descending")

        children.append(build_podium(cnst_rank, " Podio Construccion", "Valor", "% Participacion", "% Cumpl"))

        cnst_display = cnst_rank.copy()
        cnst_display.insert(0, "#", cnst_display.index)
        cnst_display["Valor"] = cnst_display["Valor"].apply(lambda x: fmt_p(x))
        cnst_display["% Participacion"] = cnst_display["% Participacion"].apply(lambda x: f"{x:.2f}%")
        if "Var%" in cnst_display.columns:
            cnst_display["Variacion"] = cnst_display["Var%"].apply(
                lambda x: f" {x:+.2f}%" if pd.notna(x) else " N/A")

        cnst_table = dash_table.DataTable(
            columns=[{"name": c, "id": c} for c in cnst_display.columns if c not in ("Var%",)],
            data=cnst_display.to_dict("records"),
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.8rem"},
            style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
            style_data_conditional=[
                {"if": {"filter_query": "{#} = 1"}, "backgroundColor": "#FFF8DC"},
                {"if": {"filter_query": "{#} = 2"}, "backgroundColor": "#F0F0F0"},
                {"if": {"filter_query": "{#} = 3"}, "backgroundColor": "#FFF0E0"},
            ],
        )

        children.append(dbc.Row([
            dbc.Col(dcc.Graph(figure=fig_cnst, style={"height": "360px"}), width=7),
            dbc.Col(dmc.Card([
                dmc.CardSection([html.H6("Detalle Construccion", className="fw-bold"), cnst_table])
            ], withBorder=True, shadow="sm", padding="lg", radius="md"), width=5),
        ], className="mb-4 g-3"))
    else:
        children.append(dmc.Alert("No hay datos del canal Construccion con los filtros actuales.",
                                  title="Aviso", color="yellow", withCloseButton=True))

    # -- Analisis Automatico --
    children.append(html.Hr())
    children.append(html.Div([
        html.H6(" Analisis Automatico", className="fw-bold", style={"color": NAVY}),
        dbc.Button(" Generar Analisis", id="btn-analisis-ranking", color="secondary", size="sm", className="mb-2"),
        html.Div(id="analisis-ranking", className="small p-3",
                 style={"backgroundColor": "#f8fafc", "borderRadius": "8px", "border": "1px solid #e2e8f0", "minHeight": "60px"}),
    ], className="mt-4"))

    return children

def pagina_embudo(data):
    children = [section_title(" Embudo de Pedidos",
                 "Pipeline: desde elaboracion hasta comprometido")]

    estado_map = {
        "En elaboracion": "1. En Elaboracion", "Aprobado": "2. Aprobado",
        "Retenido": "3. Retenido", "Comprometido parcial": "4. Comprometido Parcial",
        "Comprometido": "5. Comprometido",
    }
    funnel = data.groupby("Estado movto.").agg(
        Valor=("Valor pendiente subtotal", "sum"),
        Pedidos=("Nro documento", "nunique"),
        Cantidad=("Cant. pedida", "sum"),
    ).reset_index()
    funnel["Stage"] = funnel["Estado movto."].map(estado_map).fillna(funnel["Estado movto."])
    stage_order = ["1. En Elaboracion", "2. Aprobado", "3. Retenido",
                   "4. Comprometido Parcial", "5. Comprometido"]
    funnel["Stage_order"] = funnel["Stage"].apply(lambda x: stage_order.index(x) if x in stage_order else 99)
    funnel = funnel.sort_values("Stage_order")

    fig = go.Figure()
    fig.add_trace(go.Funnel(y=funnel["Stage"], x=funnel["Valor"],
        text=[fmt_pm(v) for v in funnel["Valor"]],
        textposition="inside", textinfo="value+percent previous",
        marker=dict(color=[BLUE, AMBER, RED, GREEN, GREEN]),
        connector=dict(line=dict(color="#e2e8f0", width=2))))
    fig.update_layout(**fig_layout("Embudo de Valor (USD)", height=450))

    total_valor = funnel["Valor"].sum()
    comprometido = funnel[funnel["Estado movto."].str.contains("Comprometido", na=False)]["Valor"].sum()
    en_proceso = funnel[funnel["Estado movto."].isin(["En elaboracion", "Aprobado"])]["Valor"].sum()
    retenido = funnel[funnel["Estado movto."]=="Retenido"]["Valor"].sum()

    desglose = dmc.Card([
        dmc.CardSection([
            html.H6("Desglose por Estado", className="fw-bold"),
            dash_table.DataTable(
                columns=[{"name": c, "id": c} for c in ["Estado movto.", "Valor", "Pedidos", "Cantidad", "%"]],
                data=[{
                    "Estado movto.": r["Estado movto."],
                    "Valor": fmt_p(r["Valor"]),
                    "Pedidos": f"{r['Pedidos']:,}",
                    "Cantidad": f"{r['Cantidad']:,.0f}",
                    "%": f"{r['Valor']/total_valor*100:.2f}%" if total_valor else "0%",
                } for _, r in funnel.iterrows()],
                style_table={"overflowX": "auto"},
                style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.8rem"},
                style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
            ),
            html.Hr(),
            html.H6("Indicadores", className="fw-bold"),
            dbc.Row([
                dbc.Col(dmc.Card([
                    dmc.CardSection([
                        html.Small("En Proceso", className="text-muted d-block"),
                        html.Strong(fmt_p(en_proceso)),
                        html.Div(f"{en_proceso/total_valor*100:.2f}%" if total_valor else "0%",
                                 className="text-muted small"),
                    ]),
                ], withBorder=True, shadow="sm", padding="md", radius="sm", className="text-center mb-2")),
                dbc.Col(dmc.Card([
                    dmc.CardSection([
                        html.Small("Comprometido", className="text-muted d-block"),
                        html.Strong(fmt_p(comprometido)),
                        html.Div(f"{comprometido/total_valor*100:.2f}%" if total_valor else "0%",
                                 className="text-muted small"),
                    ]),
                ], withBorder=True, shadow="sm", padding="md", radius="sm", className="text-center mb-2")),
                dbc.Col(dmc.Card([
                    dmc.CardSection([
                        html.Small("Retenido", className="text-muted d-block"),
                        html.Strong(fmt_p(retenido)),
                        html.Div(f"{retenido/total_valor*100:.2f}%" if total_valor else "0%",
                                 className="text-muted small"),
                    ]),
                ], withBorder=True, shadow="sm", padding="md", radius="sm", className="text-center")),
            ]),
        ])
    ], withBorder=True, shadow="sm", padding="lg", radius="md", className="h-100")

    children.append(dbc.Row([
        dbc.Col(dcc.Graph(figure=fig, style={"height": "500px"}), width=7),
        dbc.Col(desglose, width=5),
    ], className="mb-4 g-3"))

    # Conversion analysis between stages
    if len(funnel) > 1:
        funnel["Conversion"] = 0.0
        for i in range(len(funnel)-1):
            actual = funnel.iloc[i]["Valor"]
            siguiente = funnel.iloc[i+1]["Valor"]
            funnel.iloc[i, funnel.columns.get_loc("Conversion")] = (siguiente / actual * 100) if actual else 0
        funnel.iloc[-1, funnel.columns.get_loc("Conversion")] = 100.0

        conv_fig = go.Figure()
        conv_fig.add_trace(go.Bar(x=funnel["Stage"], y=funnel["Conversion"],
            marker_color=[BLUE, AMBER, RED, GREEN, GREEN],
            text=[f"{v:.1f}%" for v in funnel["Conversion"]], textposition="outside"))
        conv_fig.update_layout(**fig_layout("Tasa de Conversion entre Etapas (%)", height=320,
            yaxis=dict(range=[0, 110])))
        conv_fig.update_xaxes(tickangle=-30)

        # Pedidos por estado
        pedidos_fig = go.Figure()
        pedidos_fig.add_trace(go.Bar(x=funnel["Stage"], y=funnel["Pedidos"],
            marker_color=[BLUE, AMBER, RED, GREEN, GREEN],
            text=funnel["Pedidos"], textposition="outside"))
        pedidos_fig.update_layout(**fig_layout("Pedidos por Etapa", height=320))
        pedidos_fig.update_xaxes(tickangle=-30)

        children.append(html.H6("Analisis de Conversion", className="fw-bold mt-4", style={"color": NAVY}))
        children.append(dbc.Row([
            dbc.Col(dcc.Graph(figure=conv_fig, style={"height": "360px"}), width=6),
            dbc.Col(dcc.Graph(figure=pedidos_fig, style={"height": "360px"}), width=6),
        ], className="mb-4 g-3"))

    # Waterfall: valor que avanza / se pierde entre etapas
    if len(funnel) > 1:
        stages_w = []
        for i in range(len(funnel)):
            stage = funnel.iloc[i]["Stage"]
            val = funnel.iloc[i]["Valor"]
            if i == 0:
                stages_w.append(dict(label=stage, value=val, type="total"))
            else:
                prev = funnel.iloc[i-1]["Valor"]
                diff = val - prev
                stages_w.append(dict(label=stage, value=diff, type="relative" if diff < 0 else "total"))
        stages_w[-1]["type"] = "total"

        waterfall = go.Figure(go.Waterfall(
            name="Flujo de Valor", orientation="v",
            measure=[s["type"] for s in stages_w],
            x=[s["label"] for s in stages_w],
            y=[s["value"] for s in stages_w],
            text=[fmt_pm(s["value"]) for s in stages_w],
            textposition="outside",
            connector=dict(line=dict(color="#94a3b8", width=2)),
            decreasing=dict(marker=dict(color=RED)),
            increasing=dict(marker=dict(color=GREEN)),
            totals=dict(marker=dict(color=BLUE)),
        ))
        waterfall.update_layout(**fig_layout("Flujo de Valor entre Etapas (millones $)", height=360,
            yaxis=dict(title="$ millones")))

        children.append(dbc.Row([
            dbc.Col(dcc.Graph(figure=waterfall, style={"height": "400px"}), width=7),
            dbc.Col(dmc.Card([
                dmc.CardSection([
                    html.H6("Origen de los Datos", className="fw-bold",
                            style={"color": NAVY, "borderBottom": f"2px solid {BLUE}", "paddingBottom": "6px"}),
                    html.P("El embudo agrupa todos los pedidos por su 'Estado movto.', "
                           "que sigue una secuencia de 5 etapas: desde 'En elaboracion' hasta 'Comprometido'. "
                           "Cada barra representa el valor total acumulado de pedidos en ese estado.",
                           className="small text-muted", style={"marginTop": "8px"}),
                    html.P("La tasa de conversion mide qué porcentaje del valor total "
                           "logra avanzar a la siguiente etapa del pipeline.",
                           className="small text-muted"),
                    html.Hr(),
                    html.H6("Alertas y Sugerencias", className="fw-bold"),
                    *[html.Div([
                        html.Strong(alert_title, style={"fontSize": "0.85rem"}),
                        html.Div(alert_body, className="small text-muted"),
                    ], style={"padding": "6px 0", "borderBottom": "1px solid #f1f5f9",
                              "borderLeft": f"3px solid {color}", "paddingLeft": "8px", "marginBottom": "4px"})
                      for alert_title, alert_body, color in [
                        ("Valor Retenido",
                         f"{fmt_pm(retenido)} ({retenido/total_valor*100:.1f}%) del valor total esta retenido. "
                         "Revisar causas con el equipo comercial." if retenido > 0 else "Sin valor retenido.",
                         RED if retenido > 0 else GREEN),
                        ("Oportunidad en Proceso",
                         f"{fmt_pm(en_proceso)} ({en_proceso/total_valor*100:.1f}%) del valor esta en elaboracion o aprobado. "
                         "Acelerar gestion para convertir en comprometido.",
                         AMBER),
                        ("Tasa de Cierre",
                         f"{(comprometido/total_valor*100) if total_valor else 0:.1f}% del valor total esta comprometido. "
                         "Meta sugerida: >40%.",
                         BLUE),
                      ]],
                ])
            ], withBorder=True, shadow="sm", padding="lg", radius="md"), width=5),
        ], className="mb-4 g-3"))

    # -- Analisis Automatico --
    children.append(html.Hr())
    children.append(html.Div([
        html.H6(" Analisis Automatico", className="fw-bold", style={"color": NAVY}),
        dbc.Button(" Generar Analisis", id="btn-analisis-embudo", color="secondary", size="sm", className="mb-2"),
        html.Div(id="analisis-embudo", className="small p-3",
                 style={"backgroundColor": "#f8fafc", "borderRadius": "8px", "border": "1px solid #e2e8f0", "minHeight": "60px"}),
    ], className="mt-4"))

    return children

def pagina_heatmap(data):
    children = [section_title(" Heatmap de Rendimiento",
                 "Valor pendiente por asesor y mes")]

    heat = data.copy()
    heat["Mes_Anio"] = heat["Fecha"].dt.to_period("M").astype(str)
    pivot = heat.pivot_table(index="Nombre vendedor", columns="Mes_Anio",
                             values="Valor pendiente subtotal", aggfunc="sum").fillna(0)
    meses = sorted(pivot.columns)
    pivot = pivot[meses]

    if pivot.empty:
        return children + [dmc.Alert("No hay suficientes datos para el heatmap.", title="Aviso", color="yellow", withCloseButton=True)]

    fig = go.Figure()
    fig.add_trace(go.Heatmap(z=pivot.values/1e6, x=pivot.columns, y=pivot.index,
        colorscale="Blues",
        text=[[fmt_pm(v) for v in row] for row in pivot.values],
        texttemplate="%{text}", textfont=dict(size=9),
        hovertemplate="Asesor: %{y}<br>Mes: %{x}<br>Valor: $%{z:.1f}M<extra></extra>"))
    fig.update_layout(**fig_layout("Valor Pendiente por Asesor x Mes (millones $)", height=400,
        xaxis=dict(gridcolor="#f1f5f9", zeroline=False, tickangle=-45, side="top"),
        yaxis=dict(gridcolor="#f1f5f9", zeroline=False, autorange="reversed")))
    fig.update_traces(colorbar=dict(title="$ Millones", len=0.8))

    total_asesor = pivot.sum(axis=1).sort_values(ascending=False)
    max_col = pivot.max().idxmax()
    max_val = pivot[max_col].max()
    max_asesor = pivot[max_col].idxmax()

    totals = dmc.Card([
        dmc.CardSection([
            html.H6("Totales por Asesor", className="fw-bold"),
            dash_table.DataTable(
                columns=[{"name": c, "id": c} for c in ["Asesor", "Total", "Meses Activo", "%"]],
                data=[{
                    "Asesor": asesor,
                    "Total": fmt_p(total),
                    "Meses Activo": str((pivot.loc[asesor]>0).sum()),
                    "%": f"{total/total_asesor.sum()*100:.2f}%",
                } for asesor, total in total_asesor.items()],
                style_table={"overflowX": "auto"},
                style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.8rem"},
                style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
            ),
            html.Hr(),
            html.H6("Periodo mas activo", className="fw-bold"),
            html.Div(f"{max_col}", className="fw-bold"),
            html.Div(f"{max_asesor}: {fmt_p(max_val)}", className="text-muted small"),
        ])
    ], withBorder=True, shadow="sm", padding="lg", radius="md", className="h-100")

    children.append(dbc.Row([
        dbc.Col(dcc.Graph(figure=fig, style={"height": "460px"}), width=7),
        dbc.Col(totals, width=5),
    ], className="mb-4 g-3"))

    # Monthly trend by asesor (top 5)
    top5_asesores = total_asesor.head(5).index.tolist()
    trend_fig = go.Figure()
    for asesor in top5_asesores:
        vals = pivot.loc[asesor] / 1e6
        trend_fig.add_trace(go.Scatter(x=vals.index, y=vals.values,
            mode="lines+markers", name=asesor, line=dict(width=2)))
    trend_fig.update_layout(**fig_layout("Top 5 Asesores - Tendencia Mensual (millones $)", height=380,
        xaxis=dict(tickangle=-45)))
    trend_fig.update_layout(legend=dict(orientation="h", y=1.1, font=dict(size=9)))

    # Summary metrics
    top_asesor_name = total_asesor.index[0]
    top_asesor_val = total_asesor.iloc[0]
    prom_mensual = pivot.mean(axis=1).sort_values(ascending=False)
    asesor_mas_consistente = prom_mensual.idxmax()

    children.append(html.H6("Tendencia y Rendimiento", className="fw-bold mt-4", style={"color": NAVY}))
    children.append(dbc.Row([
        dbc.Col(dcc.Graph(figure=trend_fig, style={"height": "420px"}), width=7),
        dbc.Col(dmc.Card([
            dmc.CardSection([
                html.H6("Resumen de Rendimiento", className="fw-bold"),
                html.Div([html.Span("Mejor asesor: ", className="text-muted"), html.Strong(top_asesor_name)]),
                html.Div([html.Span("Total: ", className="text-muted"), html.Strong(fmt_p(top_asesor_val))]),
                html.Div([html.Span("Participacion: ", className="text-muted"), html.Strong(f"{top_asesor_val/total_asesor.sum()*100:.2f}%")]),
                html.Hr(),
                html.Div([html.Span("Asesor mas consistente: ", className="text-muted"), html.Strong(asesor_mas_consistente)]),
                html.Div([html.Span("Promedio mensual: ", className="text-muted"), html.Strong(fmt_p(prom_mensual.iloc[0]))]),
                html.Hr(),
                html.H6("Distribucion Mensual", className="fw-bold"),
                *[html.Div([
                    html.Strong(mes),
                    html.Div(f"Total: {fmt_p(pivot[mes].sum())} | {pivot[mes].idxmax()}: {fmt_p(pivot[mes].max())}", className="text-muted small"),
                ], className="mb-1") for mes in pivot.columns[-6:]],
            ])
        ], withBorder=True, shadow="sm", padding="lg", radius="md"), width=5),
    ], className="mb-4 g-3"))

    # Data source explanation + month ranking + insights
    meses_ranking = pivot.sum(axis=0).sort_values(ascending=False)
    mejor_mes = meses_ranking.index[0]
    mejor_mes_val = meses_ranking.iloc[0]
    prom_mensual_val = pivot.sum(axis=0).mean()

    children.append(html.H6("Analisis del Heatmap", className="fw-bold mt-4", style={"color": NAVY}))
    children.append(dbc.Row([
        dbc.Col(dmc.Card([
            dmc.CardSection([
                html.H6("Origen de los Datos", className="fw-bold",
                        style={"color": NAVY, "borderBottom": f"2px solid {BLUE}", "paddingBottom": "6px"}),
                html.P("El heatmap cruza 'Nombre vendedor' (filas) contra 'Mes-Anio' (columnas). "
                       "Cada celda muestra el valor pendiente total de cada asesor en ese mes. "
                       "Tonos mas oscuros = mayor valor.",
                       className="small text-muted", style={"marginTop": "8px"}),
                html.P("Los datos provienen de la columna 'Valor pendiente subtotal' "
                       "agrupada por asesor y mes. Asesores sin actividad en un mes aparecen en blanco.",
                       className="small text-muted"),
                html.Hr(),
                html.H6("Ranking de Meses por Actividad", className="fw-bold"),
                *[html.Div([
                    html.Span(f"{i+1}. ", style={"fontWeight": "bold", "color": NAVY}),
                    html.Strong(mes),
                    html.Span(f"  {fmt_pm(valor)} | {pivot[mes].idxmax()}: {fmt_pm(pivot[mes].max())}",
                              className="text-muted small"),
                ], style={"padding": "3px 0", "borderBottom": "1px solid #f8fafc"})
                  for i, (mes, valor) in enumerate(meses_ranking.head(6).items())],
            ])
        ], withBorder=True, shadow="sm", padding="lg", radius="md", className="h-100"), width=6),
        dbc.Col(dmc.Card([
            dmc.CardSection([
                html.H6("Patrones Detectados", className="fw-bold",
                        style={"color": NAVY, "borderBottom": f"2px solid {AMBER}", "paddingBottom": "6px"}),
                *[
                    dmc.Card([
                        dmc.CardSection([
                            html.Div(html.Strong(title, style={"fontSize": "0.85rem"})),
                            html.Div(body, className="small text-muted"),
                        ])
                    ], withBorder=True, shadow="xs", padding="sm", radius="md",
                       style={"marginBottom": "8px", "borderLeft": f"4px solid {color}"})
                    for title, body, color in [
                        ("Mes de Mayor Actividad",
                         f"{mejor_mes}: {fmt_pm(mejor_mes_val)} — "
                         f"{(mejor_mes_val/prom_mensual_val-1)*100:.1f}% sobre el promedio mensual.",
                         BLUE),
                        ("Asesor Lider",
                         f"{top_asesor_name}: {fmt_p(top_asesor_val)} en {total_asesor.iloc[0]/prom_mensual_val:.0f} meses. "
                         f"Participacion: {top_asesor_val/total_asesor.sum()*100:.1f}% del total.",
                         GREEN),
                        ("Estacionalidad",
                         f"{len([m for m in meses_ranking.values if m > prom_mensual_val])} de {len(meses_ranking)} meses "
                         f"estan por encima del promedio mensual de {fmt_pm(prom_mensual_val)}.",
                         AMBER),
                    ]
                ],
            ])
        ], withBorder=True, shadow="sm", padding="lg", radius="md", className="h-100"), width=6),
    ], className="mb-4 g-3"))

    # -- Analisis Automatico --
    children.append(html.Hr())
    children.append(html.Div([
        html.H6(" Analisis Automatico", className="fw-bold", style={"color": NAVY}),
        dbc.Button(" Generar Analisis", id="btn-analisis-heatmap", color="secondary", size="sm", className="mb-2"),
        html.Div(id="analisis-heatmap", className="small p-3",
                 style={"backgroundColor": "#f8fafc", "borderRadius": "8px", "border": "1px solid #e2e8f0", "minHeight": "60px"}),
    ], className="mt-4"))

    return children

def pagina_proyeccion(data):
    children = [section_title(" Proyeccion de Cierre",
                 "Estimacion basada en tendencia historica")]

    evol = data.groupby(data["Fecha"].dt.to_period("M")).agg(
        Valor=("Valor pendiente subtotal", "sum"),
    ).reset_index()
    evol["Periodo"] = range(len(evol))
    evol["Fecha_str"] = evol["Fecha"].astype(str)

    if len(evol) < 3:
        return children + [dmc.Alert("Se necesitan al menos 3 meses de datos historicos.", title="Aviso", color="yellow", withCloseButton=True)]

    coef = np.polyfit(evol["Periodo"], evol["Valor"], 1)
    trend = np.poly1d(coef)
    evol["Tendencia"] = trend(evol["Periodo"])

    ultimo_periodo = evol["Periodo"].max()
    futuros = [{"Periodo": ultimo_periodo+i, "Valor": trend(ultimo_periodo+i), "Label": f"Proy. +{i}"}
               for i in range(1, 4)]
    fut_df = pd.DataFrame(futuros)

    hoy = data["Fecha"].max()
    mes_actual = hoy.to_period("M")
    datos_mes_actual = evol[evol["Fecha"] == mes_actual]
    valor_actual = datos_mes_actual["Valor"].sum() if not datos_mes_actual.empty else 0
    proy_cierre = trend(ultimo_periodo)
    dif = proy_cierre - valor_actual if not datos_mes_actual.empty else 0
    pct_proy = (proy_cierre / valor_actual * 100 - 100) if valor_actual else 0

    children.append(dbc.Row([
        dbc.Col(dmc.Card([
            dmc.CardSection([
                html.Small("Valor Actual del Mes", className="text-muted d-block"),
                html.H3(fmt_p(valor_actual), className="fw-bold", style={"color": NAVY}),
            ]),
        ], withBorder=True, shadow="sm", padding="lg", radius="md", className="text-center"), width=4),
        dbc.Col(dmc.Card([
            dmc.CardSection([
                html.Small("Proyeccion Cierre", className="text-muted d-block"),
                html.H3(fmt_p(proy_cierre), className="fw-bold", style={"color": BLUE}),
                html.Small(f"{dif:+,.0f}" if dif != 0 else "", className="text-muted"),
            ]),
        ], withBorder=True, shadow="sm", padding="lg", radius="md", className="text-center"), width=4),
        dbc.Col(dmc.Card([
            dmc.CardSection([
                html.Small("Brecha vs Proyeccion", className="text-muted d-block"),
                html.H3(f"{pct_proy:+.2f}%", className="fw-bold",
                        style={"color": GREEN if pct_proy >= 0 else RED}),
            ]),
        ], withBorder=True, shadow="sm", padding="lg", radius="md", className="text-center"), width=4),
    ], className="mb-4 g-3"))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=evol["Fecha_str"], y=evol["Valor"]/1e6,
        mode="lines+markers", name="Valor Real",
        line=dict(width=3, color=BLUE), marker=dict(size=8, color=BLUE)))
    fig.add_trace(go.Scatter(x=evol["Fecha_str"], y=evol["Tendencia"]/1e6,
        mode="lines", name="Tendencia Lineal",
        line=dict(width=2, dash="dash", color=RED)))

    # Confidence interval (1 sigma)
    residuos = evol["Valor"] - evol["Tendencia"]
    std_res = residuos.std()
    evol["CI_sup"] = (evol["Tendencia"] + 1.5 * std_res) / 1e6
    evol["CI_inf"] = (evol["Tendencia"] - 1.5 * std_res) / 1e6
    fig.add_trace(go.Scatter(x=evol["Fecha_str"], y=evol["CI_sup"],
        mode="lines", line=dict(width=0), showlegend=False, name="CI_sup"))
    fig.add_trace(go.Scatter(x=evol["Fecha_str"], y=evol["CI_inf"],
        mode="lines", line=dict(width=0), fill="tonexty",
        fillcolor=rgba(BLUE, 0.1), name="Intervalo 80%",
        showlegend=True))

    fig.add_trace(go.Scatter(x=fut_df["Label"], y=fut_df["Valor"]/1e6,
        mode="markers+lines", name="Proyeccion",
        line=dict(width=2, dash="dot", color=GREEN),
        marker=dict(size=10, color=GREEN, symbol="diamond")))
    # Future confidence
    fut_df["CI_sup"] = (fut_df["Valor"] + 1.5 * std_res) / 1e6
    fut_df["CI_inf"] = (fut_df["Valor"] - 1.5 * std_res) / 1e6
    fig.add_trace(go.Scatter(x=fut_df["Label"], y=fut_df["CI_sup"],
        mode="lines", line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=fut_df["Label"], y=fut_df["CI_inf"],
        mode="lines", line=dict(width=0), fill="tonexty",
        fillcolor=rgba(GREEN, 0.1), name="Intervalo Proy."))

    # Optimistic / Pessimistic scenarios
    fut_df["Opt"] = (fut_df["Valor"] * 1.15) / 1e6
    fut_df["Pes"] = (fut_df["Valor"] * 0.85) / 1e6
    fig.add_trace(go.Scatter(x=fut_df["Label"], y=fut_df["Opt"],
        mode="lines+markers", name="Optimista (+15%)",
        line=dict(width=1.5, dash="dot", color=GREEN),
        marker=dict(size=6, color=GREEN, symbol="star")))
    fig.add_trace(go.Scatter(x=fut_df["Label"], y=fut_df["Pes"],
        mode="lines+markers", name="Pesimista (-15%)",
        line=dict(width=1.5, dash="dot", color=RED),
        marker=dict(size=6, color=RED, symbol="star")))

    fig.update_layout(**fig_layout("Proyeccion de Valor Pendiente (millones $)", height=420),
                      legend=dict(orientation="h", y=1.1))
    fig.update_xaxes(tickangle=-45)

    pronostico = dmc.Card([
        dmc.CardSection([
            html.H6("Pronostico", className="fw-bold"),
            *[dmc.Card([
                dmc.CardSection([
                    html.Small(r["Label"], className="text-muted d-block"),
                    html.Strong(fmt_p(r["Valor"])),
                    html.Div(fmt_pm(r["Valor"]), className="text-muted small"),
                ])
            ], withBorder=True, shadow="sm", padding="md", radius="sm", className="mb-2") for _, r in fut_df.iterrows()],
            html.Hr(),
            html.H6("Datos de Tendencia", className="fw-bold"),
            dash_table.DataTable(
                columns=[{"name": c, "id": c} for c in ["Fecha_str", "Valor", "Tendencia"]],
                data=evol.tail(12)[["Fecha_str", "Valor", "Tendencia"]].to_dict("records"),
                style_table={"overflowX": "auto"},
                style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.8rem"},
                style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
            ),
        ])
    ], withBorder=True, shadow="sm", padding="lg", radius="md", className="h-100")

    children.append(dbc.Row([
        dbc.Col(dcc.Graph(figure=fig, style={"height": "460px"}), width=7),
        dbc.Col(pronostico, width=5),
    ], className="mb-4 g-3"))

    # Goal vs budget comparison
    presupuesto_data = cargar_presupuesto()
    total_budget = sum(presupuesto_data.values()) if presupuesto_data else 0
    if presupuesto_data:
        pct_vs_budget = (proy_cierre / total_budget * 100) if total_budget else 0
        budget_fig = go.Figure()
        budget_fig.add_trace(go.Bar(x=["Proyeccion", "Presupuesto"], y=[proy_cierre/1e6, total_budget/1e6],
            marker_color=[BLUE, GREEN],
            text=[fmt_pm(proy_cierre), fmt_pm(total_budget)], textposition="outside"))
        budget_fig.update_layout(**fig_layout("Proyeccion vs Presupuesto (millones $)", height=320))

        # Monthly budget breakdown
        budget_asesor_data = []
        for nom, val in presupuesto_data.items():
            budget_asesor_data.append({"Asesor": nom, "Presupuesto": fmt_p(val)})
        budget_table = dash_table.DataTable(
            columns=[{"name": c, "id": c} for c in ["Asesor", "Presupuesto"]],
            data=budget_asesor_data,
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.8rem"},
            style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
        )

        children.append(html.H6("Comparativo contra Presupuesto", className="fw-bold mt-4", style={"color": NAVY}))
        children.append(dbc.Row([
            dbc.Col(dcc.Graph(figure=budget_fig, style={"height": "360px"}), width=6),
            dbc.Col(dmc.Card([
                dmc.CardSection([
                    html.H6("Presupuesto por Asesor", className="fw-bold"),
                    budget_table,
                    html.Hr(),
                    html.Div([html.Span("Presupuesto total: ", className="text-muted"), html.Strong(fmt_p(total_budget))]),
                    html.Div([html.Span("Proyeccion vs Presupuesto: ", className="text-muted"), html.Strong(f"{pct_vs_budget:.2f}%")]),
                ])
            ], withBorder=True, shadow="sm", padding="lg", radius="md"), width=6),
        ], className="mb-4 g-3"))

    # Methodology note + confidence / scenario analysis
    r2 = np.corrcoef(evol["Periodo"], evol["Valor"])[0, 1] ** 2
    mape = (abs(residuos / evol["Valor"]).mean() * 100) if evol["Valor"].sum() else 0

    children.append(html.H6("Metodologia y Escenarios", className="fw-bold mt-4", style={"color": NAVY}))
    children.append(dbc.Row([
        dbc.Col(dmc.Card([
            dmc.CardSection([
                html.H6("Nota Metodologica", className="fw-bold",
                        style={"color": NAVY, "borderBottom": f"2px solid {BLUE}", "paddingBottom": "6px"}),
                html.P("La proyeccion utiliza regresion lineal simple sobre los valores mensuales "
                       "de 'Valor pendiente subtotal'. El intervalo de confianza del 80% se calcula "
                       "como ±1.5 desviaciones estandar de los residuales.",
                       className="small text-muted", style={"marginTop": "8px"}),
                html.P("Los escenarios optimista y pesimista aplican un ajuste de ±15% sobre "
                       "la proyeccion lineal para modelar variaciones del mercado.",
                       className="small text-muted"),
                html.Hr(),
                html.Div([
                    html.Div([html.Strong("R² (bondad de ajuste): "),
                              html.Span(f"{r2:.3f}", className="text-muted")]),
                    html.Div([html.Strong("Error MAPE: "),
                              html.Span(f"{mape:.1f}%", className="text-muted")]),
                    html.Div([html.Strong("Periodos analizados: "),
                              html.Span(str(len(evol)), className="text-muted")]),
                    html.Div([html.Strong("Desv. estandar residual: "),
                              html.Span(fmt_pm(std_res), className="text-muted")]),
                ], className="small"),
            ])
        ], withBorder=True, shadow="sm", padding="lg", radius="md", className="h-100"), width=6),
        dbc.Col(dmc.Card([
            dmc.CardSection([
                html.H6("Escenarios de Cierre", className="fw-bold",
                        style={"color": NAVY, "borderBottom": f"2px solid {AMBER}", "paddingBottom": "6px"}),
                *[
                    dmc.Card([
                        dmc.CardSection([
                            html.Div(html.Strong(title, style={"fontSize": "0.85rem"})),
                            html.Div([
                                html.Span(proy_text, style={"fontWeight": "bold", "fontSize": "1.1rem",
                                                            "color": color}),
                                html.Div(f"vs Presupuesto: {pct_budg}%", className="text-muted small"),
                            ]),
                        ])
                    ], withBorder=True, shadow="xs", padding="sm", radius="md",
                       style={"marginBottom": "8px", "borderLeft": f"4px solid {color}"})
                    for title, proy_text, pct_budg, color in [
                        ("Optimista (+15%)",
                         fmt_pm(proy_cierre * 1.15),
                         f"{(proy_cierre*1.15/total_budget*100) if total_budget else 0:.1f}" if presupuesto_data else "N/A",
                         GREEN),
                        ("Base (Lineal)",
                         fmt_pm(proy_cierre),
                         f"{(proy_cierre/total_budget*100) if total_budget else 0:.1f}" if presupuesto_data else "N/A",
                         BLUE),
                        ("Pesimista (-15%)",
                         fmt_pm(proy_cierre * 0.85),
                         f"{(proy_cierre*0.85/total_budget*100) if total_budget else 0:.1f}" if presupuesto_data else "N/A",
                         RED),
                    ]
                ],
            ])
        ], withBorder=True, shadow="sm", padding="lg", radius="md", className="h-100"), width=6),
    ], className="mb-4 g-3"))

    # Asesor monthly trend for projection context
    asesor_mensual = data.groupby([data["Fecha"].dt.to_period("M").astype(str), "Nombre vendedor"]).agg(
        Valor=("Valor pendiente subtotal", "sum"),
    ).reset_index()
    top_asesores_proy = asesor_mensual.groupby("Nombre vendedor")["Valor"].sum().sort_values(ascending=False).head(5).index
    asesor_trend = asesor_mensual[asesor_mensual["Nombre vendedor"].isin(top_asesores_proy)]

    asesor_fig = go.Figure()
    for asesor in top_asesores_proy:
        d = asesor_trend[asesor_trend["Nombre vendedor"] == asesor].sort_values("Fecha")
        asesor_fig.add_trace(go.Scatter(x=d["Fecha"], y=d["Valor"]/1e6,
            mode="lines+markers", name=asesor, line=dict(width=2)))
    asesor_fig.update_layout(**fig_layout("Top 5 Asesores - Tendencia Mensual (millones $)", height=360,
        xaxis=dict(tickangle=-45)))
    asesor_fig.update_layout(legend=dict(orientation="h", y=1.1, font=dict(size=9)))

    children.append(html.H6("Tendencia por Asesor", className="fw-bold", style={"color": NAVY}))
    children.append(dbc.Row([
        dbc.Col(dcc.Graph(figure=asesor_fig, style={"height": "400px"}), width=12),
    ], className="mb-4 g-3"))

    # -- Analisis Automatico --
    children.append(html.Hr())
    children.append(html.Div([
        html.H6(" Analisis Automatico", className="fw-bold", style={"color": NAVY}),
        dbc.Button(" Generar Analisis", id="btn-analisis-proyeccion", color="secondary", size="sm", className="mb-2"),
        html.Div(id="analisis-proyeccion", className="small p-3",
                 style={"backgroundColor": "#f8fafc", "borderRadius": "8px", "border": "1px solid #e2e8f0", "minHeight": "60px"}),
    ], className="mt-4"))

    return children

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    app.run(debug=False, port=8503)
