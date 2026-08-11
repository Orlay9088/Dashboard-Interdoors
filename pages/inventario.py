from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pages.components import section_title, kpi_card, fmt_p, fmt_pm, safe_int, fig_layout, NAVY, BLUE, GREEN, AMBER, RED, GRAY, DARKGRAY, GOLD, graph_png


def pagina_resumen_stock(data):
    valor_total = data["_valor"].sum()
    productos = data["_referencia"].nunique()
    bodegas = data["_bodega"].nunique() if "_bodega" in data.columns else 0
    existencia = data["_cantidad"].sum() if "_cantidad" in data.columns else 0
    comprometido = data["_cantidad_pen"].sum() if "_cantidad_pen" in data.columns else 0
    disponible = data["_cantidad_com"].sum() if "_cantidad_com" in data.columns else 0
    pct_comp = (comprometido / existencia * 100) if existencia else 0

    children = [section_title("Resumen de Inventario", f"{productos:,} productos | {bodegas} bodegas | {existencia:,.0f} und")]

    kpi_row = dbc.Row([
        dbc.Col(kpi_card("Valor Total", fmt_p(valor_total), fmt_pm(valor_total), color=BLUE), width=3),
        dbc.Col(kpi_card("Productos", f"{productos:,}", f"{bodegas} bodegas activas", color=NAVY), width=3),
        dbc.Col(kpi_card("Existencia", f"{existencia:,.0f} und", f"Disponible: {disponible:,.0f}", color=GREEN), width=3),
        dbc.Col(kpi_card("Comprometido", f"{comprometido:,.0f} und", f"{pct_comp:.1f}% del stock", color=AMBER if pct_comp > 50 else GRAY), width=3),
    ], className="mb-4 g-3")
    children.append(kpi_row)

    top_prod = data.groupby(["_referencia", "_linea"]).agg(
        Valor=("_valor", "sum"), Existencia=("_cantidad", "sum"),
        Disponible=("_cantidad_com", "sum"), Comprometido=("_cantidad_pen", "sum"),
    ).reset_index().sort_values("Valor", ascending=False).head(10)

    labels = [str(r["_referencia"])[:20] for _, r in top_prod.iterrows()]
    fig_prod = go.Figure()
    fig_prod.add_trace(go.Bar(x=labels, y=top_prod["Valor"] / 1e6,
        marker_color=BLUE, text=[fmt_pm(v) for v in top_prod["Valor"]],
        textposition="outside", textfont=dict(size=10, color=DARKGRAY),
        hovertemplate="<b>%{x}</b><br>Valor: %{text}<br>Existencia: %{customdata:,} und<extra></extra>",
        customdata=top_prod["Existencia"].tolist()))
    fig_prod.update_layout(**fig_layout("Top 10 Productos por Valor (millones $)", height=380))
    fig_prod.update_xaxes(tickangle=-45, tickfont=dict(size=9))

    top_bod = data.groupby("_bodega").agg(
        Valor=("_valor", "sum"), Existencia=("_cantidad", "sum"),
        Productos=("_referencia", "nunique"),
    ).reset_index().sort_values("Valor", ascending=False).head(10)

    fig_bod = go.Figure()
    fig_bod.add_trace(go.Bar(y=top_bod["_bodega"].astype(str).apply(lambda x: x[:12]), x=top_bod["Valor"] / 1e6,
        orientation="h", marker_color=[GOLD if i == 0 else GREEN for i in range(len(top_bod))],
        text=[fmt_pm(v) for v in top_bod["Valor"]], textposition="outside",
        textfont=dict(size=10, color=DARKGRAY),
        hovertemplate="<b>%{y}</b><br>Valor: %{text}<br>Productos: %{customdata}<extra></extra>",
        customdata=top_bod["Productos"].tolist()))
    fig_bod.update_layout(**fig_layout("Top 10 Bodegas por Valor (millones $)", height=380))
    fig_bod.update_yaxes(automargin=True, tickfont=dict(size=10), autorange="reversed")

    children.append(dbc.Row([
        dbc.Col(graph_png(figure=fig_prod), width=6),
        dbc.Col(graph_png(figure=fig_bod), width=6),
    ], className="mb-3 g-3"))

    bodegas_data = data.groupby("_bodega").agg(
        Valor=("_valor", "sum"), Existencia=("_cantidad", "sum"),
        Comprometido=("_cantidad_pen", "sum"), Disponible=("_cantidad_com", "sum"),
    ).reset_index().sort_values("Valor", ascending=False)

    table = dash_table.DataTable(
        columns=[{"name": "Bodega", "id": "_bodega"}, {"name": "Valor", "id": "Valor"},
                 {"name": "Existencia", "id": "Existencia"}, {"name": "Comprometido", "id": "Comprometido"},
                 {"name": "Disponible", "id": "Disponible"}],
        data=[{"_bodega": str(r["_bodega"]), "Valor": fmt_p(r["Valor"]),
               "Existencia": f"{safe_int(r['Existencia']):,}", "Comprometido": f"{safe_int(r['Comprometido']):,}",
               "Disponible": f"{safe_int(r['Disponible']):,}"}
              for _, r in bodegas_data.iterrows()],
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.8rem", "fontFamily": "Segoe UI, Arial, sans-serif"},
        style_header={"fontWeight": "bold", "backgroundColor": DARKGRAY, "color": "white", "border": "none"},
        page_size=15,
    )
    children.append(html.Div([
        html.H6("Detalle por Bodega", className="fw-bold mb-2", style={"color": NAVY, "fontSize": "0.85rem"}),
        table,
        html.Hr(),
    ]))
    return children


