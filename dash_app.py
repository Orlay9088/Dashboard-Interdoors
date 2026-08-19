import base64
import threading
import traceback
from datetime import datetime
from pathlib import Path
import sys
import time

import dash
from dash import dcc, html, Input, Output, State, callback, no_update
from dash.dependencies import ALL
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import CARPETA_ENTRADA
from pages.components import NAVY, BLUE, AMBER, GREEN, RED, GRAY, DARKGRAY, GOLD, apply_filters
from etl.detector import detectar_tipo
from etl.normalizer import normalizar
from etl.processor import procesar as procesar_etl

from firebase_config import try_load, try_save, get_metadata, load_local, clear_local_cache
from analysis import generar_analisis, generar_con_gemini, generar_con_opencode
from pages.pedidos import (
    pagina_home, pagina_resumen, pagina_participacion, pagina_pareto,
    pagina_ranking, pagina_embudo, pagina_heatmap, pagina_proyeccion,
)
from pages.facturas import (
    pagina_resumen_ventas, pagina_margenes, pagina_mix_producto, pagina_precio_promedio,
)
from pages.inventario import (
    pagina_resumen_stock, pagina_por_bodega, pagina_criticos,
)

# ============================================================
# CACHE
# ============================================================
_data_cache = {}
_cache_timestamps = {}
_cache_lock = threading.Lock()

def _load_cached(module):
    with _cache_lock:
        now = time.time()
        last_load = _cache_timestamps.get(module, 0)
        if (now - last_load) > (24 * 3600):
            _data_cache.pop(module, None)
        if module in _data_cache and _data_cache[module] is not None:
            return _data_cache[module].copy()
    df, backend = try_load(module)
    if not df.empty:
        with _cache_lock:
            _data_cache[module] = df.copy()
            _cache_timestamps[module] = now
    return df

def _clear_cache(module=None):
    with _cache_lock:
        if module:
            _data_cache.pop(module, None)
            _cache_timestamps.pop(module, None)
        else:
            _data_cache.clear()
            _cache_timestamps.clear()


def _parse_filters(filters):
    import json
    if isinstance(filters, str):
        try:
            return json.loads(filters)
        except Exception:
            return {}
    return filters if isinstance(filters, dict) else {}

def _apply_special_filters(data, module, page, pareto_canal, bodega_filter):
    import json
    if (module in ("pedidos", "facturas") and pareto_canal and pareto_canal != "TODOS"
            and "_canal" in data.columns
            and pareto_canal in data["_canal"].astype(str).unique()):
        data = data[data["_canal"] == pareto_canal]
    if module == "inventario" and bodega_filter and bodega_filter != "[]" and "_bodega" in data.columns:
        try:
            selected = json.loads(bodega_filter)
            if selected:
                data = data[data["_bodega"].astype(str).isin(selected)]
        except Exception:
            pass
    return data

# ============================================================
# APP SETUP
# ============================================================
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dmc.styles.DATES],
    title="Dashboard Interdoors",
    suppress_callback_exceptions=True,
)
server = app.server


@server.route("/health")
def health_check():
    return {"status": "ok", "service": "Dashboard Interdoors"}, 200


MODULES = {
    "pedidos": {"label": "PEDIDOS", "color": BLUE, "pages": {
        "home": "Home",
        "resumen": "Resumen", "participacion": "Participacion",
        "pareto": "Pareto", "ranking": "Ranking", "embudo": "Embudo",
        "heatmap": "Heatmap", "proyeccion": "Proyeccion",
    }},
    "facturas": {"label": "FACTURACION", "color": GREEN, "pages": {
        "resumen_ventas": "Resumen", "margenes": "Margenes",
        "mix_producto": "Mix Producto", "precio_promedio": "Precio Prom.",
    }},
    "inventario": {"label": "INVENTARIO", "color": AMBER, "pages": {
        "resumen_stock": "Resumen", "por_bodega": "Por Bodega",
        "criticos": "Criticos",
    }},
}

SIDEBAR_STYLE = {
    "position": "fixed", "top": 0, "left": 0, "bottom": 0,
    "width": "260px", "padding": "1rem", "backgroundColor": DARKGRAY,
    "color": "white", "overflowY": "auto", "zIndex": 1000,
    "transition": "transform 0.3s ease",
}
CONTENT_STYLE = {"marginLeft": "260px", "padding": "1.5rem", "background": "#F5F5F0", "minHeight": "100vh"}


