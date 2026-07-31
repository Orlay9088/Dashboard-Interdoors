from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import plotly.graph_objects as go
import plotly.express as px
from pages.components import section_title, kpi_card, fmt_p, fmt_pm, fig_layout, NAVY, BLUE, GREEN, AMBER, RED, GRAY, DARKGRAY, GOLD


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

    n_bodegas = len(bodegas_data)
    bodegas_data["_label"] = bodegas_data["_bodega"].apply(lambda x: f"Bod. {str(x)[:12]}")
    subtitle = f"{n_bodegas} bodega{'s' if n_bodegas != 1 else ''}"

    bar_width = max(0.4, min(0.8, 6.0 / max(n_bodegas, 1)))
    tick_angle = 0 if n_bodegas <= 6 else -45

    fig_bodega = go.Figure()
    fig_bodega.add_trace(go.Bar(
        x=bodegas_data["_label"],
        y=bodegas_data["Valor"] / 1e6,
        name="Valor Total",
        marker_color=BLUE,
        width=bar_width,
        text=[fmt_pm(v) for v in bodegas_data["Valor"]],
        textposition="outside",
        textfont=dict(size=10, color=BLUE),
        hovertemplate="<b>%{x}</b><br>Valor: %{text}<extra></extra>",
    ))
    fig_bodega.update_layout(**fig_layout(f"<b>Valorizacion por Bodega</b> — {subtitle}", height=400))
    fig_bodega.update_xaxes(tickangle=tick_angle, automargin=True, tickfont=dict(size=10))
    fig_bodega.update_yaxes(title="$ millones", automargin=True)

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
        style_header={"fontWeight": "bold", "backgroundColor": DARKGRAY, "color": "white", "border": "none"},
        page_size=15,
    )
    children.append(table)
    children.append(html.Hr())
    return children


