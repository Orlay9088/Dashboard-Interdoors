import base64
import traceback
from datetime import datetime
from pathlib import Path
import sys

import dash
from dash import dcc, html, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import CARPETA_ENTRADA
from pages.components import NAVY, BLUE, AMBER, GREEN, RED, GRAY, apply_filters
from etl.detector import detectar_tipo
from etl.normalizer import normalizar
from etl.processor import procesar as procesar_etl
from etl.uploader import subir_a_firestore
from firebase_config import get_db, load_from_firestore, get_metadata, set_metadata
from analysis import generar_analisis, generar_con_gemini
from pages.pedidos import (
    pagina_resumen, pagina_participacion, pagina_pareto,
    pagina_ranking, pagina_embudo, pagina_heatmap, pagina_proyeccion,
)
from pages.facturas import (
    pagina_resumen_ventas, pagina_margenes, pagina_mix_producto, pagina_precio_promedio,
)
from pages.inventario import (
    pagina_resumen_stock, pagina_por_bodega, pagina_criticos,
)

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

MODULES = {
    "pedidos": {"label": "Pedidos", "icon": "", "pages": {
        "resumen": "Resumen", "participacion": "Participacion",
        "pareto": "Pareto", "ranking": "Ranking", "embudo": "Embudo",
        "heatmap": "Heatmap", "proyeccion": "Proyeccion",
    }},
    "facturas": {"label": "Facturacion", "icon": "", "pages": {
        "resumen_ventas": "Resumen", "margenes": "Margenes",
        "mix_producto": "Mix Producto", "precio_promedio": "Precio Prom.",
    }},
    "inventario": {"label": "Inventario", "icon": "", "pages": {
        "resumen_stock": "Resumen", "por_bodega": "Por Bodega",
        "criticos": "Criticos",
    }},
}

PAGE_ROUTES = {}
for mod_key, mod_val in MODULES.items():
    for page_key in mod_val["pages"]:
        PAGE_ROUTES[f"{mod_key}_{page_key}"] = (mod_key, page_key)

SIDEBAR_STYLE = {
    "position": "fixed", "top": 0, "left": 0, "bottom": 0,
    "width": "260px", "padding": "1rem", "backgroundColor": NAVY,
    "color": "white", "overflowY": "auto", "zIndex": 1000,
}
CONTENT_STYLE = {"marginLeft": "260px", "padding": "1.5rem", "background": "#f8fafc", "minHeight": "100vh"}


# ============================================================
# LAYOUT
# ============================================================
def build_sidebar():
    children = [
        html.H5("Dashboard Interdoors", className="fw-bold mb-3 text-center", style={"color": "white"}),

        html.H6("Modulo", className="text-uppercase small fw-semibold mb-2", style={"color": "#94a3b8"}),
    ]
    for key, mod in MODULES.items():
        children.append(dbc.Button(
            mod["label"], id=f"mod-{key}", color="primary",
            className="w-100 mb-1", size="sm",
            style={"backgroundColor": "transparent", "borderColor": "rgba(255,255,255,0.2)"},
        ))

    children.append(html.Hr(style={"borderColor": "rgba(255,255,255,0.15)"}))

    children.extend([
        html.H6("Subir archivo", className="text-uppercase small fw-semibold mb-2", style={"color": "#94a3b8"}),
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
        html.Div(id="file-name", className="small", style={"color": "#93c5fd"}),
        dbc.Button("Procesar archivo", id="btn-process", color="primary", size="sm", className="w-100 mb-1"),
        html.Div(id="upload-status", style={"fontSize": "0.8rem", "minHeight": "2rem"}),
        html.Hr(style={"borderColor": "rgba(255,255,255,0.15)"}),

        html.H6("Filtros", className="text-uppercase small fw-semibold mb-2", style={"color": "#94a3b8"}),
        html.Label("Periodo", className="form-label small", style={"color": "white"}),
        dcc.DatePickerRange(id="date-range", className="mb-2 w-100", display_format="DD/MM/YYYY"),
        html.Label("Asesor", className="form-label small", style={"color": "white"}),
        dcc.Dropdown(id="dropdown-asesor", options=[], value="Todos", clearable=False, className="mb-2 small"),
        html.Label("Canal", className="form-label small", style={"color": "white"}),
        dcc.Dropdown(id="dropdown-canal", options=[], value="Todos", clearable=False, className="mb-2 small"),
        html.Label("Estado", className="form-label small", style={"color": "white"}),
        dcc.Dropdown(id="dropdown-estado", options=[], value="Todos", clearable=False, className="mb-2 small"),
        html.Hr(style={"borderColor": "rgba(255,255,255,0.15)"}),

        dbc.Button("Refrescar datos", id="refresh-data", color="light", size="sm", className="w-100 mb-1 text-dark"),
        dbc.Button("Limpiar datos", id="clear-data", color="danger", size="sm", className="w-100 mb-1"),
        html.Div(id="clear-status", style={"fontSize": "0.8rem", "minHeight": "1.5rem"}),
        html.Hr(style={"borderColor": "rgba(255,255,255,0.15)"}),

        html.H6("Gemini AI", className="text-uppercase small fw-semibold mb-2", style={"color": "#94a3b8"}),
        dbc.Input(id="api-key-input", type="password", placeholder="API Key Gemini", size="sm", className="mb-1",
                  style={"fontSize": "0.8rem"}),
        dbc.Button("Verificar API", id="btn-verify-api", color="success", size="sm", className="w-100 mb-1"),
        html.Div(id="api-status", style={"fontSize": "0.75rem", "color": "#94a3b8", "minHeight": "1.2rem"}),
        dcc.Store(id="store-api-key", data=""),
        html.Hr(style={"borderColor": "rgba(255,255,255,0.15)"}),
        html.Div(id="sidebar-info", className="small", style={"color": "#94a3b8"}),
    ])
    return html.Div(children, style=SIDEBAR_STYLE)


