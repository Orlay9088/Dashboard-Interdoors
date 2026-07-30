from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import plotly.graph_objects as go
import plotly.express as px
from pages.components import section_title, kpi_card, fmt_p, fmt_pm, fig_layout, NAVY, BLUE, GREEN, AMBER, RED, DARKGRAY


def pagina_resumen_stock(data):
    valor_total = data["_valor"].sum()
    productos = data["_referencia"].nunique()
    bodegas = data["_bodega"].nunique() if "_bodega" in data.columns else 0
    existencia = data["_cantidad"].sum() if "_cantidad" in data.columns else 0
    comprometido = data["_cantidad_pen"].sum() if "_cantidad_pen" in data.columns else 0
    disponible = data["_cantidad_com"].sum() if "_cantidad_com" in data.columns else 0
    pct_comp = (comprometido / existencia * 100) if existencia else 0

    children = [section_title("Resumen de Inventario", "Stock y valorizacion")]

    kpi_row = dbc.Row([
        dbc.Col(kpi_card("Valor Total", fmt_p(valor_total), fmt_pm(valor_total)), width=3),
        dbc.Col(kpi_card("Productos", f"{productos:,}", f"{bodegas} bodegas"), width=3),
        dbc.Col(kpi_card("Existencia", f"{existencia:,.0f} und", f"Disponible: {disponible:,.0f}"), width=3),
        dbc.Col(kpi_card("Comprometido", f"{comprometido:,.0f} und", f"{pct_comp:.1f}% del stock"), width=3),
    ], className="mb-4 g-3")
    children.append(kpi_row)

    # Tabla resumen de bodegas seleccionadas (solo 3 columnas)
    bodegas_summary = data.groupby("_bodega").agg(
        CantComprometida=("_cantidad_pen", "sum"),
        Existencia=("_cantidad", "sum"),
        CantDisponible=("_cantidad_com", "sum"),
    ).reset_index().sort_values("Existencia", ascending=False)
    summary_data = []
    for _, r in bodegas_summary.iterrows():
        summary_data.append({
            "Bodega": str(r["_bodega"]),
            "Cant. Comprometida": f"{int(r['CantComprometida']):,}",
            "Existencia": f"{int(r['Existencia']):,}",
            "Cant. Disponible": f"{int(r['CantDisponible']):,}",
        })
    summary_data.append({
        "Bodega": "TOTAL",
        "Cant. Comprometida": f"{int(bodegas_summary['CantComprometida'].sum()):,}",
        "Existencia": f"{int(bodegas_summary['Existencia'].sum()):,}",
        "Cant. Disponible": f"{int(bodegas_summary['CantDisponible'].sum()):,}",
    })
    summary_table = dash_table.DataTable(
        columns=[{"name": c, "id": c} for c in ["Bodega", "Cant. Comprometida", "Existencia", "Cant. Disponible"]],
        data=summary_data,
        style_table={"overflowX": "auto", "marginBottom": "16px"},
        style_cell={"textAlign": "left", "padding": "6px 10px", "fontSize": "0.8rem"},
        style_header={"fontWeight": "bold", "backgroundColor": "#323955", "color": "white", "padding": "8px 10px"},
        style_data_conditional=[
            {"if": {"filter_query": "{Bodega} = 'TOTAL'"},
             "backgroundColor": "#F3C615", "color": DARKGRAY, "fontWeight": "bold"},
        ],
        page_size=20,
    )
    children.append(html.Div([
        html.H6("   Resumen por Bodega", className="fw-bold mb-2", style={"color": NAVY, "fontSize": "0.9rem"}),
        summary_table,
    ]))

    # Graficos
    bodegas_data = data.groupby("_bodega").agg(
        Valor=("_valor", "sum"), Existencia=("_cantidad", "sum"),
        Comprometido=("_cantidad_pen", "sum"), Disponible=("_cantidad_com", "sum"),
    ).reset_index().sort_values("Valor", ascending=False)

    fig_bodega = go.Figure()
    fig_bodega.add_trace(go.Bar(x=bodegas_data["_bodega"].head(10), y=bodegas_data["Valor"] / 1e6,
        name="Valor Total", marker_color=BLUE))
    fig_bodega.update_layout(**fig_layout("Valorizacion por Bodega (millones $)", height=380))
    fig_bodega.update_xaxes(tickangle=-45)

    top_productos = data.groupby(["_referencia", "_linea"]).agg(
        Valor=("_valor", "sum"), Existencia=("_cantidad", "sum"),
    ).reset_index().sort_values("Valor", ascending=False).head(10)

    fig_prod = go.Figure()
    labels = [f"{r['_referencia'][:20]}" for _, r in top_productos.iterrows()]
    fig_prod.add_trace(go.Bar(x=labels, y=top_productos["Valor"] / 1e6,
        marker_color=GREEN, text=[fmt_pm(v) for v in top_productos["Valor"]], textposition="outside"))
    fig_prod.update_layout(**fig_layout("Top 10 Productos por Valor (millones $)", height=380))
    fig_prod.update_xaxes(tickangle=-45)

    children.append(dbc.Row([
        dbc.Col(dcc.Graph(figure=fig_bodega), width=6),
        dbc.Col(dcc.Graph(figure=fig_prod), width=6),
    ], className="mb-3 g-3"))

    table = dash_table.DataTable(
        columns=[{"name": "Bodega", "id": "_bodega"}, {"name": "Valor", "id": "Valor"},
                 {"name": "Existencia", "id": "Existencia"}, {"name": "Comprometido", "id": "Comprometido"},
                 {"name": "Disponible", "id": "Disponible"}],
        data=[{"_bodega": r["_bodega"], "Valor": fmt_p(r["Valor"]),
               "Existencia": f"{int(r['Existencia']):,}", "Comprometido": f"{int(r['Comprometido']):,}",
               "Disponible": f"{int(r['Disponible']):,}"} for _, r in bodegas_data.iterrows()],
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.8rem"},
        style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
        page_size=15,
    )
    children.append(table)
    children.append(html.Hr())
    return children