# ============================================================
# LAYOUT
# ============================================================
def build_sidebar():
    children = [
        html.Div([
            html.Div("INTERDOORS", style={
                "fontSize": "1.3rem", "fontWeight": "bold", "color": "white",
                "letterSpacing": "2px", "textAlign": "center",
            }),
            html.Div("Creando Hogares", style={
                "fontSize": "0.65rem", "color": GOLD, "textAlign": "center",
                "fontStyle": "italic", "letterSpacing": "1px", "marginBottom": "10px",
            }),
            html.Div(style={
                "height": "2px", "background": f"linear-gradient(90deg, transparent, {GOLD}, transparent)",
                "marginBottom": "16px",
            }),
        ]),
    ]

    # Module cards
    for key, mod in MODULES.items():
        children.append(dbc.Button(
            [
                html.Div([
                    html.Span(f"  {mod['label']}",
                              id=f"mod-text-{key}",
                              style={"fontSize": "0.95rem", "fontWeight": "bold", "color": "#94a3b8"}),
                ]),
                html.Div([
                    html.Span(id=f"mod-dot-{key}", style={"fontSize": "0.65rem", "marginRight": "6px"}),
                    html.Span(id=f"mod-badge-{key}",
                              style={"fontSize": "0.7rem", "color": "#94a3b8"}),
                ], style={"display": "flex", "alignItems": "center", "marginTop": "3px"}),
            ],
            id=f"mod-{key}",
            className="w-100 text-start",
            style={
                "backgroundColor": "rgba(255,255,255,0.03)",
                "border": "1px solid rgba(255,255,255,0.06)",
                "borderLeft": "4px solid rgba(255,255,255,0.2)",
                "borderRadius": "8px",
                "padding": "12px 14px",
                "marginBottom": "10px",
                "transition": "all 0.3s",
                "opacity": "0.6",
            },
        ))

    children.append(html.Hr(style={"borderColor": "rgba(255,255,255,0.15)"}))

    # Upload section - conditional per module
    children.append(html.Div([
        html.H6(id="upload-module-title", className="text-uppercase small fw-semibold mb-2",
                style={"color": "#94a3b8"}),
        dcc.Upload(
            id="upload-data",
            children=html.Div(["Arrastra o ", html.Span("selecciona .xlsx",
                style={"color": "#93c5fd", "textDecoration": "underline", "cursor": "pointer"})]),
            className="border border-2 border-dashed rounded-3 p-3 text-center small mb-2",
            style={"cursor": "pointer", "borderColor": "rgba(255,255,255,0.3)", "color": "white",
                   "width": "100%", "minHeight": "50px", "display": "flex",
                   "alignItems": "center", "justifyContent": "center"},
            multiple=False,
            accept=".xlsx,.xls",
        ),
        html.Div(id="file-name", className="small mb-1", style={"color": "#93c5fd"}),
        dcc.Loading(
            id="loading-process",
            type="default",
            children=html.Div([
                dbc.Button("Procesar archivo", id="btn-process", color="primary", size="sm", className="w-100 mb-1"),
                html.Div(id="upload-status", style={"fontSize": "0.8rem", "minHeight": "2rem"}),
            ])
        ),
        html.Div(id="mod-last-file", className="small mb-1", style={"color": "#64748b", "minHeight": "1rem"}),
    dbc.Button("Recargar ultimo archivo", id="btn-reload-module", color="secondary",
               size="sm", className="w-100 mb-1", style={"fontSize": "0.75rem"}),
        html.Div(id="reload-status", style={"fontSize": "0.75rem", "minHeight": "1rem"}),
    ], id="upload-section")),

    children.append(html.Hr(style={"borderColor": "rgba(255,255,255,0.15)"}))

    # Action buttons - compact layout
    children.extend([
    dbc.Button("Refrescar datos", id="refresh-data", color="light", size="sm", className="w-100 mb-1 text-dark"),
    dbc.Button("Limpiar datos", id="clear-data", color="danger", size="sm", className="w-100 mb-1"),
    dbc.Button("   Descargar CSV", id="btn-download-csv", color="success", size="sm", className="w-100 mb-1"),
    dcc.Download(id="download-data"),
    html.Div(id="clear-status", style={"fontSize": "0.75rem", "minHeight": "1.2rem"}),
    html.Hr(style={"borderColor": "rgba(255,255,255,0.15)"}),
    html.H6("Nube", className="text-uppercase small fw-semibold mb-2", style={"color": "#94a3b8"}),
    dbc.Button("Guardar en la nube", id="btn-save-cloud", color="warning", size="sm", className="w-100 mb-1", style={"fontSize": "0.75rem"}),
    dbc.Button("Cargar desde la nube", id="btn-load-cloud", color="info", size="sm", className="w-100 mb-1", style={"fontSize": "0.75rem"}),
    html.Div(id="cloud-status", style={"fontSize": "0.72rem", "minHeight": "1rem", "color": "#94a3b8"}),
    html.Hr(style={"borderColor": "rgba(255,255,255,0.15)"}),

    html.H6("IA Analisis", className="text-uppercase small fw-semibold mb-2", style={"color": "#94a3b8"}),
    dcc.Dropdown(
        id="ai-model-select",
        options=[
            {"label": "OpenCode AI", "value": "opencode"},
            {"label": "Gemini (Google)", "value": "gemini"},
            {"label": "Sin IA (analisis local)", "value": "local"},
        ],
        value="local",
        clearable=False,
        className="mb-2",
        style={"fontSize": "0.8rem"},
    ),
    dbc.Input(id="api-key-input", type="password", placeholder="API Key", size="sm", className="mb-1",
              style={"fontSize": "0.8rem"}),
    dbc.Button("Verificar", id="btn-verify-api", color="success", size="sm", className="w-100 mb-1"),
    html.Div(id="api-status", style={"fontSize": "0.75rem", "color": "#94a3b8", "minHeight": "1.2rem"}),
    dcc.Store(id="store-api-key", data=""),
    dcc.Store(id="store-ai-model", data="local"),
    html.Hr(style={"borderColor": "rgba(255,255,255,0.15)"}),
    html.Div(id="sidebar-info", className="small", style={"color": "#94a3b8"}),
])
    return html.Div(children, id="sidebar", style=SIDEBAR_STYLE)


app.layout = html.Div([
    dcc.Store(id="store-module", data="pedidos"),
    dcc.Store(id="store-page", data="resumen"),
    dcc.Store(id="store-filters", data="{}"),
    dcc.Store(id="store-refresh", data=0),
    dcc.Store(id="store-clear", data=0),
    dcc.Store(id="store-tipo", data="pedidos"),
    dcc.Store(id="store-pareto-canal", data="TODOS"),
    dcc.Store(id="store-facturas-rango", data=[]),
    dcc.Store(id="store-bodega-filter", data="[]"),
    dcc.Store(id="store-clear-confirm", data=False),
    dcc.ConfirmDialog(
        id="confirm-clear",
        message="Esto limpiará todos los datos locales y la nube.\n\n¿Continuar?",
        displayed=False,
    ),
    dcc.Interval(id="stale-interval", interval=60 * 60 * 1000, n_intervals=0),
    build_sidebar(),
    html.Div([
        html.Button("☰", id="sidebar-toggle",
            style={
                "display": "none", "position": "fixed", "top": "10px", "left": "10px",
                "zIndex": 1100, "background": DARKGRAY, "color": "white", "border": "none",
                "fontSize": "1.5rem", "width": "40px", "height": "40px", "borderRadius": "8px",
                "cursor": "pointer",
            }
        ),
        dcc.Loading(
            html.Div([
                html.Div(id="nav-bar"),
                html.Div(id="canal-bar"),
                html.Div(id="resumen-filter-bar"),
                dcc.DatePickerRange(
                    id="resumen-date-range",
                    display_format="DD/MM/YYYY",
                    clearable=True,
                    style={"fontSize": "0.8rem"},
                ),
                html.Div(id="facturas-time-bar", children=[
                    html.Span("Periodo: ", style={"fontSize": "0.78rem", "color": GRAY, "marginRight": "8px", "fontWeight": "500"}),
                    dcc.DatePickerRange(
                        id="facturas-date-range",
                        display_format="DD/MM/YYYY",
                        clearable=True,
                        style={"fontSize": "0.8rem"},
                    ),
                ], style={"display": "none"}),
                html.Div(id="bodega-bar"),
                html.Div(id="page-content"),
            ]),
            type="circle", color=BLUE,
        ),
        html.Hr(style={"margin": "16px 0"}),
        html.Div([
            html.Button("   Analizar con IA   ",
                id="btn-single-analysis",
                disabled=False,
                style={
                    "backgroundColor": GOLD, "color": DARKGRAY, "border": f"1px solid {GOLD}",
                    "fontSize": "0.85rem", "padding": "8px 24px", "borderRadius": "6px",
                    "cursor": "pointer", "fontWeight": "bold",
                }
            ),
        ], style={"textAlign": "center", "marginBottom": "12px"}),
        dcc.Loading(
            html.Div(id="analisis-result", style={"padding": "12px", "backgroundColor": "#F5F5F0",
                "borderRadius": "8px", "border": "1px solid #e5e7eb", "minHeight": "50px"}),
            type="default", color=GOLD,
        ),
    ], style=CONTENT_STYLE, className="content-area"),
])