app.layout = html.Div([
    dcc.Store(id="store-module", data="pedidos"),
    dcc.Store(id="store-page", data="resumen"),
    dcc.Store(id="store-filters", data={}),
    dcc.Store(id="store-refresh", data=0),
    dcc.Store(id="store-clear", data=0),
    dcc.Store(id="store-tipo", data="pedidos"),
    build_sidebar(),
    html.Div(id="page-content", style=CONTENT_STYLE),
])

# ============================================================
# CALLBACKS
# ============================================================

@callback(
    Output("file-name", "children"),
    Input("upload-data", "filename"),
)
def show_file_name(filename):
    return f"Archivo: {filename}" if filename else ""


@callback(
    Output("store-module", "data"),
    Output("store-page", "data"),
    Input("mod-pedidos", "n_clicks"),
    Input("mod-facturas", "n_clicks"),
    Input("mod-inventario", "n_clicks"),
    prevent_initial_call=True,
)
def switch_module(*args):
    ctx = dash.ctx
    if not ctx.triggered:
        return no_update, no_update
    mod_id = ctx.triggered[0]["prop_id"].split(".")[0]
    module = mod_id.replace("mod-", "")
    first_page = list(MODULES[module]["pages"].keys())[0]
    return module, first_page


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
        "rango": [start, end],
        "asesor": asesor or "Todos",
        "canal": canal or "Todos",
        "estado": estado or "Todos",
    }


@callback(
    Output("upload-status", "children"),
    Output("store-refresh", "data"),
    Output("store-module", "data", allow_duplicate=True),
    Output("store-tipo", "data"),
    Input("upload-data", "contents"),
    Input("btn-process", "n_clicks"),
    State("upload-data", "filename"),
    State("store-refresh", "data"),
    prevent_initial_call=True,
)
def process_upload(contents, n_clicks, filename, refresh_count):
    if not contents:
        return no_update, no_update, no_update, no_update
    if not filename:
        return html.Div("Selecciona un archivo.", style={"color": AMBER}), no_update, no_update, no_update
    if not filename.endswith((".xlsx", ".xls")):
        return html.Div("Solo archivos Excel.", style={"color": RED}), no_update, no_update, no_update
    try:
        content_type, content_string = contents.split(",")
        decoded = base64.b64decode(content_string)
        CARPETA_ENTRADA.mkdir(parents=True, exist_ok=True)
        ruta = CARPETA_ENTRADA / filename
        with open(ruta, "wb") as f:
            f.write(decoded)

        tipo, sheet = detectar_tipo(str(ruta))
        df_raw = pd.read_excel(str(ruta), sheet_name=sheet)
        df_norm = normalizar(df_raw, tipo)
        df_proc = procesar_etl(df_norm)
        n_reg = subir_a_firestore(df_proc, tipo, filename)

        return html.Div([
            html.Div(f"OK: {filename}", style={"color": "#93c5fd"}),
            html.Div(f"Tipo: {tipo} | {n_reg:,} registros subidos a Firestore",
                     style={"color": GREEN, "fontWeight": "bold"}),
        ]), refresh_count + 1, tipo, tipo
    except Exception as e:
        detalle = traceback.format_exc()
        print(detalle)
        return html.Div([
            html.Div("Error procesando archivo", style={"color": RED, "fontWeight": "bold"}),
            html.Div(str(e), className="small", style={"color": "#f87171"}),
        ]), no_update, no_update, no_update


