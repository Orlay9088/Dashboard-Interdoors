import base64
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

from firebase_config import try_load, try_save, is_cache_stale, mark_cache_fresh, get_metadata, load_local, clear_local_cache
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

def _load_cached(module):
    if is_cache_stale():
        _clear_cache()
        mark_cache_fresh()
    if module in _data_cache and _data_cache[module] is not None:
        return _data_cache[module].copy()
    df, backend = try_load(module)
    if not df.empty:
        _data_cache[module] = df.copy()
    return df

def _clear_cache(module=None):
    if module:
        _data_cache.pop(module, None)
    else:
        _data_cache.clear()

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

PAGE_ROUTES = {}
ALL_PAGE_KEYS = set()
for mod_key, mod_val in MODULES.items():
    for page_key in mod_val["pages"]:
        PAGE_ROUTES[f"{mod_key}_{page_key}"] = (mod_key, page_key)
        ALL_PAGE_KEYS.add(page_key)

MODULE_LABELS = [v["label"] for v in MODULES.values()]
MODULE_COLORS = {k: v["color"] for k, v in MODULES.items()}

SIDEBAR_STYLE = {
    "position": "fixed", "top": 0, "left": 0, "bottom": 0,
    "width": "260px", "padding": "1rem", "backgroundColor": DARKGRAY,
    "color": "white", "overflowY": "auto", "zIndex": 1000,
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
    return html.Div(children, style=SIDEBAR_STYLE)


app.layout = html.Div([
    dcc.Store(id="store-module", data="pedidos"),
    dcc.Store(id="store-page", data="resumen"),
    dcc.Store(id="store-filters", data="{}"),
    dcc.Store(id="store-refresh", data=0),
    dcc.Store(id="store-clear", data=0),
    dcc.Store(id="store-tipo", data="pedidos"),
    dcc.Store(id="store-pareto-canal", data="TODOS"),
    dcc.Store(id="store-bodega-filter", data="[]"),
    build_sidebar(),
    html.Div([
        html.Div(id="nav-bar"),
        html.Div(id="canal-bar"),
        html.Div(id="bodega-bar"),
        dcc.Loading(
            html.Div(id="page-content"),
            type="circle", color=BLUE,
        ),
        html.Hr(style={"margin": "16px 0"}),
        html.Div([
            html.Button("   Analizar con IA   ",
                id="btn-single-analysis",
                style={
                    "backgroundColor": GOLD, "color": DARKGRAY, "border": f"1px solid {GOLD}",
                    "fontSize": "0.85rem", "padding": "8px 24px", "borderRadius": "6px",
                    "cursor": "pointer", "fontWeight": "bold",
                }
            ),
        ], style={"textAlign": "center", "marginBottom": "12px"}),
        html.Div(id="analisis-result", style={"padding": "12px", "backgroundColor": "#F5F5F0",
            "borderRadius": "8px", "border": "1px solid #e5e7eb", "minHeight": "50px"}),
    ], style=CONTENT_STYLE),
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

# ===== CANAL BAR CALLBACK (Pareto) =====
@callback(
    Output("canal-bar", "children"),
    Input("store-module", "data"),
    Input("store-page", "data"),
    Input("store-pareto-canal", "data"),
    Input("store-refresh", "data"),
)
def render_canal_bar(module, page, pareto_canal, _refresh):
    if not (str(module).strip().lower() == "pedidos" and page == "pareto"):
        return None
    df = _load_cached("pedidos")
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
        html.Span(buttons, style={"display": "inline-flex", "flexWrap": "wrap"}),
    ], style={"marginBottom": "12px"})

# ===== BODEGA BAR CALLBACK (Inventario) =====
@callback(
    Output("bodega-bar", "children"),
    Input("store-module", "data"),
    Input("store-refresh", "data"),
)
def render_bodega_bar(module, _refresh):
    if str(module).strip().lower() != "inventario":
        return None
    df = _load_cached("inventario")
    if df.empty or "_bodega" not in df.columns:
        return None
    bodega_options = [{"label": f"Bodega {str(b)}", "value": str(b)}
                      for b in sorted(df["_bodega"].dropna().unique())]
    return html.Div([
        html.Span("Bodega: ", style={"fontSize": "0.78rem", "color": GRAY, "marginRight": "8px", "fontWeight": "500"}),
        dcc.Dropdown(
            id="bodega-dropdown",
            options=bodega_options,
            value=[],
            multi=True,
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
    Input("store-bodega-filter", "data"),
)
def render_page_content(module, page, filters, refresh_count, clear_count, pareto_canal, bodega_filter):
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

        df = _load_cached(module)
        if df.empty:
            return dmc.Alert([html.Div(f"No hay datos para {mod_info['label']}."),
                             html.Div("Sube un archivo Excel en el panel lateral.", className="small mt-1")],
                            title="Sin Datos", color="yellow", withCloseButton=True)
        data = apply_filters(df, filters)
        if data.empty:
            return dmc.Alert("Filtros no devuelven resultados.", title="Sin resultados", color="yellow")

        if module == "pedidos" and page == "pareto" and pareto_canal != "TODOS":
            data = data[data["_canal"] == pareto_canal]
        if module == "inventario" and bodega_filter and bodega_filter != "[]" and "_bodega" in data.columns:
            try:
                selected = json.loads(bodega_filter)
                if selected:
                    data = data[data["_bodega"].astype(str).isin(selected)]
            except Exception:
                pass

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
            return html.Div(func(data))
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
    Output("analisis-result", "children"),
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
    if df.empty: return html.Div("Sin datos. Sube un archivo primero.", className="text-muted")
    data = apply_filters(df, filters)
    if data.empty: return html.Div("Sin resultados con estos filtros.", className="text-muted")
    if module == "pedidos" and page == "pareto" and pareto_canal != "TODOS":
        data = data[data["_canal"] == pareto_canal]
    if module == "inventario" and bodega_filter and bodega_filter != "[]" and "_bodega" in data.columns:
        try:
            selected = json.loads(bodega_filter)
            if selected:
                data = data[data["_bodega"].astype(str).isin(selected)]
        except Exception:
            pass

    result = None
    if ai_model == "opencode" and api_key:
        result = generar_con_opencode(module, page, data, api_key)
    elif ai_model == "gemini" and api_key:
        result = generar_con_gemini(module, page, data, api_key)

    if not result:
        result = generar_analisis(module, page, data)
    return result

# ============================================================
# CALLBACKS
# ============================================================

# Sidebar: update module badges with record counts
@callback(
    [Output(f"mod-badge-{k}", "children") for k in MODULES],
    Input("store-refresh", "data"),
    Input("store-clear", "data"),
)
def update_module_badges(_refresh, _clear):
    results = []
    for key in MODULES:
        df = _load_cached(key)
        if not df.empty:
            results.append(f"{len(df):,} reg")
        else:
            results.append("vacio")
    return results


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
    df = _load_cached(module)
    if df.empty:
        return html.Div("No hay datos guardados. Sube un archivo primero.", style={"color": AMBER}), no_update
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
    Output("analisis-result", "children"),
    Input("mod-pedidos", "n_clicks"),
    Input("mod-facturas", "n_clicks"),
    Input("mod-inventario", "n_clicks"),
    prevent_initial_call=True,
)
def switch_module(*args):
    ctx = dash.ctx
    if not ctx.triggered:
        return no_update, no_update, no_update, no_update, no_update
    mod_id = ctx.triggered[0]["prop_id"].split(".")[0]
    module = mod_id.replace("mod-", "")
    first_page = list(MODULES[module]["pages"].keys())[0]
    return module, first_page, "", "", ""


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
    Input("store-refresh", "data"),
    Input("store-clear", "data"),
)
def highlight_active_module(module, _refresh, _clear):
    import pandas as pd
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
    Input("btn-process", "n_clicks"),
    State("upload-data", "contents"),
    State("upload-data", "filename"),
    State("store-refresh", "data"),
    State("store-module", "data"),
    prevent_initial_call=True,
)
def process_upload(n_clicks, contents, filename, refresh_count, active_module):
    if not contents:
        return html.Div("Selecciona un archivo Excel primero.", style={"color": AMBER}), no_update, no_update, no_update, no_update
    if not filename:
        return html.Div("Selecciona un archivo.", style={"color": AMBER}), no_update, no_update, no_update, no_update
    if not filename.endswith((".xlsx", ".xls")):
        return html.Div("Solo archivos Excel.", style={"color": RED}), no_update, no_update, no_update, no_update
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
            ]), no_update, no_update, no_update, no_update
        df_raw = pd.read_excel(str(ruta), sheet_name=sheet)
        df_norm = normalizar(df_raw, tipo)
        df_proc = procesar_etl(df_norm)
        n_reg = try_save(df_proc, tipo, filename)
        _clear_cache(tipo)
        time.sleep(0.1)

        if tipo not in MODULES:
            tipo = str(active_module).strip().lower()
        if tipo not in MODULES:
            tipo = "pedidos"
        first_page = list(MODULES[tipo]["pages"].keys())[0]

        return html.Div([
            html.Div(f"OK: {filename}", style={"color": "#93c5fd"}),
            html.Div(f"Tipo: {tipo} | {n_reg:,} registros guardados",
                     style={"color": GREEN, "fontWeight": "bold"}),
        ]), refresh_count + 1, tipo, tipo, first_page
    except Exception as e:
        detalle = traceback.format_exc()
        print(detalle)
        return html.Div([
            html.Div("Error procesando archivo", style={"color": RED, "fontWeight": "bold"}),
            html.Div(str(e), className="small", style={"color": "#f87171"}),
        ]), no_update, no_update, no_update, no_update




