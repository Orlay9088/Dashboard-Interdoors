from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pages.components import section_title, kpi_card, fmt_p, fmt_pm, safe_int, fig_layout, NAVY, BLUE, GREEN, AMBER, RED, GRAY, DARKGRAY, GOLD, graph_png


def pagina_resumen_ventas(data):
    ventas = data["_valor"].sum()
    total_facturas = data["_documento"].nunique()
    total_clientes = data["_cliente"].nunique()
    num_vendedores = data["_vendedor"].nunique()
    costo_total = data["_costo"].sum() if "_costo" in data.columns else 0
    ticket_prom = ventas / total_facturas if total_facturas else 0
    mgn_pct = (ventas - costo_total) / ventas * 100 if ventas else 0
    has_costo = "_costo" in data.columns
    has_margen = "_margen" in data.columns

    title_sub = f"{total_facturas:,} facturas | {total_clientes} clientes | {num_vendedores} vendedores"
    children = [section_title("Resumen de Ventas", title_sub)]

    kpi_row = dbc.Row([
        dbc.Col(kpi_card("Ventas Totales", fmt_p(ventas), fmt_pm(ventas), color=BLUE), width=12, sm=6, lg=3),
        dbc.Col(kpi_card("Ticket Promedio", fmt_p(ticket_prom), f"por factura", color=NAVY), width=12, sm=6, lg=3),
        dbc.Col(kpi_card("Margen Global", f"{mgn_pct:.1f}%", f"Costo: {fmt_pm(costo_total)}", color=GREEN if mgn_pct > 30 else AMBER), width=12, sm=6, lg=3),
        dbc.Col(kpi_card("Facturas", f"{total_facturas:,}", f"{total_clientes} clientes activos", color=GRAY), width=12, sm=6, lg=3),
    ], className="mb-4 g-3")
    children.append(kpi_row)

    agg_dict = {"Ventas": ("_valor", "sum"), "Facturas": ("_documento", "nunique")}
    if has_costo:
        agg_dict["Costo"] = ("_costo", "sum")
    evol = data.groupby(data["_fecha"].dt.to_period("M")).agg(**agg_dict).reset_index()
    if not has_costo:
        evol["Costo"] = 0
    evol["_fecha_str"] = evol["_fecha"].astype(str)
    if has_costo:
        evol["Margen %"] = ((evol["Ventas"] - evol["Costo"]) / evol["Ventas"].replace(0, 1) * 100).round(1)

    fig_evol = go.Figure()
    fig_evol.add_trace(go.Scatter(x=evol["_fecha_str"], y=evol["Ventas"] / 1e6,
        mode="lines+markers", name="Ventas", line=dict(width=3, color=BLUE), marker=dict(size=7),
        hovertemplate="<b>%{x}</b><br>Ventas: $%{y:.1f}M<extra></extra>"))
    if has_costo:
        fig_evol.add_trace(go.Scatter(x=evol["_fecha_str"], y=evol["Costo"] / 1e6,
            mode="lines+markers", name="Costo", line=dict(width=3, color=RED), marker=dict(size=7),
            hovertemplate="<b>%{x}</b><br>Costo: $%{y:.1f}M<extra></extra>"))
    fig_evol.update_layout(**fig_layout("Evolucion Mensual de Ventas (millones $)", height=380,
        legend=dict(orientation="h", y=1.1)))

    top_agg = {"Ventas": ("_valor", "sum")}
    if has_margen:
        top_agg["Margen"] = ("_margen", "mean")
    top_vendedores = data.groupby("_vendedor").agg(**top_agg).reset_index().sort_values("Ventas", ascending=True).tail(12)
    if not has_margen:
        top_vendedores["Margen"] = 0
    top_n = len(top_vendedores)

    fig_vend = go.Figure()
    fig_vend.add_trace(go.Bar(x=top_vendedores["Ventas"] / 1e6, y=top_vendedores["_vendedor"],
        orientation="h", marker_color=[GOLD if i == top_n - 1 else BLUE for i in range(top_n)],
        text=[fmt_pm(v) for v in top_vendedores["Ventas"]], textposition="outside",
        textfont=dict(size=10, color=GRAY),
        hovertemplate="<b>%{y}</b><br>Ventas: %{text}<extra></extra>"))
    fig_vend.update_layout(**fig_layout("Top 12 Vendedores (millones $)", height=380))
    fig_vend.update_xaxes(title="$ millones")
    fig_vend.update_yaxes(automargin=True, tickfont=dict(size=10), autorange="reversed")

    children.append(dbc.Row([
        dbc.Col(graph_png(figure=fig_evol), width=12, lg=6),
        dbc.Col(graph_png(figure=fig_vend), width=12, lg=6),
    ], className="mb-3 g-3"))

    evol_table = dash_table.DataTable(
        columns=[{"name": "Mes", "id": "Mes"}, {"name": "Ventas", "id": "Ventas"},
                 {"name": "Costo", "id": "Costo"}, {"name": "Margen %", "id": "Margen %"},
                 {"name": "Facturas", "id": "Facturas"}],
        data=[{"Mes": r["_fecha_str"], "Ventas": fmt_pm(r["Ventas"]),
               "Costo": fmt_pm(r["Costo"]), "Margen %": f"{r['Margen %']:.1f}%" if has_costo else "-",
               "Facturas": f"{int(r['Facturas']):,}"} for _, r in evol.tail(12).iterrows()],
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "6px 10px", "fontSize": "0.78rem", "fontFamily": "Segoe UI, Arial, sans-serif"},
        style_header={"fontWeight": "bold", "backgroundColor": DARKGRAY, "color": "white", "border": "none"},
        page_size=12,
    )
    children.append(html.Div([
        html.H6("● Evolucion Mensual", className="fw-bold mb-2", style={"color": NAVY, "fontSize": "0.85rem"}),
        evol_table,
        html.Hr(),
    ]))
    return children


