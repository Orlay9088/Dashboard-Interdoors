from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import plotly.graph_objects as go
import plotly.express as px
from pages.components import section_title, kpi_card, fmt_p, fmt_pm, fig_layout, NAVY, BLUE, GREEN, AMBER, RED


def pagina_resumen_ventas(data):
    ventas = data["_valor"].sum()
    margen_prom = data["_margen"].mean() if "_margen" in data.columns else 0
    total_facturas = data["_documento"].nunique()
    total_clientes = data["_cliente"].nunique()
    num_vendedores = data["_vendedor"].nunique()
    costo_total = data["_costo"].sum() if "_costo" in data.columns else 0
    ticket_prom = ventas / total_facturas if total_facturas else 0
    mgn_pct = (ventas - costo_total) / ventas * 100 if ventas else 0

    children = [section_title("Resumen de Ventas", "Facturacion - Indicadores principales")]

    kpi_row = dbc.Row([
        dbc.Col(kpi_card("Ventas Totales", fmt_p(ventas), fmt_pm(ventas)), width=3),
        dbc.Col(kpi_card("Facturas", f"{total_facturas:,}", f"{total_clientes} clientes"), width=3),
        dbc.Col(kpi_card("Ticket Promedio", fmt_p(ticket_prom)), width=3),
        dbc.Col(kpi_card("Margen Global", f"{mgn_pct:.1f}%", f"Costo: {fmt_pm(costo_total)}"), width=3),
    ], className="mb-4 g-3")
    children.append(kpi_row)

    has_costo = "_costo" in data.columns
    agg_dict = {"Ventas": ("_valor", "sum"), "Facturas": ("_documento", "nunique")}
    if has_costo:
        agg_dict["Costo"] = ("_costo", "sum")
    evol = data.groupby(data["_fecha"].dt.to_period("M")).agg(**agg_dict).reset_index()
    if not has_costo:
        evol["Costo"] = 0
    evol["_fecha_str"] = evol["_fecha"].astype(str)

    fig_evol = go.Figure()
    fig_evol.add_trace(go.Scatter(x=evol["_fecha_str"], y=evol["Ventas"] / 1e6,
        mode="lines+markers", name="Ventas", line=dict(width=3, color=BLUE), marker=dict(size=6)))
    if has_costo:
        fig_evol.add_trace(go.Scatter(x=evol["_fecha_str"], y=evol["Costo"] / 1e6,
            mode="lines+markers", name="Costo", line=dict(width=3, color=RED), marker=dict(size=6)))
    fig_evol.update_layout(**fig_layout("Evolucion Mensual (millones $)", height=380))
    fig_evol.update_layout(legend=dict(orientation="h", y=1.1))

    top_agg = {"Ventas": ("_valor", "sum")}
    if "_margen" in data.columns:
        top_agg["Margen"] = ("_margen", "mean")
    top_vendedores = data.groupby("_vendedor").agg(**top_agg).reset_index().sort_values("Ventas", ascending=True).tail(10)
    if "_margen" not in data.columns:
        top_vendedores["Margen"] = 0

    fig_vend = go.Figure()
    fig_vend.add_trace(go.Bar(x=top_vendedores["Ventas"] / 1e6, y=top_vendedores["_vendedor"],
        orientation="h", marker_color=BLUE,
        text=[fmt_pm(v) for v in top_vendedores["Ventas"]], textposition="outside"))
    fig_vend.update_layout(**fig_layout("Top 10 Vendedores (millones $)", height=380))
    fig_vend.update_xaxes(title="$ millones")
    fig_vend.update_yaxes(automargin=True, tickfont=dict(size=10))

    children.append(dbc.Row([
        dbc.Col(dcc.Graph(figure=fig_evol), width=6),
        dbc.Col(dcc.Graph(figure=fig_vend), width=6),
    ], className="mb-3 g-3"))

    children.append(html.Hr())
    return children


def pagina_margenes(data):
    children = [section_title("Margenes", "Analisis de rentabilidad por canal, vendedor y grupo")]

    if "_margen" not in data.columns or "_costo" not in data.columns:
        children.append(html.P("Datos de margen no disponibles en este archivo.", className="text-muted"))
        return children

    mgn_canal = data.groupby("_canal").agg(
        Ventas=("_valor", "sum"), Costo=("_costo", "sum"), Margen=("_margen", "mean"),
    ).reset_index()
    mgn_canal["Margen %"] = ((mgn_canal["Ventas"] - mgn_canal["Costo"]) / mgn_canal["Ventas"] * 100).round(1)

    fig_canal = go.Figure()
    fig_canal.add_trace(go.Bar(x=mgn_canal["_canal"], y=mgn_canal["Ventas"] / 1e6, name="Ventas", marker_color=BLUE))
    fig_canal.add_trace(go.Bar(x=mgn_canal["_canal"], y=mgn_canal["Costo"] / 1e6, name="Costo", marker_color=RED))
    fig_canal.update_layout(**fig_layout("Ventas vs Costo por Canal (millones $)", height=380, barmode="group"))
    fig_canal.update_xaxes(tickangle=-45)

    mgn_vend = data.groupby("_vendedor").agg(
        Ventas=("_valor", "sum"), Costo=("_costo", "sum"),
    ).reset_index().sort_values("Ventas", ascending=False).head(10)
    mgn_vend["Margen %"] = ((mgn_vend["Ventas"] - mgn_vend["Costo"]) / mgn_vend["Ventas"] * 100).round(1)

    fig_vend = go.Figure()
    fig_vend.add_trace(go.Bar(y=mgn_vend["_vendedor"], x=mgn_vend["Ventas"] / 1e6,
        orientation="h", marker_color=GREEN,
        text=[f"{r['Margen %']:.1f}%" for _, r in mgn_vend.iterrows()], textposition="outside"))
    fig_vend.update_layout(**fig_layout("Margen por Vendedor (millones $)", height=380))
    fig_vend.update_xaxes(title="$ millones")
    fig_vend.update_yaxes(automargin=True, tickfont=dict(size=10))

    children.append(dbc.Row([
        dbc.Col(dcc.Graph(figure=fig_canal), width=6),
        dbc.Col(dcc.Graph(figure=fig_vend), width=6),
    ], className="mb-3 g-3"))

    table = dash_table.DataTable(
        columns=[{"name": c, "id": c} for c in ["_canal", "Ventas", "Costo", "Margen %"]],
        data=[{"_canal": r["_canal"], "Ventas": fmt_p(r["Ventas"]),
               "Costo": fmt_p(r["Costo"]), "Margen %": f"{r['Margen %']:.1f}%"}
              for _, r in mgn_canal.iterrows()],
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.8rem"},
        style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
        page_size=10,
    )
    children.append(table)
    children.append(html.Hr())
    return children