def pagina_por_bodega(data):
    bodegas = sorted(data["_bodega"].dropna().unique()) if "_bodega" in data.columns else []
    if not bodegas:
        return [section_title("Inventario por Bodega", "Sin datos"),
                html.P("No hay datos de bodega.", className="text-muted")]

    panorama = data.groupby("_bodega").agg(
        Productos=("_referencia", "nunique"), Valor=("_valor", "sum"),
        Existencia=("_cantidad", "sum"), Disponible=("_cantidad_com", "sum"),
        Comprometido=("_cantidad_pen", "sum"),
    ).reset_index().sort_values("Valor", ascending=False)

    n_bodegas = len(panorama)
    valor_total = panorama["Valor"].sum()
    bodega_top = str(panorama.iloc[0]["_bodega"]) if not panorama.empty else "N/A"
    bodega_top_pct = (panorama.iloc[0]["Valor"] / valor_total * 100) if valor_total else 0

    children = [section_title("Inventario por Bodega", f"{n_bodegas} bodegas | Principal: Bod.{bodega_top} ({bodega_top_pct:.1f}%)")]

    kpi_row = dbc.Row([
        dbc.Col(kpi_card("Total Bodegas", str(n_bodegas), "Todas activas", color=BLUE), width=3),
        dbc.Col(kpi_card("Valor Total", fmt_p(valor_total), fmt_pm(valor_total), color=NAVY), width=3),
        dbc.Col(kpi_card("Bodega TOP", f"Bod.{bodega_top}", fmt_pm(panorama.iloc[0]["Valor"]) if not panorama.empty else "-", color=GOLD), width=3),
        dbc.Col(kpi_card("Productos", f"{data['_referencia'].nunique():,}", f"{safe_int(panorama['Existencia'].sum()):,} und", color=GRAY), width=3),
    ], className="mb-4 g-3")
    children.append(kpi_row)

    n_bars = min(15, len(panorama))
    panorama["_label"] = panorama["_bodega"].astype(str).apply(lambda x: f"Bod.{x[:12]}")

    fig_barras = go.Figure()
    fig_barras.add_trace(go.Bar(
        y=panorama["_label"].head(n_bars), x=panorama["Valor"].head(n_bars) / 1e6,
        orientation="h", marker_color=[GOLD if i == 0 else BLUE for i in range(n_bars)],
        text=[fmt_pm(v) for v in panorama["Valor"].head(n_bars)],
        textposition="outside", textfont=dict(size=10, color=DARKGRAY),
        hovertemplate="<b>%{y}</b><br>Valor: %{text}<br>Productos: %{customdata}<extra></extra>",
        customdata=panorama["Productos"].head(n_bars).tolist()))
    fig_barras.update_layout(**fig_layout(f"Top {n_bars} Bodegas por Valor (millones $)", height=380))
    fig_barras.update_xaxes(title="$ millones")
    fig_barras.update_yaxes(automargin=True, tickfont=dict(size=10), autorange="reversed")

    top_refs = data.groupby(["_referencia", "_bodega"]).agg(
        Existencia=("_cantidad", "sum"), Valor=("_valor", "sum"),
    ).reset_index().sort_values("Valor", ascending=False).head(10)

    ref_labels = [f"{r['_referencia'][:15]}@B{r['_bodega']}" for _, r in top_refs.iterrows()]
    fig_refs = go.Figure()
    fig_refs.add_trace(go.Bar(x=ref_labels, y=top_refs["Valor"] / 1e6,
        marker_color=GREEN, text=[fmt_pm(v) for v in top_refs["Valor"]],
        textposition="outside", textfont=dict(size=9, color=DARKGRAY)))
    fig_refs.update_layout(**fig_layout("Top 10 Referencias x Bodega (millones $)", height=380))
    fig_refs.update_xaxes(tickangle=-45, tickfont=dict(size=8))

    children.append(dbc.Row([
        dbc.Col(graph_png(figure=fig_barras), width=6),
        dbc.Col(graph_png(figure=fig_refs), width=6),
    ], className="mb-3 g-3"))

    table = dash_table.DataTable(
        columns=[{"name": "Bodega", "id": "_bodega"}, {"name": "Productos", "id": "Productos"},
                 {"name": "Valor", "id": "Valor"}, {"name": "Existencia", "id": "Existencia"},
                 {"name": "Disponible", "id": "Disponible"}, {"name": "Comprometido", "id": "Comprometido"}],
        data=[{"_bodega": str(r["_bodega"]), "Productos": f"{safe_int(r['Productos']):,}",
               "Valor": fmt_p(r["Valor"]), "Existencia": f"{safe_int(r['Existencia']):,}",
               "Disponible": f"{safe_int(r['Disponible']):,}", "Comprometido": f"{safe_int(r['Comprometido']):,}"}
              for _, r in panorama.iterrows()],
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "6px 10px", "fontSize": "0.78rem", "fontFamily": "Segoe UI, Arial, sans-serif"},
        style_header={"fontWeight": "bold", "backgroundColor": DARKGRAY, "color": "white", "border": "none"},
        page_size=20,
    )
    children.append(html.Div([
        html.H6("Detalle por Bodega", className="fw-bold mb-2", style={"color": NAVY, "fontSize": "0.85rem"}),
        table,
        html.Hr(),
    ]))
    return children