@callback(
    Output("clear-status", "children"),
    Output("store-clear", "data"),
    Input("clear-data", "n_clicks"),
    State("store-clear", "data"),
    prevent_initial_call=True,
)
def clear_data(n, clear_count):
    try:
        set_metadata("ultima_actualizacion", {"fecha": "-", "tipo": "-", "registros": 0, "archivo": "-"})
    except Exception:
        pass
    return html.Div("Datos limpiados.", style={"color": GREEN}), clear_count + 1


@callback(
    Output("sidebar-info", "children"),
    Input("store-refresh", "data"),
    Input("store-clear", "data"),
    Input("store-filters", "data"),
)
def update_sidebar_info(n, _refresh, _clear, filters):
    try:
        meta = get_metadata()
        ult = meta.get("ultima_actualizacion", {})
        fecha = ult.get("fecha", "N/A")
        tipo = ult.get("tipo", "-")
        regs = ult.get("registros", 0)
        return html.Div([
            html.Div(f"Ultima actualizacion: {fecha}"),
            html.Div(f"Tipo: {tipo} | {regs:,} registros", style={"color": GREEN}),
        ])
    except Exception:
        return html.Div("Firestore no disponible. Conecta las credenciales.", style={"color": AMBER})


@callback(
    Output("dropdown-asesor", "options"),
    Output("dropdown-canal", "options"),
    Output("dropdown-estado", "options"),
    Input("store-refresh", "data"),
    Input("store-clear", "data"),
    Input("store-tipo", "data"),
)
def update_dropdowns(_refresh, _clear, tipo):
    try:
        df = load_from_firestore(tipo)
        if df.empty:
            return [{"label": "Sin datos", "value": "Todos"}], [{"label": "Sin datos", "value": "Todos"}], [{"label": "Sin datos", "value": "Todos"}]
        asesores = [{"label": "Todos", "value": "Todos"}] + [{"label": a, "value": a} for a in sorted(df["_vendedor"].dropna().unique()) if a]
        canales = [{"label": "Todos", "value": "Todos"}] + [{"label": c, "value": c} for c in sorted(df["_canal"].dropna().unique()) if c]
        estados = [{"label": "Todos", "value": "Todos"}] + [{"label": e, "value": e} for e in sorted(df["_estado"].dropna().unique()) if e]
        return asesores, canales, estados
    except Exception:
        return [{"label": "Sin conexion", "value": "Todos"}], [{"label": "Sin conexion", "value": "Todos"}], [{"label": "Sin conexion", "value": "Todos"}]


@callback(
    Output("page-content", "children"),
    Input("store-module", "data"),
    Input("store-page", "data"),
    Input("store-filters", "data"),
    Input("store-refresh", "data"),
    Input("store-clear", "data"),
)
def render_page(module, page, filters, _refresh, _clear):
    try:
        df = load_from_firestore(module)
    except Exception as e:
        return dmc.Alert([
            html.Div("Error al conectar con Firestore.", style={"fontWeight": "bold"}),
            html.Div(f"Verifica el archivo firebase-key.json y la conexion.", className="small mt-1"),
            html.Div(str(e), className="small text-muted mt-1"),
        ], title="Error de Conexion", color="red", withCloseButton=True)

    if df.empty:
        return dmc.Alert([
            html.Div("No hay datos para mostrar.", style={"fontWeight": "bold"}),
            html.Div(f"Sube un archivo Excel de tipo {MODULES[module]['label']} usando el panel lateral.",
                     className="small mt-1"),
        ], title="Sin Datos", color="yellow", withCloseButton=True)

    data = apply_filters(df, filters)
    if data.empty:
        return dmc.Alert(
            "Los filtros actuales no devuelven resultados. Ajusta el periodo, asesor o canal.",
            title="Sin resultados", color="yellow", withCloseButton=True)

    mod_info = MODULES[module]
    nav_items = []
    for pk, plabel in mod_info["pages"].items():
        nav_items.append(dbc.Button(
            plabel, id=f"nav-{module}_{pk}", color="link",
            className="me-1" if page != pk else "me-1 active",
            size="sm",
            style={"fontWeight": "bold", "color": NAVY} if page == pk else {"color": GRAY},
        ))

    nav = html.Div(nav_items, className="mb-3")

    page_funcs = {
        "pedidos": {
            "resumen": pagina_resumen, "participacion": pagina_participacion,
            "pareto": pagina_pareto, "ranking": pagina_ranking,
            "embudo": pagina_embudo, "heatmap": pagina_heatmap,
            "proyeccion": pagina_proyeccion,
        },
        "facturas": {
            "resumen_ventas": pagina_resumen_ventas, "margenes": pagina_margenes,
            "mix_producto": pagina_mix_producto, "precio_promedio": pagina_precio_promedio,
        },
        "inventario": {
            "resumen_stock": pagina_resumen_stock, "por_bodega": pagina_por_bodega,
            "criticos": pagina_criticos,
        },
    }

    func = page_funcs.get(module, {}).get(page)
    if not func:
        return html.Div("Pagina no encontrada.")

    try:
        result = func(data)
    except Exception as e:
        print(traceback.format_exc())
        result = dmc.Alert(f"Error: {e}", title="Error", color="red", withCloseButton=True)

    return html.Div([nav, html.Hr(className="mt-0 mb-3"), result])