def pagina_por_bodega(data):
    bodegas = sorted(data["_bodega"].dropna().unique()) if "_bodega" in data.columns else []
    if not bodegas:
        return [section_title("Inventario por Bodega", "Sin datos"),
                html.P("Sin datos de bodega disponibles.", className="text-muted")]

    panorama = data.groupby("_bodega").agg(
        Productos=("_referencia", "nunique"), Valor=("_valor", "sum"),
        Existencia=("_cantidad", "sum"), Disponible=("_cantidad_com", "sum"),
        Comprometido=("_cantidad_pen", "sum"),
    ).reset_index().sort_values("Valor", ascending=False)

    n_bodegas = len(panorama)
    valor_total = panorama["Valor"].sum()
    bodega_top = panorama.iloc[0]["_bodega"] if not panorama.empty else "N/A"
    bodega_top_pct = (panorama.iloc[0]["Valor"] / valor_total * 100) if valor_total else 0

    children = [section_title("Inventario por Bodega", f"{n_bodegas} bodegas | Principal: Bod.{bodega_top} ({bodega_top_pct:.1f}%)")]

    kpi_row = dbc.Row([
        dbc.Col(kpi_card("Total Bodegas", str(n_bodegas), f"Todas activas", color=BLUE), width=3),
        dbc.Col(kpi_card("Valor Total", fmt_p(valor_total), fmt_pm(valor_total), color=NAVY), width=3),
        dbc.Col(kpi_card("Bodega TOP", f"Bod.{bodega_top}", fmt_pm(panorama.iloc[0]["Valor"]) if not panorama.empty else "-", color=GOLD), width=3),
        dbc.Col(kpi_card("Productos", f"{panorama['Productos'].sum():,}" if not panorama.empty else "-", f"{int(panorama['Existencia'].sum()):,} unidades", color=GRAY), width=3),
    ], className="mb-4 g-3")
    children.append(kpi_row)

    panorama["_label"] = panorama["_bodega"].apply(lambda x: f"Bod.{str(x)[:12]}")
    n_bars = min(15, len(panorama))

    fig_barras = go.Figure()
    fig_barras.add_trace(go.Bar(
        y=panorama["_label"].head(n_bars), x=panorama["Valor"].head(n_bars) / 1e6,
        orientation="h", marker_color=[GOLD if i == 0 else BLUE for i in range(n_bars)],
        text=[fmt_pm(v) for v in panorama["Valor"].head(n_bars)],
        textposition="outside", textfont=dict(size=10, color=GRAY),
        hovertemplate="<b>%{y}</b><br>Valor: %{text}<br>Productos: %{customdata}<extra></extra>",
        customdata=panorama["Productos"].head(n_bars).tolist(),
    ))
    fig_barras.update_layout(**fig_layout(f"Top {n_bars} Bodegas por Valor (millones $)", height=380))
    fig_barras.update_xaxes(title="$ millones")
    fig_barras.update_yaxes(automargin=True, tickfont=dict(size=10), autorange="reversed")

    fig_sun = px.sunburst(panorama, path=["_bodega"], values="Valor",
        color="Valor", color_continuous_scale="Blues",
        hover_data={"_bodega": False, "Valor": True, "Productos": True})
    fig_sun.update_traces(
        texttemplate="<b>Bod.%{label}</b><br>%{value:,.0f}",
        hovertemplate="<b>Bod.%{label}</b><br>Valor: %{value:$,.0f}<br>Productos: %{customdata[0]}<extra></extra>",
    )
    fig_sun.update_layout(**fig_layout("Distribucion de Valor por Bodega", height=380))

    children.append(dbc.Row([
        dbc.Col(dcc.Graph(figure=fig_barras), width=6),
        dbc.Col(dcc.Graph(figure=fig_sun), width=6),
    ], className="mb-3 g-3"))

    table = dash_table.DataTable(
        columns=[{"name": "Bodega", "id": "_bodega"}, {"name": "Productos", "id": "Productos"},
                 {"name": "Valor", "id": "Valor"}, {"name": "Existencia", "id": "Existencia"},
                 {"name": "Disponible", "id": "Disponible"}, {"name": "Comprometido", "id": "Comprometido"}],
        data=[{"_bodega": r["_bodega"], "Productos": f"{int(r['Productos']):,}",
               "Valor": fmt_p(r["Valor"]), "Existencia": f"{int(r['Existencia']):,}",
               "Disponible": f"{int(r['Disponible']):,}", "Comprometido": f"{int(r['Comprometido']):,}"}
              for _, r in panorama.iterrows()],
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "6px 10px", "fontSize": "0.78rem", "fontFamily": "Segoe UI, Arial, sans-serif"},
        style_header={"fontWeight": "bold", "backgroundColor": DARKGRAY, "color": "white", "border": "none"},
        page_size=20,
    )
    children.append(html.Div([
        html.H6("● Detalle por Bodega", className="fw-bold mb-2", style={"color": NAVY, "fontSize": "0.85rem"}),
        table,
        html.Hr(),
    ]))

    return children