# ===== NAV BAR CALLBACK =====
@callback(
    Output("nav-bar", "children"),
    Input("store-module", "data"),
    Input("store-page", "data"),
)
def render_nav_bar(module, page):
    module = str(module).strip().lower()
    if module not in MODULES:
        module = list(MODULES.keys())[0]
    mod_info = MODULES[module]
    if page not in mod_info["pages"]:
        page = list(mod_info["pages"].keys())[0]
    buttons = []
    for pk, plabel in mod_info["pages"].items():
        active = pk == page
        buttons.append(html.Button(
            plabel,
            id={"type": "nav-btn", "page": pk},
            style={
                "backgroundColor": BLUE if active else "white",
                "color": "white" if active else GRAY,
                "border": f"1px solid {BLUE}", "fontSize": "0.78rem",
                "padding": "6px 14px", "borderRadius": "6px",
                "marginRight": "6px", "marginBottom": "4px",
                "cursor": "pointer", "fontWeight": "bold" if active else "normal",
            }
        ))
    return html.Div([html.Div(buttons, style={"display": "flex", "flexWrap": "wrap"}), html.Hr(style={"margin": "12px 0"})])

# ===== CANAL FILTER CALLBACK (PEDIDOS + FACTURAS) =====
@callback(
    Output("canal-bar", "children"),
    Input("store-module", "data"),
    Input("store-page", "data"),
    Input("store-pareto-canal", "data"),
    Input("store-refresh", "data"),
)
def render_canal_bar(module, page, pareto_canal, _refresh):
    if str(module).strip().lower() not in ("pedidos", "facturas"):
        return None
    df = _load_cached(str(module).strip().lower())
    if df.empty:
        return None
    canales = ["TODOS"] + sorted(df["_canal"].dropna().unique().tolist()) if "_canal" in df.columns else ["TODOS"]
    buttons = []
    for c in canales:
        active = c == pareto_canal
        buttons.append(html.Button(c,
            id={"type": "canal-btn", "name": c},
            style={
                "backgroundColor": BLUE if active else "white",
                "color": "white" if active else GRAY,
                "border": f"1px solid {BLUE}", "fontSize": "0.72rem",
                "padding": "4px 10px", "borderRadius": "4px", "marginRight": "5px",
                "cursor": "pointer", "fontWeight": "bold" if active else "normal",
            }
        ))
    return html.Div([
        html.Span("Canal: ", style={"fontSize": "0.78rem", "color": GRAY, "marginRight": "8px", "fontWeight": "500"}),
        html.Span(buttons, style={"display": "inline-flex", "flexWrap": "nowrap", "overflowX": "auto", "maxWidth": "100%"}),
    ], style={"marginBottom": "12px"})


# ===== RESUMEN FILTER BAR (Pedidos > Resumen) =====
@callback(
    Output("resumen-filter-bar", "children"),
    Output("resumen-filter-bar", "style"),
    Output("resumen-canal-dropdown", "value", allow_duplicate=True),
    Input("store-module", "data"),
    Input("store-page", "data"),
    Input("store-refresh", "data"),
    Input("store-clear", "data"),
    Input("store-pareto-canal", "data"),
    prevent_initial_call=True,
)
def render_resumen_filter_bar(module, page, _refresh, _clear, pareto_canal):
    hidden = ([], {"display": "none"}, no_update)
    if str(module).strip().lower() != "pedidos" or str(page).strip().lower() != "resumen":
        return hidden
    df = _load_cached("pedidos")
    if df.empty:
        return hidden

    canales = ["TODOS"] + sorted(df["_canal"].dropna().unique().tolist()) if "_canal" in df.columns else ["TODOS"]
    canal_val = pareto_canal if pareto_canal and pareto_canal in canales else "TODOS"

    canal_dropdown = html.Div([
        html.Span("Canal: ", style={"fontSize": "0.78rem", "color": GRAY, "marginRight": "6px", "fontWeight": "500"}),
        dcc.Dropdown(
            id="resumen-canal-dropdown",
            options=[{"label": c, "value": c} for c in canales],
            value=canal_val,
            clearable=False,
            style={"minWidth": "160px", "fontSize": "0.8rem"},
        ),
    ], style={"display": "inline-flex", "alignItems": "center", "marginRight": "16px"})

    visible = {"marginBottom": "10px", "display": "flex", "alignItems": "center", "gap": "4px", "flexWrap": "wrap"}
    return html.Div([canal_dropdown]), visible, canal_val


@callback(
    Output("resumen-date-range", "min_date_allowed"),
    Output("resumen-date-range", "max_date_allowed"),
    Output("resumen-date-range", "start_date"),
    Output("resumen-date-range", "end_date"),
    Input("store-module", "data"),
    Input("store-page", "data"),
    Input("store-refresh", "data"),
    Input("store-clear", "data"),
    Input("store-pareto-canal", "data"),
    State("store-filters", "data"),
    prevent_initial_call=True,
)
def sync_resumen_dates(module, page, _refresh, _clear, _canal, filters_json):
    none4 = (no_update, no_update, no_update, no_update)
    if str(module).strip().lower() != "pedidos" or str(page).strip().lower() != "resumen":
        return none4
    df = _load_cached("pedidos")
    if df.empty:
        return none4
    fechas = pd.to_datetime(df["_fecha"], errors="coerce").dropna()
    if fechas.empty:
        return none4
    min_date = fechas.min().date().isoformat()
    max_date = fechas.max().date().isoformat()
    import json as _json
    try:
        filters = _json.loads(filters_json) if isinstance(filters_json, str) else (filters_json or {})
    except Exception:
        filters = {}
    rango = filters.get("rango", [])
    start_date = rango[0] if len(rango) == 2 and rango[0] else min_date
    end_date = rango[1] if len(rango) == 2 and rango[1] else max_date
    return min_date, max_date, start_date, end_date