def pagina_por_bodega(data):
    children = [section_title("Inventario por Bodega", "Detalle de stock por ubicacion")]

    bodegas = sorted(data["_bodega"].dropna().unique()) if "_bodega" in data.columns else []
    if not bodegas:
        children.append(html.P("Sin datos de bodega disponibles.", className="text-muted"))
        return children

    panorama = data.groupby("_bodega").agg(
        Productos=("_referencia", "nunique"), Valor=("_valor", "sum"),
        Existencia=("_cantidad", "sum"), Disponible=("_cantidad_com", "sum"),
        Comprometido=("_cantidad_pen", "sum"),
    ).reset_index().sort_values("Valor", ascending=False)

    fig = px.sunburst(panorama, path=["_bodega"], values="Valor",
        color="Valor", color_continuous_scale="Blues",
        title="Distribucion de Valor por Bodega")
    fig.update_layout(**fig_layout("", height=420))

    table = dash_table.DataTable(
        columns=[{"name": "Bodega", "id": "_bodega"}, {"name": "Productos", "id": "Productos"},
                 {"name": "Valor", "id": "Valor"}, {"name": "Existencia", "id": "Existencia"},
                 {"name": "Disponible", "id": "Disponible"}, {"name": "Comprometido", "id": "Comprometido"}],
        data=[{"_bodega": r["_bodega"], "Productos": f"{int(r['Productos']):,}",
               "Valor": fmt_p(r["Valor"]), "Existencia": f"{int(r['Existencia']):,}",
               "Disponible": f"{int(r['Disponible']):,}", "Comprometido": f"{int(r['Comprometido']):,}"}
              for _, r in panorama.iterrows()],
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.8rem"},
        style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
        page_size=20,
    )

    children.append(dbc.Row([
        dbc.Col(dcc.Graph(figure=fig), width=6),
        dbc.Col(html.Div([
            html.H6("Resumen por Bodega", className="fw-bold", style={"color": NAVY}),
            table,
        ]), width=6),
    ], className="mb-3 g-3"))

    children.append(html.Hr())
    return children


def pagina_criticos(data):
    children = [section_title("Productos Criticos", "Bajo stock, alto compromiso, sin movimiento")]

    criticos = []
    if "_cantidad_com" in data.columns and "_cantidad" in data.columns:
        data["_ratio_comp"] = data["_cantidad_com"] / data["_cantidad"].replace(0, 1) * 100
        criticos_comp = data[data["_ratio_comp"] > 80].groupby(["_referencia", "_linea", "_bodega"]).agg(
            Existencia=("_cantidad", "sum"), Disponible=("_cantidad_com", "sum"),
            Comprometido=("_cantidad_pen", "sum"), Valor=("_valor", "sum"),
        ).reset_index().sort_values("Valor", ascending=False).head(20)
        criticos.append(html.H6("Alto Compromiso (>80%)", className="fw-bold", style={"color": RED}))
        criticos.append(dash_table.DataTable(
            columns=[{"name": c, "id": c} for c in ["_referencia", "_linea", "_bodega", "Existencia", "Disponible", "Comprometido", "Valor"]],
            data=[{"_referencia": r["_referencia"][:30], "_linea": r["_linea"],
                   "_bodega": r["_bodega"], "Existencia": f"{int(r['Existencia']):,}",
                   "Disponible": f"{int(r['Disponible']):,}", "Comprometido": f"{int(r['Comprometido']):,}",
                   "Valor": fmt_p(r["Valor"])} for _, r in criticos_comp.iterrows()],
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.75rem"},
            style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
            page_size=10,
        ))

    if "_cantidad" in data.columns:
        bajo_stock = data[data["_cantidad"] <= 3].groupby(["_referencia", "_linea", "_bodega"]).agg(
            Existencia=("_cantidad", "sum"), Valor=("_valor", "sum"),
            Comprometido=("_cantidad_pen", "sum"),
        ).reset_index().sort_values("Valor", ascending=False).head(20)
        criticos.append(html.H6("Bajo Stock (3 o menos)", className="fw-bold mt-4", style={"color": AMBER}))
        criticos.append(dash_table.DataTable(
            columns=[{"name": c, "id": c} for c in ["_referencia", "_linea", "_bodega", "Existencia", "Comprometido", "Valor"]],
            data=[{"_referencia": r["_referencia"][:30], "_linea": r["_linea"],
                   "_bodega": r["_bodega"], "Existencia": f"{int(r['Existencia']):,}",
                   "Comprometido": f"{int(r['Comprometido']):,}",
                   "Valor": fmt_p(r["Valor"])} for _, r in bajo_stock.iterrows()],
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.75rem"},
            style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
            page_size=10,
        ))

    if not criticos:
        criticos.append(html.P("Datos insuficientes para analisis de criticos.", className="text-muted"))

    children.extend(criticos)
    return children