@callback(
    Output("download-data", "data"),
    Input("btn-download-csv", "n_clicks"),
    State("store-module", "data"),
    State("store-filters", "data"),
    State("store-pareto-canal", "data"),
    State("store-bodega-filter", "data"),
    prevent_initial_call=True,
)
def download_csv(n, module, filters, pareto_canal, bodega_filter):
    import json, io
    if not n:
        return no_update
    try:
        if isinstance(filters, str):
            try: filters = json.loads(filters)
            except: filters = {}
        if not isinstance(filters, dict):
            filters = {}
        df = _load_cached(module)
        if df.empty:
            return dict(content="Sin datos. Sube un archivo Excel primero.", filename="sin_datos.txt")
        data = apply_filters(df, filters)
        if data.empty:
            return dict(content="No hay datos con los filtros actuales.", filename="sin_resultados.txt")
        if module == "pedidos" and pareto_canal and pareto_canal != "TODOS":
            data = data[data["_canal"] == pareto_canal]
        if module == "inventario" and bodega_filter and bodega_filter != "[]" and "_bodega" in data.columns:
            try:
                selected = json.loads(bodega_filter)
                if selected:
                    data = data[data["_bodega"].astype(str).isin(selected)]
            except: pass
        buffer = io.StringIO()
        data.to_csv(buffer, index=False, encoding="utf-8-sig")
        return dict(content=buffer.getvalue(), filename=f"dashboard_{module}.csv")
    except Exception:
        return no_update