def pagina_margenes(data):
    if "_margen" not in data.columns or "_costo" not in data.columns:
        return [section_title("Margenes", "Sin datos"),
                html.P("Datos de margen y costo no disponibles en este archivo.", className="text-muted")]

    ventas = data["_valor"].sum()
    costo = data["_costo"].sum()
    mgn_global = (ventas - costo) / ventas * 100 if ventas else 0
    mgn_prom_val = data["_margen"].mean()
    mgn_prom = f"{mgn_prom_val:.1f}%" if not pd.isna(mgn_prom_val) else "-"
    n_vend = data["_vendedor"].nunique()
    n_canales = data["_canal"].nunique() if "_canal" in data.columns else 0

    children = [section_title("Margenes", f"Margen global: {mgn_global:.1f}% | {n_vend} vendedores | {n_canales} canales")]

    kpi_row = dbc.Row([
        dbc.Col(kpi_card("Margen Global", f"{mgn_global:.1f}%", f"Margen prom: {mgn_prom}", color=GREEN if mgn_global > 25 else AMBER), width=12, sm=6, lg=3),
        dbc.Col(kpi_card("Ventas Totales", fmt_p(ventas), fmt_pm(ventas), color=BLUE), width=12, sm=6, lg=3),
        dbc.Col(kpi_card("Costo Total", fmt_p(costo), f"{costo/ventas*100:.1f}% de ventas" if ventas else "", color=RED), width=12, sm=6, lg=3),
        dbc.Col(kpi_card("Utilidad Bruta", fmt_p(ventas - costo), fmt_pm(ventas - costo), color=GREEN), width=12, sm=6, lg=3),
    ], className="mb-4 g-3")
    children.append(kpi_row)

    mgn_canal = data.groupby("_canal").agg(
        Ventas=("_valor", "sum"), Costo=("_costo", "sum"), Margen=("_margen", "mean"),
    ).reset_index()
    mgn_canal["Margen %"] = ((mgn_canal["Ventas"] - mgn_canal["Costo"]) / mgn_canal["Ventas"].replace(0, 1) * 100).round(1)
    mgn_canal = mgn_canal.sort_values("Ventas", ascending=False)

    fig_canal = go.Figure()
    fig_canal.add_trace(go.Bar(x=mgn_canal["_canal"], y=mgn_canal["Ventas"] / 1e6, name="Ventas",
        marker_color=BLUE, hovertemplate="<b>%{x}</b><br>Ventas: $%{y:.1f}M<extra></extra>"))
    fig_canal.add_trace(go.Bar(x=mgn_canal["_canal"], y=mgn_canal["Costo"] / 1e6, name="Costo",
        marker_color=RED, hovertemplate="<b>%{x}</b><br>Costo: $%{y:.1f}M<extra></extra>"))
    fig_canal.update_layout(**fig_layout("Ventas vs Costo por Canal (millones $)", height=380, barmode="group"))
    fig_canal.update_xaxes(tickangle=-45)

    mgn_vend = data.groupby("_vendedor").agg(
        Ventas=("_valor", "sum"), Costo=("_costo", "sum"),
    ).reset_index().sort_values("Ventas", ascending=False).head(12)
    mgn_vend["Margen %"] = ((mgn_vend["Ventas"] - mgn_vend["Costo"]) / mgn_vend["Ventas"].replace(0, 1) * 100).round(1)
    vend_n = len(mgn_vend)

    fig_vend = go.Figure()
    fig_vend.add_trace(go.Bar(y=mgn_vend["_vendedor"], x=mgn_vend["Ventas"] / 1e6,
        orientation="h", marker_color=[GOLD if i == 0 else GREEN for i in range(vend_n)],
        text=[f"{r['Margen %']:.1f}%" for _, r in mgn_vend.iterrows()],
        textposition="outside", textfont=dict(size=10, color=GRAY),
        hovertemplate="<b>%{y}</b><br>Ventas: $%{x:.1f}M<br>Margen: %{text}<extra></extra>"))
    fig_vend.update_layout(**fig_layout("Margen por Vendedor (top 12)", height=380))
    fig_vend.update_xaxes(title="$ millones")
    fig_vend.update_yaxes(automargin=True, tickfont=dict(size=10), autorange="reversed")

    children.append(dbc.Row([
        dbc.Col(graph_png(figure=fig_canal), width=12, lg=6),
        dbc.Col(graph_png(figure=fig_vend), width=12, lg=6),
    ], className="mb-3 g-3"))

    canal_table = dash_table.DataTable(
        columns=[{"name": "Canal", "id": "_canal"}, {"name": "Ventas", "id": "Ventas"},
                 {"name": "Costo", "id": "Costo"}, {"name": "Margen %", "id": "Margen %"}],
        data=[{"_canal": r["_canal"], "Ventas": fmt_p(r["Ventas"]),
               "Costo": fmt_p(r["Costo"]), "Margen %": f"{r['Margen %']:.1f}%"}
              for _, r in mgn_canal.iterrows()],
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "6px 10px", "fontSize": "0.78rem", "fontFamily": "Segoe UI, Arial, sans-serif"},
        style_header={"fontWeight": "bold", "backgroundColor": DARKGRAY, "color": "white", "border": "none"},
        style_data_conditional=[
            {"if": {"filter_query": "{Margen %} > 30", "column_id": "Margen %"},
             "color": GREEN, "fontWeight": "bold"},
            {"if": {"filter_query": "{Margen %} < 15", "column_id": "Margen %"},
             "color": RED, "fontWeight": "bold"},
        ],
        page_size=10,
    )
    children.append(html.Div([
        html.H6("● Detalle por Canal", className="fw-bold mb-2", style={"color": NAVY, "fontSize": "0.85rem"}),
        canal_table,
        html.Hr(),
    ]))
    return children