@callback(
    Output("store-pareto-canal", "data", allow_duplicate=True),
    Input("resumen-canal-dropdown", "value"),
    prevent_initial_call=True,
)
def update_resumen_canal(canal):
    if not canal or canal == "TODOS":
        return "TODOS"
    return canal


@callback(
    Output("store-filters", "data", allow_duplicate=True),
    Input("resumen-date-range", "start_date"),
    Input("resumen-date-range", "end_date"),
    State("store-filters", "data"),
    prevent_initial_call=True,
)
def update_resumen_dates(start_date, end_date, current_json):
    import json as _json
    try:
        filters = _json.loads(current_json) if isinstance(current_json, str) else (current_json or {})
    except Exception:
        filters = {}
    filters = dict(filters)
    if start_date and end_date:
        filters["rango"] = [start_date, end_date]
    else:
        filters.pop("rango", None)
    return _json.dumps(filters)


# ===== FACTURAS DATE FILTER =====
@callback(
    Output("facturas-time-bar", "style"),
    Output("facturas-date-range", "min_date_allowed"),
    Output("facturas-date-range", "max_date_allowed"),
    Output("facturas-date-range", "start_date"),
    Output("facturas-date-range", "end_date"),
    Input("store-module", "data"),
    Input("store-refresh", "data"),
    State("store-facturas-rango", "data"),
)
def render_facturas_time_bar(module, _refresh, current_range):
    hidden = {"display": "none"}
    if str(module).strip().lower() != "facturas":
        return hidden, None, None, None, None
    df = _load_cached("facturas")
    if df.empty or "_fecha" not in df.columns:
        return hidden, None, None, None, None
    fechas = pd.to_datetime(df["_fecha"], errors="coerce").dropna()
    if fechas.empty:
        return hidden, None, None, None, None
    min_date = fechas.min().date().isoformat()
    max_date = fechas.max().date().isoformat()
    selected = current_range if isinstance(current_range, list) else []
    start_date = selected[0] if len(selected) == 2 and selected[0] else min_date
    end_date = selected[1] if len(selected) == 2 and selected[1] else max_date
    visible = {"marginBottom": "12px", "display": "flex", "alignItems": "center", "gap": "6px"}
    return visible, min_date, max_date, start_date, end_date


@callback(
    Output("store-facturas-rango", "data"),
    Input("facturas-date-range", "start_date"),
    Input("facturas-date-range", "end_date"),
    State("store-facturas-rango", "data"),
    prevent_initial_call=True,
)
def select_facturas_range(start_date, end_date, current_range):
    new = [start_date, end_date] if start_date and end_date else []
    if new == (current_range or []):
        return no_update
    return new

# ===== BODEGA BAR CALLBACK (Inventario) =====
@callback(
    Output("bodega-bar", "children"),
    Input("store-module", "data"),
    Input("store-refresh", "data"),
    State("store-bodega-filter", "data"),
)
def render_bodega_bar(module, _refresh, bodega_filter):
    if str(module).strip().lower() != "inventario":
        return None
    df = _load_cached("inventario")
    if df.empty or "_bodega" not in df.columns:
        return None
    bodega_options = [{"label": f"Bodega {str(b)}", "value": str(b)}
                      for b in sorted(df["_bodega"].dropna().unique())]
    import json
    current_sel = json.loads(bodega_filter) if isinstance(bodega_filter, str) else bodega_filter
    if not isinstance(current_sel, list):
        current_sel = []
    return html.Div([
        html.Span("Bodega: ", style={"fontSize": "0.78rem", "color": GRAY, "marginRight": "8px", "fontWeight": "500"}),
        dcc.Dropdown(
            id="bodega-dropdown",
            options=bodega_options,
            value=current_sel,
            multi=True,
            debounce=True,
            placeholder="Todas las bodegas (selecciona para filtrar)",
            className="d-inline-block",
            style={"minWidth": "300px", "fontSize": "0.8rem"},
            clearable=True,
        ),
    ], style={"marginBottom": "12px", "display": "flex", "alignItems": "center"})

# ===== BODEGA FILTER CALLBACK =====
@callback(
    Output("store-bodega-filter", "data"),
    Input("bodega-dropdown", "value"),
)
def select_bodega(selected):
    import json
    if not selected or len(selected) == 0:
        return "[]"
    return json.dumps(selected)