@callback(
    Output("clear-status", "children"),
    Output("store-clear", "data"),
    Input("clear-data", "n_clicks"),
    State("store-clear", "data"),
    prevent_initial_call=True,
)
def clear_data(n, clear_count):
    _clear_cache()
    clear_local_cache()
    return html.Div("Datos limpiados.", style={"color": GREEN}), clear_count + 1


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
    Output("sidebar-info", "children"),
    Input("store-refresh", "data"),
    Input("store-clear", "data"),
)
def update_sidebar_info(n, _clear):
    info = []
    for tipo in ["pedidos", "facturas", "inventario"]:
        df = _load_cached(tipo)
        if not df.empty:
            info.append(f"{tipo}: {len(df):,}")
    meta = get_metadata()
    syncs = meta.get("syncs_remaining", 0)
    sync_info = f"| Firestore: {syncs}/3" if syncs > 0 else "| Firestore: agotado"
    lines = []
    if info:
        lines.append(html.Div(" | ".join(info), style={"color": GREEN, "fontWeight": "bold"}))
    else:
        lines.append(html.Div("Sin datos. Sube un archivo.", style={"color": AMBER}))
    lines.append(html.Div(sync_info, className="small", style={"color": "#94a3b8"}))
    return html.Div(lines)





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
    Output("store-pareto-canal", "data"),
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
    Output("store-filters", "data", allow_duplicate=True),
    Input("chart-canal-pie", "clickData"),
    prevent_initial_call=True,
)
def crossfilter_canal(clickData):
    import json
    if not clickData:
        return no_update
    try:
        canal = clickData["points"][0]["label"]
        return json.dumps({"canal": canal, "asesor": "Todos", "estado": "Todos", "linea": "Todos", "sublinea": "Todos"})
    except Exception:
        return no_update


@callback(
    Output("store-filters", "data", allow_duplicate=True),
    Input("chart-asesor-participacion", "clickData"),
    Input("chart-ranking-asesores", "clickData"),
    prevent_initial_call=True,
)
def crossfilter_asesor(click_part, click_rank):
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
            return json.dumps({"canal": "Todos", "asesor": asesor, "estado": "Todos", "linea": "Todos", "sublinea": "Todos"})
    except Exception:
        pass
    return no_update


@callback(
    Output("store-filters", "data", allow_duplicate=True),
    Input("clear-data", "n_clicks"),
    prevent_initial_call=True,
)
def clear_filters_on_clear(n):
    import json
    if n:
        return json.dumps({})
    return no_update


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8503))
    app.run(debug=False, host="0.0.0.0", port=port, threaded=True)