def pagina_mix_producto(data):
    group_col = "_grupo" if "_grupo" in data.columns and not data["_grupo"].eq("").all() else "_linea"
    titulo = "Grupos" if group_col == "_grupo" else "Lineas"

    mix_agg = {"Ventas": ("_valor", "sum")}
    if "_margen" in data.columns:
        mix_agg["Margen"] = ("_margen", "mean")
    mix = data.groupby(group_col).agg(**mix_agg).reset_index().sort_values("Ventas", ascending=False)
    tv = mix["Ventas"].sum()
    mix["%"] = (mix["Ventas"] / tv * 100).round(1)
    n_groups = len(mix)
    top_group = mix.iloc[0][group_col] if not mix.empty else "N/A"
    top_pct = mix.iloc[0]["%"] if not mix.empty else 0

    children = [section_title("Mix de Producto", f"{n_groups} {titulo.lower()} | Principal: {str(top_group)[:25]} ({top_pct:.1f}%)")]

    kpi_row = dbc.Row([
        dbc.Col(kpi_card("Total Grupos", str(n_groups), "categorias de producto", color=BLUE), width=12, lg=4),
        dbc.Col(kpi_card("Ventas Totales", fmt_p(tv), fmt_pm(tv), color=NAVY), width=12, lg=4),
        dbc.Col(kpi_card("Top 3 Concentran", f"{mix.head(3)['%'].sum():.1f}%", f"#1: {top_group[:20]}", color=AMBER), width=12, lg=4),
    ], className="mb-4 g-3")
    children.append(kpi_row)

    fig_treemap = px.treemap(mix.head(20), path=[group_col], values="Ventas",
        color="%", color_continuous_scale="Blues",
        title=f"Participacion por {titulo}",
        hover_data={group_col: False, "Ventas": True, "%": True})
    fig_treemap.update_traces(
        texttemplate="<b>%{label}</b><br>%{customdata[1]:.1f}%",
        hovertemplate="<b>%{label}</b><br>Ventas: %{customdata[0]}<br>%: %{customdata[1]:.1f}%<extra></extra>",
    )
    fig_treemap.update_layout(**fig_layout(f"Mix por {titulo}", height=400))

    fig_bar = go.Figure()
    top_mix = mix.head(12)
    fig_bar.add_trace(go.Bar(
        y=top_mix[group_col], x=top_mix["Ventas"] / 1e6, orientation="h",
        marker_color=[GOLD if i == 0 else BLUE for i in range(len(top_mix))],
        text=[f"{r['%']:.1f}%" for _, r in top_mix.iterrows()],
        textposition="outside", textfont=dict(size=10, color=GRAY),
        hovertemplate="<b>%{y}</b><br>$%{x:.1f}M<br>%{text}<extra></extra>",
    ))
    fig_bar.update_layout(**fig_layout(f"Top 12 {titulo} (millones $)", height=380))
    fig_bar.update_xaxes(title="$ millones")
    fig_bar.update_yaxes(automargin=True, tickfont=dict(size=10), autorange="reversed")

    children.append(dbc.Row([
        dbc.Col(graph_png(figure=fig_treemap), width=12, lg=6),
        dbc.Col(graph_png(figure=fig_bar), width=12, lg=6),
    ], className="mb-3 g-3"))

    mix_table = dash_table.DataTable(
        columns=[{"name": group_col, "id": group_col}, {"name": "Ventas", "id": "Ventas"},
                 {"name": "%", "id": "%"}, {"name": "% Acum", "id": "% Acum"}],
        data=[{group_col: r[group_col], "Ventas": fmt_p(r["Ventas"]),
               "%": f"{r['%']:.1f}%", "% Acum": f"{mix['%'].cumsum().iloc[i]:.1f}%"}
              for i, (_, r) in enumerate(mix.iterrows())],
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "6px 10px", "fontSize": "0.78rem", "fontFamily": "Segoe UI, Arial, sans-serif"},
        style_header={"fontWeight": "bold", "backgroundColor": DARKGRAY, "color": "white", "border": "none"},
        page_size=15,
    )
    children.append(html.Div([
        html.H6(f"● Ranking de {titulo}", className="fw-bold mb-2", style={"color": NAVY, "fontSize": "0.85rem"}),
        mix_table,
        html.Hr(),
    ]))
    return children