# ===== PAGE CONTENT CALLBACK =====
@callback(
    Output("page-content", "children"),
    Input("store-module", "data"),
    Input("store-page", "data"),
    Input("store-filters", "data"),
    Input("store-refresh", "data"),
    Input("store-clear", "data"),
    Input("store-pareto-canal", "data"),
    Input("store-facturas-rango", "data"),
    Input("store-bodega-filter", "data"),
)
def render_page_content(module, page, filters, refresh_count, clear_count, pareto_canal, facturas_range, bodega_filter):
    import json, traceback
    try:
        module = str(module).strip().lower()
        if module not in MODULES:
            module = list(MODULES.keys())[0]
        mod_info = MODULES[module]
        if page not in mod_info["pages"]:
            page = list(mod_info["pages"].keys())[0]
        if isinstance(filters, str):
            try: filters = json.loads(filters)
            except: filters = {}
        if not isinstance(filters, dict):
            filters = {}
        if module == "facturas" and isinstance(facturas_range, list) and len(facturas_range) == 2:
            filters = dict(filters)
            filters["rango"] = facturas_range

        df = _load_cached(module)
        if df.empty:
            return dmc.Alert([html.Div(f"No hay datos para {mod_info['label']}."),
                             html.Div("Sube un archivo Excel en el panel lateral.", className="small mt-1")],
                            title="Sin Datos", color="yellow", withCloseButton=True)
        data = apply_filters(df, filters)
        if data.empty:
            return dmc.Alert("Filtros no devuelven resultados.", title="Sin resultados", color="yellow")

        data = _apply_special_filters(data, module, page, pareto_canal, bodega_filter)

        page_funcs = {
            "pedidos": {"home":pagina_home, "resumen":pagina_resumen,"participacion":pagina_participacion,"pareto":pagina_pareto,
                        "ranking":pagina_ranking,"embudo":pagina_embudo,"heatmap":pagina_heatmap,"proyeccion":pagina_proyeccion},
            "facturas": {"resumen_ventas":pagina_resumen_ventas,"margenes":pagina_margenes,
                         "mix_producto":pagina_mix_producto,"precio_promedio":pagina_precio_promedio},
            "inventario": {"resumen_stock":pagina_resumen_stock,"por_bodega":pagina_por_bodega,"criticos":pagina_criticos},
        }
        func = page_funcs.get(module, {}).get(page)
        if not func:
            return dmc.Alert(f"Pagina no encontrada", title="Error", color="red")
        try:
            content = func(data)
            from firebase_config import is_data_stale, get_upload_age_hours
            if is_data_stale(module):
                age = get_upload_age_hours(module)
                age_text = f" hace {int(age / 24)} dias" if age is not None else ""
                notice = dmc.Alert(
                    f"Actualiza los datos de {mod_info['label']}{age_text}. La actualizacion semanal es cada lunes desde las 6:00 a. m.",
                    title="Actualizacion pendiente",
                    color="yellow", variant="light", withCloseButton=False,
                    className="mb-3",
                )
                content = [notice] + (content if isinstance(content, list) else [content])
            return html.Div(content)
        except Exception as e:
            return dmc.Alert([html.Div(f"Error: {module}/{page}", style={"fontWeight":"bold"}),
                             html.Div(str(e), className="small text-muted mt-1"),
                             html.Div(traceback.format_exc().replace("\n","<br>"), style={"fontSize":"0.6rem","maxHeight":"150px","overflow":"auto"})],
                            title="Error de Pagina", color="red", withCloseButton=True)
    except Exception as e:
        return dmc.Alert([html.Div("ERROR GLOBAL", style={"fontWeight":"bold", "color": RED, "fontSize":"1.2rem"}),
                         html.Div(str(e), style={"fontSize":"0.7rem", "color": RED}),
                         html.Div(traceback.format_exc().replace("\n","<br>"), style={"fontSize":"0.55rem","maxHeight":"200px","overflow":"auto","fontFamily":"monospace"})],
                        title="Error Critico en Dashboard", color="red", withCloseButton=True)

# ===== SINGLE ANALYSIS CALLBACK =====
@callback(
    Output("btn-single-analysis", "disabled"),
    Input("btn-single-analysis", "n_clicks"),
    prevent_initial_call=True,
)
def disable_analysis_button(n_clicks):
    return True


@callback(
    Output("analisis-result", "children"),
    Output("btn-single-analysis", "disabled", allow_duplicate=True),
    Input("btn-single-analysis", "n_clicks"),
    State("store-module", "data"),
    State("store-page", "data"),
    State("store-filters", "data"),
    State("store-api-key", "data"),
    State("store-ai-model", "data"),
    State("store-pareto-canal", "data"),
    State("store-bodega-filter", "data"),
    prevent_initial_call=True,
)
def generate_analysis_single(n_clicks, module, page, filters, api_key, ai_model, pareto_canal, bodega_filter):
    import json
    module = str(module).strip().lower()
    if module not in MODULES: module = list(MODULES.keys())[0]
    if page not in MODULES[module]["pages"]: page = list(MODULES[module]["pages"].keys())[0]
    if isinstance(filters, str):
        try: filters = json.loads(filters)
        except: filters = {}
    if not isinstance(filters, dict): filters = {}

    df = _load_cached(module)
    if df.empty: return html.Div("Sin datos. Sube un archivo primero.", className="text-muted"), False
    data = apply_filters(df, filters)
    if data.empty: return html.Div("Sin resultados con estos filtros.", className="text-muted"), False
    data = _apply_special_filters(data, module, page, pareto_canal, bodega_filter)

    result = None
    if ai_model == "opencode" and api_key:
        result = generar_con_opencode(module, page, data, api_key)
    elif ai_model == "gemini" and api_key:
        result = generar_con_gemini(module, page, data, api_key)

    if not result:
        result = generar_analisis(module, page, data)
    return result, False

# ============================================================
# CALLBACKS
# ============================================================

# Sidebar: update module badges + sidebar info (merged to avoid double data loading)
@callback(
    [Output(f"mod-badge-{k}", "children") for k in MODULES] +
    [Output("sidebar-info", "children")],
    Input("store-refresh", "data"),
    Input("store-clear", "data"),
)
def update_badges_and_sidebar(_refresh, _clear):
    from firebase_config import get_upload_age_hours, is_data_stale, STALE_HOURS
    meta = get_metadata()
    badges = []
    info_lines = []
    alertas = []

    for tipo in ["pedidos", "facturas", "inventario"]:
        count = meta.get(tipo, 0)
        stale = is_data_stale(tipo)
        if count > 0:
            badge_text = f"{count:,} reg"
            if stale:
                badge_text = f"{badge_text} | actualizar"
            badges.append(badge_text)
            info_lines.append(f"{tipo}: {count:,}")
        else:
            badges.append("vacio")
        age = get_upload_age_hours(tipo)
        if age is not None and age > STALE_HOURS:
            alertas.append(f"{tipo}: +{int(age / 24)}d")
        elif stale:
            dias = int(age / 24) if age else 0
            alertas.append(f"{tipo}:   {dias}d (lunes)")

    syncs = meta.get("syncs_remaining", 0)
    sync_info = f"| Firestore: {syncs}/3" if syncs > 0 else "| Firestore: agotado"

    sidebar_lines = []
    if info_lines:
        sidebar_lines.append(html.Div(" | ".join(info_lines),
            style={"color": GREEN, "fontWeight": "bold"}))
    else:
        sidebar_lines.append(html.Div("Sin datos. Sube un archivo.", style={"color": AMBER}))
    sidebar_lines.append(html.Div(sync_info, className="small", style={"color": "#94a3b8"}))
    if alertas:
        sidebar_lines.append(html.Div(
            f"   Datos desactualizados: {', '.join(alertas)}",
            style={"color": RED, "fontWeight": "bold", "fontSize": "0.68rem", "marginTop": "6px", "lineHeight": "1.3"}
        ))

    return tuple(badges) + (html.Div(sidebar_lines),)