def pagina_criticos(data):
    n_criticos_comp = 0
    n_bajo_stock = 0
    vp = data["_valor"].sum()

    if "_cantidad_com" in data.columns and "_cantidad" in data.columns:
        data["_ratio_comp"] = data["_cantidad_com"] / data["_cantidad"].replace(0, 1) * 100
        criticos_comp = data[data["_ratio_comp"] > 80]
        n_criticos_comp = criticos_comp["_referencia"].nunique()

    if "_cantidad" in data.columns:
        bajo_stock_data = data[data["_cantidad"] <= 3]
        n_bajo_stock = bajo_stock_data["_referencia"].nunique()

    children = [section_title("Productos Criticos", f"{n_criticos_comp} alto compromiso | {n_bajo_stock} bajo stock")]

    kpi_row = dbc.Row([
        dbc.Col(kpi_card("Alto Compromiso", str(n_criticos_comp), ">80% ratio", color=RED), width=3),
        dbc.Col(kpi_card("Bajo Stock", str(n_bajo_stock), "3 unidades o menos", color=AMBER), width=3),
        dbc.Col(kpi_card("Valor Crítico", fmt_p(criticos_comp["_valor"].sum() if n_criticos_comp > 0 else 0), fmt_pm(criticos_comp["_valor"].sum() if n_criticos_comp > 0 else 0), color=NAVY), width=3),
        dbc.Col(kpi_card("Valor Total", fmt_p(vp), fmt_pm(vp), color=GRAY), width=3),
    ], className="mb-4 g-3")
    children.append(kpi_row)

    criticos = []

    if n_criticos_comp > 0:
        criticos_top = criticos_comp.groupby(["_referencia", "_linea", "_bodega"]).agg(
            Existencia=("_cantidad", "sum"), Disponible=("_cantidad_com", "sum"),
            Comprometido=("_cantidad_pen", "sum"), Valor=("_valor", "sum"),
        ).reset_index().sort_values("Valor", ascending=False).head(20)

        barras_data = criticos_top.groupby("_referencia")["Valor"].sum().sort_values(ascending=False).head(10)
        fig_crit = go.Figure()
        refs_short = [str(r)[:25] for r in barras_data.index]
        fig_crit.add_trace(go.Bar(x=[str(r)[:25] for r in barras_data.index],
            y=barras_data.values / 1e6,
            marker_color=RED, text=[f"${v/1e6:.1f}M" for v in barras_data.values],
            textposition="outside", textfont=dict(size=9, color=DARKGRAY),
            hovertemplate="<b>%{x}</b><br>Valor: $%{y:.1f}M<extra></extra>"))
        fig_crit.update_layout(**fig_layout("Top 10 Criticos por Valor (millones $)", height=320))
        fig_crit.update_xaxes(tickangle=-45, tickfont=dict(size=9))
        fig_crit.update_yaxes(title="$ millones", automargin=True)

        children.append(dbc.Row([dbc.Col(dcc.Graph(figure=fig_crit), width=12)], className="mb-3"))

        criticos.append(html.H6("● Alto Compromiso (>80%)", className="fw-bold", style={"color": RED, "fontSize": "0.85rem"}))
        criticos.append(dash_table.DataTable(
            columns=[{"name": c, "id": c} for c in ["_referencia", "_linea", "_bodega", "Existencia", "Disponible", "Comprometido", "Valor"]],
            data=[{"_referencia": r["_referencia"][:30], "_linea": r["_linea"],
                   "_bodega": r["_bodega"], "Existencia": f"{int(r['Existencia']):,}",
                   "Disponible": f"{int(r['Disponible']):,}", "Comprometido": f"{int(r['Comprometido']):,}",
                   "Valor": fmt_p(r["Valor"])} for _, r in criticos_top.iterrows()],
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "left", "padding": "5px 8px", "fontSize": "0.75rem", "fontFamily": "Segoe UI, Arial, sans-serif"},
            style_header={"fontWeight": "bold", "backgroundColor": DARKGRAY, "color": "white", "border": "none"},
            page_size=10,
        ))

    if n_bajo_stock > 0:
        bajo_top = bajo_stock_data.groupby(["_referencia", "_linea", "_bodega"]).agg(
            Existencia=("_cantidad", "sum"), Valor=("_valor", "sum"),
            Comprometido=("_cantidad_pen", "sum"),
        ).reset_index().sort_values("Valor", ascending=False).head(20)

        criticos.append(html.H6("● Bajo Stock (3 unidades o menos)", className="fw-bold mt-4", style={"color": AMBER, "fontSize": "0.85rem"}))
        criticos.append(dash_table.DataTable(
            columns=[{"name": c, "id": c} for c in ["_referencia", "_linea", "_bodega", "Existencia", "Comprometido", "Valor"]],
            data=[{"_referencia": r["_referencia"][:30], "_linea": r["_linea"],
                   "_bodega": r["_bodega"], "Existencia": f"{int(r['Existencia']):,}",
                   "Comprometido": f"{int(r['Comprometido']):,}",
                   "Valor": fmt_p(r["Valor"])} for _, r in bajo_top.iterrows()],
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "left", "padding": "5px 8px", "fontSize": "0.75rem", "fontFamily": "Segoe UI, Arial, sans-serif"},
            style_header={"fontWeight": "bold", "backgroundColor": DARKGRAY, "color": "white", "border": "none"},
            page_size=10,
        ))

    if not criticos:
        criticos.append(html.P("Datos insuficientes para analisis de criticos.", className="text-muted"))

    children.extend(criticos)
    children.append(html.Hr())
    return children