def pagina_precio_promedio(data):
    if "_linea" not in data.columns or "_cantidad" not in data.columns:
        return [section_title("Precio Promedio", "Sin datos"),
                html.P("Datos insuficientes para calcular precio promedio.", className="text-muted")]

    precios = data.groupby(["_linea", data["_fecha"].dt.to_period("M")]).agg(
        Valor=("_valor", "sum"), Cantidad=("_cantidad", "sum"),
    ).reset_index()
    precios["Precio Prom"] = precios["Valor"] / precios["Cantidad"].replace(0, 1)

    resumen = precios.groupby("_linea").agg(
        Valor=("Valor", "sum"), Cantidad=("Cantidad", "sum"),
    ).reset_index()
    resumen["Precio Prom"] = resumen["Valor"] / resumen["Cantidad"].replace(0, 1)
    global_precio = resumen["Valor"].sum() / resumen["Cantidad"].sum() if resumen["Cantidad"].sum() else 0
    n_lineas = len(resumen)
    linea_top = str(resumen.iloc[0]["_linea"])[:22] if not resumen.empty else "-"
    precio_top = fmt_p(resumen.iloc[0]["Precio Prom"]) if not resumen.empty else ""

    children = [section_title("Precio Promedio", f"{n_lineas} lineas | Precio global: {fmt_p(global_precio)}")]

    kpi_row = dbc.Row([
        dbc.Col(kpi_card("Precio Global", fmt_p(global_precio), f"{n_lineas} lineas de producto", color=BLUE), width=12, lg=4),
        dbc.Col(kpi_card("Linea TOP", linea_top, precio_top, color=GOLD), width=12, lg=4),
        dbc.Col(kpi_card("Unidades Totales", f"{safe_int(resumen['Cantidad'].sum()):,}", f"Valor: {fmt_pm(resumen['Valor'].sum())}", color=GRAY), width=12, lg=4),
    ], className="mb-4 g-3")
    children.append(kpi_row)

    top_lineas = precios.groupby("_linea")["Valor"].sum().sort_values(ascending=False).head(6).index.tolist()

    fig = go.Figure()
    colors = [BLUE, RED, GREEN, AMBER, "#8b5cf6", GOLD]
    for idx, linea in enumerate(top_lineas):
        d = precios[precios["_linea"] == linea].sort_values("_fecha")
        fig.add_trace(go.Scatter(x=d["_fecha"].astype(str), y=d["Precio Prom"],
            mode="lines+markers", name=str(linea)[:20],
            line=dict(width=2, color=colors[idx % len(colors)]),
            marker=dict(size=5),
            hovertemplate=f"<b>{str(linea)[:20]}</b><br>Precio: %{{y:$,.0f}}<extra></extra>"))
    fig.update_layout(**fig_layout("Evolucion de Precio Promedio por Linea", height=400,
        legend=dict(orientation="h", y=1.12, font=dict(size=9))))
    fig.update_xaxes(tickangle=-45, tickfont=dict(size=9))
    fig.update_yaxes(title="$ pesos", automargin=True)

    children.append(dbc.Row([dbc.Col(graph_png(figure=fig), width=12)], className="mb-3 g-3"))

    precio_table = dash_table.DataTable(
        columns=[{"name": "Linea", "id": "_linea"}, {"name": "Valor", "id": "Valor"},
                 {"name": "Unidades", "id": "Cantidad"}, {"name": "Precio Prom", "id": "Precio Prom"}],
        data=[{"_linea": r["_linea"], "Valor": fmt_p(r["Valor"]),
               "Cantidad": f"{int(r['Cantidad']):,}",
               "Precio Prom": fmt_p(r["Precio Prom"])} for _, r in resumen.sort_values("Precio Prom", ascending=False).iterrows()],
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "6px 10px", "fontSize": "0.78rem", "fontFamily": "Segoe UI, Arial, sans-serif"},
        style_header={"fontWeight": "bold", "backgroundColor": DARKGRAY, "color": "white", "border": "none"},
        page_size=20,
    )
    children.append(html.Div([
        html.H6("● Resumen por Linea", className="fw-bold mb-2", style={"color": NAVY, "fontSize": "0.85rem"}),
        precio_table,
        html.Hr(),
    ]))
    return children