# Sidebar: show last uploaded file for current module
@callback(
    Output("mod-last-file", "children"),
    Input("store-module", "data"),
    Input("store-refresh", "data"),
)
def update_last_file(module, _refresh):
    from firebase_config import get_last_files
    module = str(module).strip().lower()
    if module not in MODULES:
        module = "pedidos"
    files = get_last_files()
    fname = files.get(module, "")
    if fname:
        return f"Ultimo: {fname}"
    return ""


# Sidebar: reload module from last saved parquet
@callback(
    Output("reload-status", "children"),
    Output("store-refresh", "data", allow_duplicate=True),
    Input("btn-reload-module", "n_clicks"),
    State("store-module", "data"),
    State("store-refresh", "data"),
    prevent_initial_call=True,
)
def reload_module(n, module, count):
    module = str(module).strip().lower()
    if module not in MODULES:
        return html.Div("Modulo invalido.", style={"color": RED}), no_update
    _clear_cache(module)
    from firebase_config import load_local
    df = load_local(module)
    if df.empty:
        return html.Div("No hay datos guardados. Sube un archivo primero.", style={"color": AMBER}), no_update
    _data_cache[module] = df.copy()
    _cache_timestamps[module] = time.time()
    return html.Div(f"Recargado: {len(df):,} registros.", style={"color": GREEN}), count + 1


# Sidebar: update upload section title
@callback(
    Output("upload-module-title", "children"),
    Input("store-module", "data"),
)
def update_upload_title(module):
    mod = MODULES.get(str(module).strip().lower(), MODULES["pedidos"])
    return f"{mod['label']} — Subir archivo"


@callback(
    Output("file-name", "children"),
    Input("upload-data", "filename"),
)
def show_file_name(filename):
    return f"Archivo: {filename}" if filename else ""


@callback(
    Output("store-module", "data"),
    Output("store-page", "data"),
    Output("file-name", "children"),
    Output("upload-status", "children"),
    Input("mod-pedidos", "n_clicks"),
    Input("mod-facturas", "n_clicks"),
    Input("mod-inventario", "n_clicks"),
    State("store-page", "data"),
    prevent_initial_call=True,
)
def switch_module(*args):
    clicks = args[:3]
    current_page = args[3]
    ctx = dash.ctx
    if not ctx.triggered:
        return no_update, no_update, no_update, no_update
    mod_id = ctx.triggered[0]["prop_id"].split(".")[0]
    module = mod_id.replace("mod-", "")
    pages = MODULES[module]["pages"]
    if current_page in pages:
        page = current_page
    else:
        page = list(pages.keys())[0]
    return module, page, "", ""


@callback(
    Output("mod-pedidos", "style"),
    Output("mod-facturas", "style"),
    Output("mod-inventario", "style"),
    Output("mod-text-pedidos", "style"),
    Output("mod-text-facturas", "style"),
    Output("mod-text-inventario", "style"),
    Output("mod-dot-pedidos", "children"),
    Output("mod-dot-facturas", "children"),
    Output("mod-dot-inventario", "children"),
    Output("mod-badge-pedidos", "style"),
    Output("mod-badge-facturas", "style"),
    Output("mod-badge-inventario", "style"),
    Input("store-module", "data"),
)
def highlight_active_module(module):
    BASE = {
        "borderRadius": "8px",
        "padding": "12px 14px",
        "marginBottom": "10px",
        "transition": "all 0.3s",
    }
    styles = {}
    texts = {}
    dots = {}
    badges = {}
    for key, mod in MODULES.items():
        active = key == module
        color = mod["color"]
        if active:
            styles[f"mod-{key}"] = {
                **BASE,
                "backgroundColor": f"rgba(255,255,255,0.15)",
                "border": f"1px solid {color}",
                "borderLeft": f"8px solid {color}",
                "boxShadow": f"0 0 20px {color}44, inset 0 0 30px {color}10",
                "opacity": "1",
            }
            texts[f"mod-text-{key}"] = {
                "fontSize": "0.95rem", "fontWeight": "bold",
                "color": "white",
            }
            dots[f"mod-dot-{key}"] = "●"
            badges[f"mod-badge-{key}"] = {
                "fontSize": "0.7rem", "color": color, "fontWeight": "bold",
            }
        else:
            styles[f"mod-{key}"] = {
                **BASE,
                "backgroundColor": "rgba(255,255,255,0.08)",
                "border": "1px solid rgba(255,255,255,0.12)",
                "borderLeft": f"4px solid {color}88",
                "opacity": "0.85",
            }
            texts[f"mod-text-{key}"] = {
                "fontSize": "0.95rem", "fontWeight": "normal",
                "color": "#94a3b8",
            }
            dots[f"mod-dot-{key}"] = ""
            badges[f"mod-badge-{key}"] = {
                "fontSize": "0.7rem", "color": "#94a3b8",
            }
    return (
        styles["mod-pedidos"], styles["mod-facturas"], styles["mod-inventario"],
        texts["mod-text-pedidos"], texts["mod-text-facturas"], texts["mod-text-inventario"],
        dots["mod-dot-pedidos"], dots["mod-dot-facturas"], dots["mod-dot-inventario"],
        badges["mod-badge-pedidos"], badges["mod-badge-facturas"], badges["mod-badge-inventario"],
    )