@callback(
    Output("store-page", "data", allow_duplicate=True),
    [Input(f"nav-{pk}", "n_clicks") for pk in PAGE_ROUTES],
    prevent_initial_call=True,
)
def navigate(*args):
    ctx = dash.ctx
    if not ctx.triggered:
        return no_update
    route = ctx.triggered[0]["prop_id"].split(".")[0].replace("nav-", "")
    _, page = PAGE_ROUTES.get(route, ("pedidos", "resumen"))
    return page


ANALYSIS_BTN_IDS = []
for pk in PAGE_ROUTES:
    ANALYSIS_BTN_IDS.append(f"btn-analisis-{pk}")

ANALYSIS_OUTPUTS = []
for pk in PAGE_ROUTES:
    ANALYSIS_OUTPUTS.append(f"analisis-{pk}")


@callback(
    [Output(oid, "children") for oid in ANALYSIS_OUTPUTS],
    [Input(bid, "n_clicks") for bid in ANALYSIS_BTN_IDS],
    State("store-filters", "data"),
    State("store-module", "data"),
    State("store-api-key", "data"),
    prevent_initial_call=True,
)
def generate_analysis(*args):
    filters = args[len(ANALYSIS_BTN_IDS)]
    module = args[len(ANALYSIS_BTN_IDS) + 1]
    api_key = args[len(ANALYSIS_BTN_IDS) + 2]
    ctx = dash.ctx
    if not ctx.triggered:
        return [no_update] * len(ANALYSIS_OUTPUTS)
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    route = triggered_id.replace("btn-analisis-", "")
    _, page = PAGE_ROUTES.get(route, ("pedidos", "resumen"))

    try:
        df = load_from_firestore(module)
    except Exception:
        return [no_update] * len(ANALYSIS_OUTPUTS)

    data = apply_filters(df, filters)
    if api_key:
        result = generar_con_gemini(module, page, data, api_key)
        result = result if result else generar_analisis(module, page, data)
    else:
        result = generar_analisis(module, page, data)

    outputs = [no_update] * len(ANALYSIS_OUTPUTS)
    idx = list(PAGE_ROUTES.keys()).index(route)
    outputs[idx] = result
    return outputs


@callback(
    Output("api-status", "children"),
    Output("store-api-key", "data"),
    Input("btn-verify-api", "n_clicks"),
    State("api-key-input", "value"),
    prevent_initial_call=True,
)
def verify_api(n, key):
    if not key:
        return html.Div("Ingresa una API Key.", style={"color": AMBER}), no_update
    try:
        import requests
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
        resp = requests.post(url, json={"contents": [{"parts": [{"text": "di hola"}]}]}, timeout=10)
        if resp.ok:
            return html.Div("API Gemini verificada", style={"color": GREEN}), key
        return html.Div(f"Error: {resp.status_code}", style={"color": RED}), no_update
    except Exception as e:
        return html.Div(f"Error: {e}", style={"color": RED}), no_update


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8503))
    app.run(debug=False, host="0.0.0.0", port=port, threaded=True)