def pagina_mix_producto(data):
    children = [section_title("Mix de Producto", "Participacion de grupos y lineas en ventas")]

    group_col = "_grupo" if "_grupo" in data.columns and not data["_grupo"].eq("").all() else "_linea"
    titulo = "Grupos" if group_col == "_grupo" else "Lineas"

    mix_agg = {"Ventas": ("_valor", "sum")}
    if "_margen" in data.columns:
        mix_agg["Margen"] = ("_margen", "mean")
    mix = data.groupby(group_col).agg(**mix_agg).reset_index().sort_values("Ventas", ascending=False)
    tv = mix["Ventas"].sum()
    mix["%"] = (mix["Ventas"] / tv * 100).round(1)

    fig_treemap = px.treemap(mix.head(20), path=[group_col], values="Ventas",
        color="%", color_continuous_scale="Blues",
        title=f"Participacion por {titulo}")
    fig_treemap.update_layout(**fig_layout(f"Mix por {titulo}", height=420))

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(x=mix[group_col].head(10), y=mix["Ventas"].head(10) / 1e6,
        marker_color=BLUE, text=[f"{r:.1f}%" for r in mix["%"].head(10)], textposition="outside"))
    fig_bar.update_layout(**fig_layout(f"Top 10 {titulo} (millones $)", height=380))
    fig_bar.update_xaxes(tickangle=-45)

    children.append(dbc.Row([
        dbc.Col(dcc.Graph(figure=fig_treemap), width=6),
        dbc.Col(dcc.Graph(figure=fig_bar), width=6),
    ], className="mb-3 g-3"))

    table = dash_table.DataTable(
        columns=[{"name": group_col, "id": group_col}, {"name": "Ventas", "id": "Ventas"}, {"name": "%", "id": "%"}],
        data=[{group_col: r[group_col], "Ventas": fmt_p(r["Ventas"]), "%": f"{r['%']:.1f}%"}
              for _, r in mix.iterrows()],
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.8rem"},
        style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
        page_size=15,
    )
    children.append(table)
    children.append(html.Hr())
    return children


def pagina_precio_promedio(data):
    children = [section_title("Precio Promedio", "Evolucion de precios por linea")]

    if "_linea" not in data.columns or "_cantidad" not in data.columns:
        children.append(html.P("Datos insuficientes para precio promedio.", className="text-muted"))
        return children

    precios = data.groupby(["_linea", data["_fecha"].dt.to_period("M")]).agg(
        Valor=("_valor", "sum"), Cantidad=("_cantidad", "sum"),
    ).reset_index()
    precios["Precio Prom"] = precios["Valor"] / precios["Cantidad"].replace(0, 1)

    top_lineas = precios.groupby("_linea")["Valor"].sum().sort_values(ascending=False).head(6).index.tolist()

    fig = go.Figure()
    for linea in top_lineas:
        d = precios[precios["_linea"] == linea].sort_values("_fecha")
        fig.add_trace(go.Scatter(x=d["_fecha"].astype(str), y=d["Precio Prom"],
            mode="lines+markers", name=linea, line=dict(width=2)))
    fig.update_layout(**fig_layout("Precio Promedio por Linea", height=400))
    fig.update_layout(legend=dict(orientation="h", y=1.1))
    fig.update_xaxes(tickangle=-45)

    resumen = precios.groupby("_linea").agg(
        Valor=("Valor", "sum"), Cantidad=("Cantidad", "sum"),
    ).reset_index()
    resumen["Precio Prom"] = resumen["Valor"] / resumen["Cantidad"].replace(0, 1)

    children.append(dbc.Row([dbc.Col(dcc.Graph(figure=fig), width=12)], className="mb-3"))
    children.append(dash_table.DataTable(
        columns=[{"name": "Linea", "id": "_linea"}, {"name": "Valor", "id": "Valor"},
                 {"name": "Cantidad", "id": "Cantidad"}, {"name": "Precio Prom", "id": "Precio Prom"}],
        data=[{"_linea": r["_linea"], "Valor": fmt_p(r["Valor"]),
               "Cantidad": f"{int(r['Cantidad']):,}",
               "Precio Prom": fmt_p(r["Precio Prom"])} for _, r in resumen.iterrows()],
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.8rem"},
        style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
        page_size=20,
    ))
    return children