@callback(
    Output("upload-status", "children"),
    Output("store-refresh", "data"),
    Output("store-module", "data", allow_duplicate=True),
    Output("store-tipo", "data"),
    Output("store-page", "data", allow_duplicate=True),
    Output("store-filters", "data", allow_duplicate=True),
    Input("btn-process", "n_clicks"),
    State("upload-data", "contents"),
    State("upload-data", "filename"),
    State("store-refresh", "data"),
    State("store-module", "data"),
    prevent_initial_call=True,
)
def process_upload(n_clicks, contents, filename, refresh_count, active_module):
    import json
    if not contents:
        return html.Div("Selecciona un archivo Excel primero.", style={"color": AMBER}), no_update, no_update, no_update, no_update, no_update
    if not filename:
        return html.Div("Selecciona un archivo.", style={"color": AMBER}), no_update, no_update, no_update, no_update, no_update
    if not filename.endswith((".xlsx", ".xls")):
        return html.Div("Solo archivos Excel.", style={"color": RED}), no_update, no_update, no_update, no_update, no_update
    try:
        content_type, content_string = contents.split(",", 1)
        decoded = base64.b64decode(content_string)
        CARPETA_ENTRADA.mkdir(parents=True, exist_ok=True)
        ruta = CARPETA_ENTRADA / filename
        with open(ruta, "wb") as f:
            f.write(decoded)

        tipo, sheet = detectar_tipo(str(ruta))
        if tipo == "generic":
            return html.Div([
                html.Div(f"No se pudo identificar el tipo de archivo", style={"color": RED, "fontWeight": "bold"}),
                html.Div(f"Columnas encontradas no coinciden con pedidos, facturas ni inventario.", className="small", style={"color": "#f87171"}),
                html.Div(f"Verifica que el archivo tenga las columnas requeridas.", className="small mt-1", style={"color": GRAY}),
            ]), no_update, no_update, no_update, no_update, no_update
        df_raw = pd.read_excel(str(ruta), sheet_name=sheet)
        df_norm = normalizar(df_raw, tipo)
        df_proc = procesar_etl(df_norm)
        n_reg = try_save(df_proc, tipo, filename)
        _data_cache[tipo] = df_proc.copy()
        _cache_timestamps[tipo] = time.time()

        if tipo not in MODULES:
            tipo = str(active_module).strip().lower()
        if tipo not in MODULES:
            tipo = "pedidos"
        first_page = list(MODULES[tipo]["pages"].keys())[0]

        current_mod = str(active_module).strip().lower()
        switch_msg = ""
        if current_mod != tipo:
            switch_msg = html.Div(f"   Cambia al modulo {tipo.upper()} para ver los datos",
                                  style={"color": GRAY, "fontSize": "0.7rem"})

        return html.Div([
            html.Div(f"OK: {filename}", style={"color": "#93c5fd"}),
            html.Div(f"{tipo.upper()}: {n_reg:,} registros guardados",
                     style={"color": GREEN, "fontWeight": "bold"}),
            switch_msg,
        ]), refresh_count + 1, no_update, tipo, no_update, json.dumps({})
    except Exception as e:
        detalle = traceback.format_exc()
        print(detalle)
        return html.Div([
            html.Div("Error procesando archivo", style={"color": RED, "fontWeight": "bold"}),
            html.Div(str(e), className="small", style={"color": "#f87171"}),
        ]), no_update, no_update, no_update, no_update, no_update




@callback(
    Output("download-data", "data"),
    Input("btn-download-csv", "n_clicks"),
    State("store-module", "data"),
    State("store-filters", "data"),
    State("store-pareto-canal", "data"),
    State("store-facturas-rango", "data"),
    State("store-bodega-filter", "data"),
    prevent_initial_call=True,
)
def download_csv(n, module, filters, pareto_canal, facturas_range, bodega_filter):
    import json, io
    if not n:
        return no_update
    try:
        if isinstance(filters, str):
            try: filters = json.loads(filters)
            except: filters = {}
        if not isinstance(filters, dict):
            filters = {}
        if str(module).strip().lower() == "facturas" and isinstance(facturas_range, list) and len(facturas_range) == 2:
            filters = dict(filters)
            filters["rango"] = facturas_range
        df = _load_cached(module)
        if df.empty:
            return dict(content="Sin datos. Sube un archivo Excel primero.", filename="sin_datos.txt")
        data = apply_filters(df, filters)
        if data.empty:
            return dict(content="No hay datos con los filtros actuales.", filename="sin_resultados.txt")
        data = _apply_special_filters(data, module, "", pareto_canal, bodega_filter)
        buffer = io.StringIO()
        data.to_csv(buffer, index=False, encoding="utf-8-sig")
        return dict(content=buffer.getvalue(), filename=f"dashboard_{module}.csv")
    except Exception:
        return no_update


@callback(
    Output("clear-status", "children"),
    Output("store-clear", "data"),
    Output("store-filters", "data", allow_duplicate=True),
    Output("store-pareto-canal", "data", allow_duplicate=True),
    Input("clear-data", "n_clicks"),
    State("store-clear", "data"),
    prevent_initial_call=True,
)
def clear_data(n, clear_count):
    return no_update, no_update, no_update, no_update


@callback(
    Output("confirm-clear", "displayed"),
    Input("clear-data", "n_clicks"),
    prevent_initial_call=True,
)
def show_clear_confirm(n):
    return True


@callback(
    Output("clear-status", "children"),
    Output("store-clear", "data"),
    Output("store-filters", "data", allow_duplicate=True),
    Output("store-pareto-canal", "data", allow_duplicate=True),
    Input("confirm-clear", "submit_n_clicks"),
    State("store-clear", "data"),
    prevent_initial_call=True,
)
def execute_clear_confirmed(submit_n, clear_count):
    import json
    if not submit_n:
        return no_update, no_update, no_update, no_update
    _clear_cache()
    clear_local_cache()
    return (
        html.Div("Datos limpiados.", style={"color": GREEN}),
        (clear_count or 0) + 1,
        json.dumps({}),
        "TODOS",
    )
@callback(
    Output("store-refresh", "data", allow_duplicate=True),
    Input("refresh-data", "n_clicks"),
    State("store-refresh", "data"),
    prevent_initial_call=True,
)
def refresh_data(n, count):
    _clear_cache()
    return count + 1


@callback(
    Output("cloud-status", "children"),
    Output("store-refresh", "data", allow_duplicate=True),
    Input("btn-save-cloud", "n_clicks"),
    State("store-refresh", "data"),
    prevent_initial_call=True,
)
def save_to_cloud(n, count):
    from firebase_config import save_all_to_firestore
    results = save_all_to_firestore()
    lines = []
    for tipo, (n_reg, status) in results.items():
        if n_reg > 0:
            lines.append(f"{tipo}: {n_reg:,} reg guardados")
        else:
            lines.append(f"{tipo}: {status}")
    return html.Div("Guardado: " + " | ".join(lines), style={"color": GREEN}), count + 1