def pagina_criticos(data):
    data = data.copy()
    n_criticos_comp = 0
    n_bajo_stock = 0
    vp = data["_valor"].sum()

    if "_cantidad_com" in data.columns and "_cantidad" in data.columns:
        data["_ratio_comp"] = data["_cantidad_com"] / data["_cantidad"].replace(0, 1) * 100
        criticos_comp = data[data["_ratio_comp"] > 80]
        n_criticos_comp = criticos_comp["_referencia"].nunique()
    else:
        criticos_comp = pd.DataFrame()

    if "_cantidad" in data.columns:
        bajo_stock_data = data[data["_cantidad"] <= 3]
        n_bajo_stock = bajo_stock_data["_referencia"].nunique()
    else:
        bajo_stock_data = pd.DataFrame()

    children = [section_title("Productos Criticos", f"{n_criticos_comp} alto compromiso | {n_bajo_stock} bajo stock")]

    val_critico = criticos_comp["_valor"].sum() if n_criticos_comp > 0 else 0
    val_bajo = bajo_stock_data["_valor"].sum() if n_bajo_stock > 0 else 0

    kpi_row = dbc.Row([
        dbc.Col(kpi_card("Alto Compromiso", str(n_criticos_comp), ">80% ratio", color=RED), width=3),
        dbc.Col(kpi_card("Bajo Stock", str(n_bajo_stock), "3 und o menos", color=AMBER), width=3),
        dbc.Col(kpi_card("Valor Critico", fmt_p(val_critico), fmt_pm(val_critico), color=NAVY), width=3),
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
        refs_short = [str(r)[:25] for r in barras_data.index]
        fig_crit = go.Figure()
        fig_crit.add_trace(go.Bar(x=refs_short,
            y=barras_data.values / 1e6,
            marker_color=RED, text=[f"${v/1e6:.1f}M" for v in barras_data.values],
            textposition="outside", textfont=dict(size=9, color=DARKGRAY),
            hovertemplate="<b>%{x}</b><br>Valor: $%{y:.1f}M<extra></extra>"))
        fig_crit.update_layout(**fig_layout("Top 10 Criticos por Valor (millones $)", height=320))
        fig_crit.update_xaxes(tickangle=-45, tickfont=dict(size=9))
        fig_crit.update_yaxes(title="$ millones", automargin=True)

        children.append(dbc.Row([dbc.Col(graph_png(figure=fig_crit), width=12)], className="mb-3"))

        criticos.append(html.H6("Alto Compromiso (>80%)", className="fw-bold", style={"color": RED, "fontSize": "0.85rem"}))
        criticos.append(dash_table.DataTable(
            columns=[{"name": c, "id": c} for c in ["_referencia", "_linea", "_bodega", "Existencia", "Disponible", "Comprometido", "Valor"]],
            data=[{"_referencia": str(r["_referencia"])[:30], "_linea": str(r["_linea"]),
                   "_bodega": str(r["_bodega"]), "Existencia": f"{safe_int(r['Existencia']):,}",
                   "Disponible": f"{safe_int(r['Disponible']):,}", "Comprometido": f"{safe_int(r['Comprometido']):,}",
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

        criticos.append(html.H6("Bajo Stock (3 und o menos)", className="fw-bold mt-4", style={"color": AMBER, "fontSize": "0.85rem"}))
        criticos.append(dash_table.DataTable(
            columns=[{"name": c, "id": c} for c in ["_referencia", "_linea", "_bodega", "Existencia", "Comprometido", "Valor"]],
            data=[{"_referencia": str(r["_referencia"])[:30], "_linea": str(r["_linea"]),
                   "_bodega": str(r["_bodega"]), "Existencia": f"{safe_int(r['Existencia']):,}",
                   "Comprometido": f"{safe_int(r['Comprometido']):,}",
                   "Valor": fmt_p(r["Valor"])} for _, r in bajo_top.iterrows()],
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "left", "padding": "5px 8px", "fontSize": "0.75rem", "fontFamily": "Segoe UI, Arial, sans-serif"},
            style_header={"fontWeight": "bold", "backgroundColor": DARKGRAY, "color": "white", "border": "none"},
            page_size=10,
        ))

    if not criticos:
        criticos.append(html.P("No se encontraron productos criticos en este inventario.", className="text-muted"))

    children.extend(criticos)
    children.append(html.Hr())
    return children