@callback(
    Output("cloud-status", "children", allow_duplicate=True),
    Output("store-refresh", "data", allow_duplicate=True),
    Input("btn-load-cloud", "n_clicks"),
    State("store-refresh", "data"),
    prevent_initial_call=True,
)
def load_from_cloud(n, count):
    from firebase_config import load_all_from_firestore
    _clear_cache()
    results = load_all_from_firestore()
    lines = []
    for tipo, (n_reg, status) in results.items():
        if n_reg > 0:
            lines.append(f"{tipo}: {n_reg:,} reg cargados")
        else:
            lines.append(f"{tipo}: {status}")
    return html.Div("Cargado: " + " | ".join(lines), style={"color": GREEN}), count + 1


@callback(
    Output("api-status", "children"),
    Output("store-api-key", "data"),
    Output("store-ai-model", "data"),
    Input("btn-verify-api", "n_clicks"),
    State("api-key-input", "value"),
    State("ai-model-select", "value"),
    prevent_initial_call=True,
)
def verify_model(n, api_key, model):
    if not api_key or not api_key.strip():
        return html.Div("Ingresa una API Key.", style={"color": AMBER}), no_update, no_update
    import requests
    key = api_key.strip()
    if model == "opencode":
        try:
            resp = requests.post("https://api.opencode.ai/v1/chat/completions",
                json={"model": "opencode", "messages": [{"role":"user","content":"hi"}]},
                headers={"Authorization": f"Bearer {key}"}, timeout=8)
            if resp.ok:
                return html.Div("OpenCode verificado", style={"color": GREEN, "fontWeight":"bold"}), key, model
            code = resp.status_code
            return html.Div(f"Error {code}: {'clave invalida' if code==401 else 'servidor'}", style={"color": RED}), no_update, no_update
        except Exception:
            return html.Div("Sin conexion con OpenCode", style={"color": RED}), no_update, no_update
    elif model == "gemini":
        try:
            resp = requests.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
                params={"key": key}, json={"contents":[{"parts":[{"text":"hi"}]}]}, timeout=8)
            if resp.ok:
                return html.Div("Gemini verificado", style={"color": GREEN, "fontWeight":"bold"}), key, model
            code = resp.status_code
            msg = "clave invalida" if code == 400 else "limite excedido" if code == 429 else str(code)
            return html.Div(f"Error {code}: {msg}", style={"color": RED}), no_update, no_update
        except Exception:
            return html.Div("Sin conexion con Gemini", style={"color": RED}), no_update, no_update
    else:
        return html.Div("Modo local activado", style={"color": GRAY}), api_key if api_key and api_key.strip() else "", "local"


# Navigation via pattern-matching buttons
@callback(
    Output("store-page", "data", allow_duplicate=True),
    Output("analisis-result", "children", allow_duplicate=True),
    Input({"type": "nav-btn", "page": ALL}, "n_clicks"),
    State("store-page", "data"),
    prevent_initial_call=True,
)
def navigate_buttons(n_clicks, current_page):
    import json
    ctx = dash.ctx
    if not ctx.triggered:
        return no_update, no_update
    triggered = ctx.triggered[0]["prop_id"]
    obj = json.loads(triggered.split(".")[0])
    page = obj["page"]
    if page == current_page:
        return no_update, no_update
    return page, ""


# Pareto canal selector callback
@callback(
    Output("store-pareto-canal", "data", allow_duplicate=True),
    Input({"type": "canal-btn", "name": ALL}, "n_clicks"),
    State("store-pareto-canal", "data"),
    prevent_initial_call=True,
)
def select_pareto_canal(n_clicks, current):
    import json
    ctx = dash.ctx
    if not ctx.triggered:
        return no_update
    triggered = ctx.triggered[0]["prop_id"]
    obj = json.loads(triggered.split(".")[0])
    name = obj["name"]
    return name if name != current else no_update


# ===== HOME NAVIGATION: Click "Ir al modulo" → switch module =====
@callback(
    Output("store-module", "data", allow_duplicate=True),
    Output("store-page", "data", allow_duplicate=True),
    Input({"type": "home-nav", "mod": ALL, "page": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def home_navigate_module(n_clicks):
    import json
    ctx = dash.ctx
    if not ctx.triggered or not n_clicks or all(nc is None for nc in n_clicks):
        return no_update, no_update
    triggered = ctx.triggered[0]["prop_id"]
    obj = json.loads(triggered.split(".")[0])
    return obj.get("mod", "pedidos"), obj.get("page", "resumen")


# ===== CROSS-FILTERING: Click en gráfico → actualizar store-filters =====
@callback(
    Output("store-pareto-canal", "data", allow_duplicate=True),
    Input("chart-canal-pie", "clickData"),
    prevent_initial_call=True,
)
def crossfilter_canal(clickData):
    if not clickData:
        return no_update
    try:
        canal = clickData["points"][0]["label"]
        return canal
    except Exception:
        return no_update


@callback(
    Output("store-filters", "data", allow_duplicate=True),
    Input("chart-asesor-participacion", "clickData"),
    Input("chart-ranking-asesores", "clickData"),
    State("store-filters", "data"),
    prevent_initial_call=True,
)
def crossfilter_asesor(click_part, click_rank, current_json):
    import json
    ctx = dash.ctx
    if not ctx.triggered:
        return no_update
    try:
        clickData = ctx.triggered[0]["value"]
        if not clickData:
            return no_update
        asesor = clickData["points"][0].get("y") or clickData["points"][0].get("label")
        if asesor:
            try:
                filters = json.loads(current_json) if isinstance(current_json, str) else (current_json or {})
            except Exception:
                filters = {}
            filters = dict(filters)
            filters["asesor"] = asesor
            return json.dumps(filters)
    except Exception:
        pass
    return no_update


@callback(
    Output("sidebar-toggle", "style"),
    Input("stale-interval", "n_intervals"),
    prevent_initial_call=False,
)
def check_stale_periodic(_n):
    from firebase_config import is_data_stale
    styles = {
        "display": "none", "position": "fixed", "top": "10px", "left": "10px",
        "zIndex": 1100, "background": "#1e293b", "color": "white", "border": "none",
        "fontSize": "1.5rem", "width": "40px", "height": "40px", "borderRadius": "8px",
        "cursor": "pointer",
    }
    for mod in ["pedidos", "facturas", "inventario"]:
        if is_data_stale(mod):
            styles["background"] = "#b91c1c"
            styles["color"] = "#fef2f2"
            break
    return styles
