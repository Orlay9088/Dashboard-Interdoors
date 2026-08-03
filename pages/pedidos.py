from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from pages.components import (
    section_title, kpi_card, fmt_p, fmt_pm, fig_layout,
    NAVY, BLUE, AMBER, GREEN, RED, GRAY, DARKGRAY, GOLD, kahoot_podium, apply_filters, graph_png,
)


def pagina_home(data):
    from firebase_config import load_local

    pedidos = data.copy()
    try:
        from dash_app import _data_cache
        facturas = _data_cache.get("facturas")
        inventario = _data_cache.get("inventario")
    except Exception:
        facturas = None
        inventario = None
    if facturas is None:
        facturas = load_local("facturas")
    else:
        facturas = facturas.copy()
    if inventario is None:
        inventario = load_local("inventario")
    else:
        inventario = inventario.copy()

    vp = pedidos["_valor"].sum() if not pedidos.empty else 0
    vc = pedidos["_valor_sec"].sum() if not pedidos.empty and "_valor_sec" in pedidos.columns else 0
    ped_count = pedidos["_documento"].nunique() if not pedidos.empty else 0
    ped_clientes = pedidos["_cliente"].nunique() if not pedidos.empty else 0
    ped_asesores = pedidos["_vendedor"].nunique() if not pedidos.empty else 0

    vf = facturas["_valor"].sum() if not facturas.empty else 0
    fact_count = facturas["_documento"].nunique() if not facturas.empty else 0
    fact_costo = facturas["_costo"].sum() if not facturas.empty and "_costo" in facturas.columns else 0
    mgn_pct = (vf - fact_costo) / vf * 100 if vf else 0

    vi = inventario["_valor"].sum() if not inventario.empty else 0
    inv_prod = inventario["_referencia"].nunique() if not inventario.empty else 0
    inv_bod = inventario["_bodega"].nunique() if not inventario.empty and "_bodega" in inventario.columns else 0
    inv_exist = inventario["_cantidad"].sum() if not inventario.empty else 0

    children = [section_title("Dashboard Interdoors", "Resumen consolidado de todos los modulos")]

    children.append(_home_block("PEDIDOS", BLUE, [
        ("Valor Pendiente", fmt_p(vp), fmt_pm(vp)),
        ("Comprometido", fmt_p(vc), f"{(vc/vp*100):.1f}% cumplimiento" if vp else "0%"),
        ("Pedidos", f"{ped_count:,}", f"{ped_clientes} clientes"),
        ("Asesores", str(ped_asesores), "activos en el periodo"),
    ], pedidos.empty))

    children.append(_home_block("FACTURACION", GREEN, [
        ("Ventas Totales", fmt_p(vf), fmt_pm(vf)),
        ("Margen Global", f"{mgn_pct:.1f}%", f"Costo: {fmt_pm(fact_costo)}"),
        ("Facturas", f"{fact_count:,}" if fact_count else "-", "emitidas" if fact_count else "Sin datos"),
        ("Ticket Prom.", fmt_p(vf/fact_count) if fact_count else "-", "por factura" if fact_count else ""),
    ], facturas.empty))

    children.append(_home_block("INVENTARIO", AMBER, [
        ("Valor Inventario", fmt_p(vi), fmt_pm(vi)),
        ("Productos", f"{inv_prod:,}" if inv_prod else "-", f"{inv_bod} bodegas" if inv_bod else ""),
        ("Existencia", f"{inv_exist:,.0f} und" if inv_exist else "-", "unidades totales" if inv_exist else "Sin datos"),
        ("Valor Prom.", fmt_p(vi/inv_prod) if inv_prod else "-", "por producto" if inv_prod else ""),
    ], inventario.empty))

    if not pedidos.empty and not inventario.empty and "_referencia" in pedidos.columns and "_referencia" in inventario.columns:
        ped_refs = pedidos.groupby("_referencia")["_cantidad"].sum().reset_index()
        ped_refs.columns = ["_referencia", "demanda"]
        inv_refs = inventario.groupby("_referencia").agg(
            stock=("_cantidad", "sum"), disponible=("_cantidad_com", "sum")
        ).reset_index()
        cruzado = ped_refs.merge(inv_refs, on="_referencia", how="inner")
        if not cruzado.empty:
            cruzado["deficit"] = cruzado["demanda"] - cruzado["disponible"]
            alertas = cruzado[cruzado["deficit"] > 0].sort_values("deficit", ascending=False).head(10)
            if not alertas.empty:
                children.append(html.Div([
                    html.H6("ALERTAS: Demanda vs Stock", className="fw-bold mb-2", style={"color": RED, "fontSize": "0.8rem", "letterSpacing": "1px", "textTransform": "uppercase"}),
                    html.P(f"{len(alertas)} productos con demanda mayor al stock disponible", style={"fontSize": "0.7rem", "color": GRAY, "marginBottom": "8px"}),
                    dash_table.DataTable(
                        columns=[{"name": "Referencia", "id": "_referencia"}, {"name": "Demanda", "id": "demanda"},
                                 {"name": "Disponible", "id": "disponible"}, {"name": "Deficit", "id": "deficit"}],
                        data=[{"_referencia": str(r["_referencia"])[:25], "demanda": f"{int(r['demanda']):,}",
                               "disponible": f"{int(r['disponible']):,}", "deficit": f"{int(r['deficit']):,}"}
                              for _, r in alertas.iterrows()],
                        style_table={"overflowX": "auto"},
                        style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.7rem", "fontFamily": "Segoe UI, Arial, sans-serif"},
                        style_header={"fontWeight": "bold", "backgroundColor": DARKGRAY, "color": "white", "border": "none"},
                        style_data_conditional=[
                            {"if": {"column_id": "deficit"}, "color": RED, "fontWeight": "bold"},
                        ],
                        page_size=10,
                    ),
                ], style={"background": "white", "borderRadius": "12px", "padding": "14px 20px", "marginBottom": "16px",
                           "borderLeft": f"5px solid {RED}", "boxShadow": "0 1px 3px rgba(0,0,0,0.05)"}))

    children.append(html.Hr())
    return children


def _home_block(title, color, kpis, is_empty):
    mod_id = "pedidos" if title == "PEDIDOS" else "facturas" if title == "FACTURACION" else "inventario"
    first_page = "resumen" if title != "PEDIDOS" else "resumen"

    if is_empty:
        return html.Div([
            html.Div([
                html.H6(title, className="fw-bold mb-1", style={"color": color, "fontSize": "0.8rem", "display": "inline", "letterSpacing": "1.5px", "textTransform": "uppercase"}),
                html.Button("Ir al modulo", id={"type": "home-nav", "mod": mod_id, "page": first_page}, style={
                    "background": "none", "border": f"1px solid {color}", "cursor": "pointer",
                    "color": color, "fontSize": "0.6rem", "padding": "2px 8px", "borderRadius": "4px",
                    "float": "right",
                }),
            ]),
            html.P("Sin datos. Sube un archivo Excel en el panel lateral.", style={"color": GRAY, "fontSize": "0.8rem", "fontStyle": "italic"}),
        ], style={"background": "white", "borderRadius": "12px", "padding": "16px 20px", "marginBottom": "16px",
                   "borderLeft": f"5px solid {color}", "boxShadow": "0 1px 3px rgba(0,0,0,0.05)"})

    return html.Div([
        html.Div([
            html.H6(title, className="fw-bold mb-3", style={"color": color, "fontSize": "0.8rem", "display": "inline", "letterSpacing": "1.5px", "textTransform": "uppercase"}),
            html.Button("Ir al modulo", id={"type": "home-nav", "mod": mod_id, "page": first_page}, style={
                "background": "none", "border": f"1px solid {color}", "cursor": "pointer",
                "color": color, "fontSize": "0.6rem", "padding": "2px 8px", "borderRadius": "4px",
                "float": "right", "marginTop": "-3px",
            }),
        ]),
        dbc.Row([
            dbc.Col(kpi_card(name, val, sub, color=(color if i == 0 else NAVY if i == 1 else GRAY)), width=3)
            for i, (name, val, sub) in enumerate(kpis)
        ], className="g-3"),
    ], style={"background": "white", "borderRadius": "12px", "padding": "16px 20px", "marginBottom": "16px",
               "borderLeft": f"5px solid {color}", "boxShadow": "0 1px 3px rgba(0,0,0,0.05)"})


def pagina_resumen(data):
    vp = data["_valor"].sum()
    vc = data["_valor_sec"].sum()
    total_pedidos = data["_documento"].nunique()
    total_clientes = data["_cliente"].nunique()
    num_asesores = data["_vendedor"].nunique()
    cant_pedida = data["_cantidad"].sum()
    cant_pendiente = data["_cantidad_pen"].sum()
    pct_pend = (cant_pendiente / cant_pedida * 100) if cant_pedida else 0
    promedio_cliente = vp / total_clientes if total_clientes else 0
    promedio_pedido = vp / total_pedidos if total_pedidos else 0

    children = [section_title("Resumen Ejecutivo", "Pedidos - Indicadores principales")]

    kpi_row = dbc.Row([
        dbc.Col(kpi_card("Valor Total", fmt_p(vp), fmt_pm(vp), color=BLUE), width=3),
        dbc.Col(kpi_card("Pedidos", f"{total_pedidos:,}", f"{cant_pedida:,.0f} unidades", color=NAVY), width=3),
        dbc.Col(kpi_card("Clientes Activos", f"{total_clientes}", f"{num_asesores} asesores", color=NAVY), width=3),
        dbc.Col(kpi_card("Valor Pendiente", fmt_p(vp), f"{pct_pend:.2f}% del pedido", color=AMBER), width=3),
    ], className="mb-4 g-3")
    children.append(kpi_row)

    kpi2 = dbc.Row([
        dbc.Col(kpi_card("Promedio x Cliente", fmt_p(promedio_cliente), fmt_pm(promedio_cliente), color=GRAY), width=3),
        dbc.Col(kpi_card("Promedio x Pedido", fmt_p(promedio_pedido), fmt_pm(promedio_pedido), color=GRAY), width=3),
        dbc.Col(kpi_card("Cumplimiento", f"{vc/vp*100:.2f}%" if vp else "0%", f"{fmt_p(vc)} comprometido", color=GREEN), width=3),
        dbc.Col(kpi_card("Construccion", f"{data[data['_canal'].str.contains('CNST|CONSTR', case=False, na=False)]['_valor'].sum()/vp*100:.2f}%" if vp else "0%", "% del total", color=AMBER), width=3),
    ], className="mb-4 g-3")
    children.append(kpi2)

    evol = data.groupby(data["_fecha"].dt.to_period("M")).agg(
        Valor_pendiente=("_valor", "sum"), Comprometido=("_valor_sec", "sum"),
        Pedidos=("_documento", "nunique"),
    ).reset_index()
    evol["Fecha"] = evol["_fecha"].astype(str)

    fig_evol = go.Figure()
    fig_evol.add_trace(go.Scatter(x=evol["Fecha"], y=evol["Valor_pendiente"] / 1e6,
        mode="lines+markers", name="Valor Pendiente",
        line=dict(width=3, color=BLUE), marker=dict(size=6, color=BLUE)))
    fig_evol.add_trace(go.Scatter(x=evol["Fecha"], y=evol["Comprometido"] / 1e6,
        mode="lines+markers", name="Comprometido",
        line=dict(width=3, color=GREEN), marker=dict(size=6, color=GREEN)))
    fig_evol.update_layout(**fig_layout("Evolucion Mensual (millones $)", height=380))
    fig_evol.update_layout(legend=dict(orientation="h", y=1.1, x=0.7))
    fig_evol.update_xaxes(tickangle=-45, tickfont=dict(size=9), dtick="M1")

    top_asesores = data.groupby("_vendedor").agg(
        Valor=("_valor", "sum"),
    ).reset_index().sort_values("Valor", ascending=True).tail(10)

    fig_asesores = go.Figure()
    fig_asesores.add_trace(go.Bar(x=top_asesores["Valor"] / 1e6, y=top_asesores["_vendedor"],
        orientation="h", marker_color=BLUE,
        text=[fmt_pm(v) for v in top_asesores["Valor"]], textposition="outside"))
    fig_asesores.update_layout(**fig_layout("Top 10 Asesores (millones $)", height=380,
        margin=dict(t=40, b=20, l=20, r=40)))
    fig_asesores.update_xaxes(title="$ millones")
    fig_asesores.update_yaxes(automargin=True, tickfont=dict(size=10))

    part_const = (data[data["_canal"].str.contains("CNST|CONSTR", case=False, na=False)]["_valor"].sum() / vp * 100) if vp else 0
    top3 = data.groupby("_cliente")["_valor"].sum().sort_values(ascending=False)
    top3_pct = (top3.iloc[:3].sum() / vp * 100) if vp and len(top3) > 0 else 0
    cumpl_val = (vc / vp * 100) if vp else 0

    evol_table = dash_table.DataTable(
        columns=[{"name": "Mes", "id": "Fecha"}, {"name": "Valor", "id": "V_pend"},
                 {"name": "Comprometido", "id": "V_comp"}, {"name": "Pedidos", "id": "N_pedidos"}],
        data=[{"Fecha": r["Fecha"], "V_pend": fmt_p(r["Valor_pendiente"]),
               "V_comp": fmt_p(r["Comprometido"]), "N_pedidos": f"{int(r['Pedidos']):,}"}
              for _, r in evol.tail(12).iterrows()],
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.8rem"},
        style_header={"fontWeight": "bold", "backgroundColor": DARKGRAY, "color": "white", "border": "none"},
        page_size=12,
    )

    children.append(dbc.Row([
        dbc.Col(graph_png(figure=fig_evol), width=6),
        dbc.Col(html.Div([
            html.H6("Indicadores Clave", className="fw-bold", style={"color": NAVY}),
            html.Ul([
                html.Li(f"Participacion Construccion: {part_const:.1f}%"),
                html.Li(f"Top 3 clientes concentran: {top3_pct:.1f}%"),
                html.Li(f"Cumplimiento general: {cumpl_val:.1f}%"),
            ], className="small"),
            html.Hr(),
            graph_png(figure=fig_asesores, style={"height": "300px"}),
        ]), width=6),
    ], className="mb-3 g-3"))

    children.append(html.Details([
        html.Summary("   Ver Evolucion Mensual (12 meses)", style={
            "cursor": "pointer", "color": NAVY, "fontWeight": "600",
            "fontSize": "0.85rem", "padding": "6px 0",
        }),
        html.Div(evol_table, style={"marginTop": "8px", "marginBottom": "8px"}),
    ], open=False))
    children.append(html.Hr())

    return children


def pagina_participacion(data):
    vp = data["_valor"].sum()
    n_canales = data["_canal"].nunique() if "_canal" in data.columns else 0
    n_asesores = data["_vendedor"].nunique()
    n_lineas = data["_linea"].nunique() if "_linea" in data.columns else 0
    n_clientes = data["_cliente"].nunique()

    canal_top = data.groupby("_canal")["_valor"].sum().idxmax() if "_canal" in data.columns else "N/A"

    children = [section_title("Participacion Comercial", f"{n_canales} canales | {n_asesores} asesores | {n_lineas} lineas | {n_clientes} clientes")]

    kpi_row = dbc.Row([
        dbc.Col(kpi_card("Valor Total", fmt_p(vp), fmt_pm(vp), color=BLUE), width=3),
        dbc.Col(kpi_card("Canales", str(n_canales), f"Principal: {canal_top[:18]}", color=NAVY), width=3),
        dbc.Col(kpi_card("Asesores", str(n_asesores), f"Promedio: {fmt_pm(vp/n_asesores) if n_asesores else 0}", color=GRAY), width=3),
        dbc.Col(kpi_card("Lineas", str(n_lineas), "Diversidad de portafolio", color=GREEN), width=3),
    ], className="mb-4 g-3")
    children.append(kpi_row)

    canales = data.groupby("_canal").agg(Valor=("_valor", "sum")).reset_index().sort_values("Valor", ascending=False)
    canales["%"] = (canales["Valor"] / vp * 100).round(2)

    fig_canal = go.Figure(go.Pie(
        labels=canales["_canal"], values=canales["Valor"],
        hole=0.45, textinfo="label+percent",
        marker=dict(colors=[BLUE, GREEN, "#f59e0b", RED, "#8b5cf6"], line=dict(color="white", width=2)),
        hovertemplate="<b>%{label}</b><br>%{value:$,.0f}<br>%{percent}<extra></extra>",
    ))
    fig_canal.add_annotation(text=fmt_pm(vp), x=0.5, y=0.5, showarrow=False,
        font=dict(size=16, color=DARKGRAY, family="Segoe UI"), xref="paper", yref="paper")
    fig_canal.update_layout(**fig_layout("Por Canal", height=370))
    fig_canal.update_layout(clickmode="event+select")

    asesores = data.groupby("_vendedor").agg(Valor=("_valor", "sum"), Pedidos=("_documento", "nunique")).reset_index().sort_values("Valor", ascending=False)
    asesores["%"] = (asesores["Valor"] / vp * 100).round(2)
    top_ase = asesores.head(12)
    fig_ase = go.Figure(go.Bar(
        x=top_ase["Valor"] / 1e6, y=top_ase["_vendedor"], orientation="h",
        marker_color=[GOLD if i == 0 else BLUE for i in range(len(top_ase))],
        text=[f"{(r['%'])}% · {r['Pedidos']} ped" for _, r in top_ase.iterrows()],
        textposition="outside", textfont=dict(size=9, color=GRAY),
        hovertemplate="<b>%{y}</b><br>$%{x:.1f}M<br>%{text}<extra></extra>",
    ))
    fig_ase.update_layout(**fig_layout("Top Asesores (millones $)", height=370))
    fig_ase.update_xaxes(title="$ millones")
    fig_ase.update_yaxes(automargin=True, autorange="reversed")

    lineas = data.groupby("_linea").agg(Valor=("_valor", "sum"), Pedidos=("_documento", "nunique")).reset_index().sort_values("Valor", ascending=False)
    lineas["%"] = (lineas["Valor"] / vp * 100).round(2)
    top_lin = lineas.head(12)
    fig_lin = go.Figure(go.Bar(
        x=top_lin["Valor"] / 1e6, y=top_lin["_linea"], orientation="h",
        marker_color=[GREEN if i > 0 else "#0C8E82" for i in range(len(top_lin))],
        text=[f"{r['%']:.1f}% · {r['Pedidos']} ped" for _, r in top_lin.iterrows()],
        textposition="outside", textfont=dict(size=9, color=GRAY),
        hovertemplate="<b>%{y}</b><br>$%{x:.1f}M<br>%{text}<extra></extra>",
    ))
    fig_lin.update_layout(**fig_layout("Top Lineas (millones $)", height=370))
    fig_lin.update_xaxes(title="$ millones")
    fig_lin.update_yaxes(automargin=True, autorange="reversed")

    children.append(dbc.Row([
        dbc.Col(graph_png(figure=fig_canal, id="chart-canal-pie"), width=4),
        dbc.Col(graph_png(figure=fig_ase, id="chart-asesor-participacion"), width=4),
        dbc.Col(graph_png(figure=fig_lin), width=4),
    ], className="mb-3 g-3"))

    canal_table = dash_table.DataTable(
        columns=[{"name": "Canal", "id": "_canal"}, {"name": "Valor", "id": "Valor"}, {"name": "%", "id": "%"}],
        data=[{"_canal": r["_canal"], "Valor": fmt_p(r["Valor"]), "%": f"{r['%']:.1f}%"} for _, r in canales.iterrows()],
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "5px 10px", "fontSize": "0.78rem", "fontFamily": "Segoe UI, Arial, sans-serif"},
        style_header={"fontWeight": "bold", "backgroundColor": DARKGRAY, "color": "white"},
        page_size=10,
    )
    children.append(html.Div([
        html.H6("● Distribucion por Canal", className="fw-bold mb-2", style={"color": NAVY, "fontSize": "0.85rem"}),
        canal_table,
        html.Hr(),
    ]))

    return children


def pagina_pareto(data):
    vp = data["_valor"].sum()
    canal = data["_canal"].iloc[0] if len(data["_canal"].unique()) == 1 else "TODOS"
    titulo = f"Pareto - {canal}"

    pg = data.groupby("_cliente").agg(Valor=("_valor", "sum")).reset_index().sort_values("Valor", ascending=False).reset_index(drop=True)
    pg["%"] = (pg["Valor"] / vp * 100).round(2)
    pg["% Acum"] = pg["%"].cumsum()
    pg.insert(0, "#", range(1, len(pg) + 1))
    top = pg.head(15).copy()
    top["_label"] = top["_cliente"].apply(lambda x: x[:22] + "..." if len(str(x)) > 25 else str(x))

    fig = go.Figure()
    fig.add_trace(go.Bar(x=top["_label"], y=top["Valor"],
        marker_color=BLUE, name="Valor", text=[fmt_pm(v) for v in top["Valor"]], textposition="outside"))
    fig.add_trace(go.Scatter(x=top["_label"], y=top["% Acum"],
        name="% Acumulado", yaxis="y2", marker_color=RED, mode="lines+markers", line=dict(width=3)))
    fig.update_layout(**fig_layout(titulo, height=420,
        margin=dict(t=40, b=60, l=80, r=50),
        yaxis=dict(title="$", gridcolor="#f1f5f9", zeroline=False),
        yaxis2=dict(title="%", overlaying="y", side="right", range=[0, 105])))
    fig.update_xaxes(tickangle=-45, tickfont=dict(size=9))

    hasta_80 = (pg["% Acum"] <= 80).sum()
    top3_pct = pg.head(3)["%"].sum()

    table = dash_table.DataTable(
        columns=[{"name": c, "id": c} for c in ["#", "_cliente", "Valor", "%", "% Acum"]],
        data=pg.head(50).to_dict("records"),
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.8rem"},
        style_header={"fontWeight": "bold", "backgroundColor": DARKGRAY, "color": "white", "border": "none"},
        page_size=10,
    )

    top10 = html.Div([
        html.H6("Indicadores", className="fw-bold"),
        dbc.Row([
            dbc.Col(dmc.Card([
                dmc.CardSection([html.Small("Top 3 concentran", className="text-muted d-block"),
                                 html.Strong(f"{top3_pct:.1f}%")])
            ], withBorder=True, shadow="sm", padding="md", radius="sm", className="text-center mb-2")),
            dbc.Col(dmc.Card([
                dmc.CardSection([html.Small("Clientes hasta 80%", className="text-muted d-block"),
                                 html.Strong(str(hasta_80))])
            ], withBorder=True, shadow="sm", padding="md", radius="sm", className="text-center mb-2")),
        ]),
        dmc.Card([
            dmc.CardSection([html.Small("Total Clientes", className="text-muted d-block"),
                             html.Strong(str(len(pg)))])
        ], withBorder=True, shadow="sm", padding="md", radius="sm", className="text-center"),
    ])

    children = [section_title("Pareto de Clientes", "Analisis de concentracion")]
    children.append(dbc.Row([
        dbc.Col(graph_png(figure=fig, style={"height": "460px"}), width=8),
        dbc.Col(top10, width=4),
    ], className="mb-3 g-3"))
    children.append(table)
    children.append(html.Hr())
    return children


def pagina_ranking(data):
    rank = data[~data["_vendedor"].isin(["VENTAS CORPORATIVAS", "VENTAS INTERNACIONALES"])].groupby("_vendedor").agg(
        Valor=("_valor", "sum"), Pedidos=("_documento", "nunique"),
        Clientes=("_cliente", "nunique"), Comprometido=("_valor_sec", "sum"),
    ).reset_index().sort_values("Valor", ascending=False).reset_index(drop=True)

    tv = rank["Valor"].sum()
    rank["% Part"] = (rank["Valor"] / tv * 100).round(2) if tv else 0

    from budget import cargar_presupuesto_asesores, get_budget_for
    from config import RUTA_PRESUPUESTO, RUTA_PRESUPUESTO_ASESORES
    try:
        budgets = cargar_presupuesto_asesores(str(RUTA_PRESUPUESTO))
    except Exception:
        budgets = {}
    if not budgets:
        try:
            budgets = cargar_presupuesto_asesores(str(RUTA_PRESUPUESTO_ASESORES))
        except Exception:
            budgets = {}
    rank["Presupuesto"] = rank["_vendedor"].apply(lambda x: get_budget_for(x, budgets))
    has_budgets = rank["Presupuesto"].sum() > 0
    rank["% Presup"] = rank.apply(lambda r: round(r["Valor"] / r["Presupuesto"] * 100, 2) if r["Presupuesto"] > 0 else 0, axis=1)
    rank["% Cumpl"] = rank.apply(lambda r: round(r["Comprometido"] / r["Presupuesto"] * 100, 2) if r["Presupuesto"] > 0 else 0, axis=1)
    rank.insert(0, "#", range(1, len(rank) + 1))

    n_asesores = len(rank)
    presup_total = rank["Presupuesto"].sum()
    presup_pct = (tv / presup_total * 100) if presup_total else 0
    presup_color = GREEN if presup_pct >= 100 else AMBER if presup_pct >= 70 else RED
    promedio = tv / n_asesores if n_asesores else 0
    brecha = (rank["Valor"].iloc[0] / promedio) if promedio > 0 else 1
    meta_str = f"Meta total: {fmt_pm(presup_total)}" if presup_total else "Sin metas cargadas"
    title_sub = f"{n_asesores} asesores | {meta_str}"

    children = [section_title("Ranking de Asesores", title_sub)]

    top3 = rank.head(3)
    children.append(kahoot_podium(top3))

    kpi_row = dbc.Row([
        dbc.Col(kpi_card("Asesores Activos", f"{n_asesores}", f"Brecha #1 vs prom: {brecha:.1f}x", color=BLUE), width=3),
        dbc.Col(kpi_card("Valor Total", fmt_p(tv), fmt_pm(tv), color=NAVY), width=3),
        dbc.Col(kpi_card("vs Presupuesto", f"{presup_pct:.1f}%" if has_budgets else "-", f"Meta: {fmt_pm(presup_total)}" if presup_total else "Sin datos", color=presup_color), width=3),
        dbc.Col(kpi_card("Cumpl. Prom.", f"{rank['% Cumpl'].mean():.1f}%" if has_budgets else "-", f"Top 3: {rank.head(3)['% Part'].sum():.1f}%", color=GREEN if rank['% Cumpl'].mean() > 50 else AMBER), width=3),
    ], className="mb-4 g-3")
    children.append(kpi_row)

    top_show = rank.head(min(20, len(rank)))
    chart_n = len(top_show)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=top_show["Valor"] / 1e6,
        y=top_show["_vendedor"],
        orientation="h",
        marker=dict(
            color=[GOLD if i == 0 else BLUE for i in range(chart_n)],
            line=dict(color="white", width=1),
        ),
        text=[fmt_pm(v) for v in top_show["Valor"]],
        textposition="outside",
        textfont=dict(size=10, color=GRAY),
        hovertemplate="<b>%{y}</b><br>Valor: %{text}<br>Participacion: %{customdata}%<extra></extra>",
        customdata=top_show["% Part"].tolist(),
    ))
    chart_h = max(320, min(700, chart_n * 28))
    fig.update_layout(**fig_layout(f"Top {chart_n} Asesores por Valor (millones $)", height=chart_h,
        margin=dict(t=40, b=20, l=20, r=50)))
    fig.update_xaxes(title="$ millones", showgrid=True, gridcolor="#e2e8f0")
    fig.update_yaxes(automargin=True, tickfont=dict(size=10), autorange="reversed")
    children.append(dbc.Row([dbc.Col(graph_png(figure=fig, id="chart-ranking-asesores"), width=12)], className="mb-3"))

    table_data = []
    for _, r in rank.iterrows():
        cumpl_pct = r["% Cumpl"]
        has_ppto = r["Presupuesto"] > 0
        row = {
            "#": r["#"],
            "_vendedor": r["_vendedor"],
            "Valor_total": fmt_p(r["Valor"]),
            "Presupuesto": fmt_p(r["Presupuesto"]) if has_ppto else "-",
            "% Part": f"{r['% Part']:.1f}%",
            "% Presup": f"{r['% Presup']:.1f}%" if has_ppto else "-",
            "Pedidos": f"{int(r['Pedidos']):,}",
            "Clientes": f"{int(r['Clientes'])}",
            "% Cumpl": f"{cumpl_pct:.1f}%" if has_ppto else "-",
            "_cumpl_num": cumpl_pct if has_ppto else -1,
            "_presup_num": r["Presupuesto"],
        }
        table_data.append(row)

    table = dash_table.DataTable(
        columns=[{"name": c, "id": c} for c in ["#", "_vendedor", "Valor_total", "Presupuesto", "% Part", "% Presup", "Pedidos", "Clientes", "% Cumpl"]],
        data=table_data,
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "6px 10px", "fontSize": "0.75rem", "fontFamily": "Segoe UI, Arial, sans-serif"},
        style_header={"fontWeight": "bold", "backgroundColor": DARKGRAY, "color": "white", "border": "none"},
        style_data_conditional=[
            {
                "if": {"filter_query": "{#} = 1"},
                "backgroundColor": "#FFF8E1", "fontWeight": "bold",
                "borderLeft": f"4px solid {GOLD}",
            },
            {
                "if": {"filter_query": "{#} = 2"},
                "backgroundColor": "#F8FAFC", "fontWeight": "bold",
                "borderLeft": "4px solid #B8BCC8",
            },
            {
                "if": {"filter_query": "{#} = 3"},
                "backgroundColor": "#FFF5EC", "fontWeight": "bold",
                "borderLeft": "4px solid #CD7F32",
            },
            {
                "if": {"filter_query": "{_cumpl_num} >= 100", "column_id": "% Cumpl"},
                "color": GREEN, "fontWeight": "bold",
            },
            {
                "if": {"filter_query": "{_cumpl_num} >= 70 && {_cumpl_num} < 100", "column_id": "% Cumpl"},
                "color": "#E5A100", "fontWeight": "bold",
            },
            {
                "if": {"filter_query": "{_cumpl_num} >= 0 && {_cumpl_num} < 70", "column_id": "% Cumpl"},
                "color": RED, "fontWeight": "bold",
            },
            {
                "if": {"filter_query": "{_cumpl_num} < 0", "column_id": "% Cumpl"},
                "color": GRAY,
            },
        ],
        page_size=20,
        sort_action="native",
    )
    children.append(table)
    children.append(html.Hr())
    return children


def pagina_embudo(data):
    vp = data["_valor"].sum()
    vc = data["_valor_sec"].sum() if "_valor_sec" in data.columns else 0
    total_pedidos = data["_documento"].nunique()

    funnel = data.groupby("_estado").agg(
        Valor=("_valor", "sum"), Pedidos=("_documento", "nunique"),
    ).reset_index().sort_values("Valor", ascending=False)
    total = funnel["Valor"].sum()
    funnel["%"] = (funnel["Valor"] / total * 100).round(2) if total else 0

    comp = funnel[funnel["_estado"].str.contains("Comprometido|Cumplid|Cerrad|Despac", na=False, case=False)]["Valor"].sum()
    rate = comp / total * 100 if total else 0

    estados_n = len(funnel)

    children = [section_title("Embudo de Pedidos", f"{estados_n} estados | Tasa cierre: {rate:.1f}%")]

    kpi_row = dbc.Row([
        dbc.Col(kpi_card("Pipeline Total", fmt_p(vp), f"{total_pedidos:,} pedidos", color=BLUE), width=3),
        dbc.Col(kpi_card("Comprometido", fmt_p(comp), fmt_pm(comp), color=GREEN), width=3),
        dbc.Col(kpi_card("Tasa de Cierre", f"{rate:.1f}%", f"Pendiente: {fmt_pm(vp-comp)}", color=GREEN if rate > 50 else AMBER), width=3),
        dbc.Col(kpi_card("Estados", str(estados_n), f"Valor prom: {fmt_pm(total/estados_n)}" if estados_n else "", color=GRAY), width=3),
    ], className="mb-4 g-3")
    children.append(kpi_row)

    funnel_colors = [BLUE, GREEN, AMBER, RED, "#8b5cf6", GRAY, "#ec4899", "#14b8a6"]
    fig = go.Figure(go.Funnel(
        y=funnel["_estado"], x=funnel["Valor"] / 1e6,
        text=[f"${v/1e6:.1f}M" + (f"<br>{p} pedidos" if p else "") for v, p in zip(funnel["Valor"], funnel["Pedidos"])],
        textposition="auto", textinfo="text",
        textfont=dict(size=11, color="white"),
        marker=dict(color=funnel_colors[:len(funnel)], line=dict(color="white", width=1)),
        connector=dict(fillcolor="white", line=dict(color="#e2e8f0", width=1)),
    ))
    fig.update_layout(**fig_layout("Pipeline de Pedidos (millones $)", height=420,
        margin=dict(t=45, b=20, l=80, r=40)))

    children.append(dbc.Row([dbc.Col(graph_png(figure=fig), width=12)], className="mb-3"))

    funnel_table = dash_table.DataTable(
        columns=[{"name": "Estado", "id": "_estado"}, {"name": "Valor", "id": "Valor"},
                 {"name": "%", "id": "%"}, {"name": "Pedidos", "id": "Pedidos"}],
        data=[{"_estado": r["_estado"], "Valor": f"${r['Valor']/1e6:,.1f}M",
               "%": f"{r['%']:.1f}%", "Pedidos": f"{int(r['Pedidos']):,}"}
              for _, r in funnel.iterrows()],
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "6px 12px", "fontSize": "0.8rem", "fontFamily": "Segoe UI, Arial, sans-serif"},
        style_header={"fontWeight": "bold", "backgroundColor": DARKGRAY, "color": "white"},
        style_data_conditional=[
            {"if": {"filter_query": "{_estado} contains 'Comprometido'"},
             "backgroundColor": "#F0FFF0", "fontWeight": "bold"},
        ],
        page_size=20,
    )
    children.append(html.Div([
        html.H6("● Detalle por Estado", className="fw-bold mb-2", style={"color": NAVY, "fontSize": "0.85rem"}),
        funnel_table,
        html.Hr(),
    ]))

    return children


def pagina_heatmap(data):
    n_asesores = data["_vendedor"].nunique()
    n_meses = data["_fecha"].dt.to_period("M").nunique() if "_fecha" in data.columns else 0
    vp = data["_valor"].sum()

    children = [section_title("Heatmap de Rendimiento", f"{n_asesores} asesores × {n_meses} meses | {fmt_pm(vp)} total")]

    heat = data.copy()
    heat["Mes_Anio"] = heat["_fecha"].dt.to_period("M").astype(str)
    pivot = heat.pivot_table(index="_vendedor", columns="Mes_Anio", values="_valor", aggfunc="sum").fillna(0)

    pivot["_total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("_total", ascending=False)
    pivot_display = pivot.drop(columns=["_total"])

    total_row = pd.DataFrame([pivot_display.sum(axis=0).values], columns=pivot_display.columns, index=["TOTAL"])

    pivot_with_total = pd.concat([pivot_display, total_row])

    text_matrix = []
    for idx in pivot_with_total.index:
        row_text = []
        for col in pivot_with_total.columns:
            v = pivot_with_total.loc[idx, col]
            if v == 0:
                row_text.append("")
            else:
                row_text.append(f"${v/1e6:.1f}M")
        text_matrix.append(row_text)

    base_colorscale = [
        [0.0, "#f0f4ff"],
        [0.3, "#93c5fd"],
        [0.6, "#3b82f6"],
        [0.85, "#1e40af"],
        [1.0, "#0c1d5c"],
    ]

    y_labels = list(pivot_with_total.index)
    fig = go.Figure(go.Heatmap(
        z=pivot_with_total.values,
        x=list(pivot_with_total.columns),
        y=y_labels,
        colorscale=base_colorscale,
        text=text_matrix,
        texttemplate="%{text}",
        textfont=dict(size=8, color=DARKGRAY),
        hovertemplate="<b>%{y}</b><br>%{x}: %{text}<extra></extra>",
        xgap=2, ygap=2,
    ))

    chart_h = max(350, min(650, len(y_labels) * 28))
    fig.update_layout(**fig_layout("Valor por Asesor y Mes (millones $)", height=chart_h,
        margin=dict(t=45, b=50, l=100, r=30)))
    fig.update_xaxes(tickangle=-45, tickfont=dict(size=9), side="top")
    fig.update_yaxes(tickfont=dict(size=9, family="Segoe UI"), automargin=True)
    fig.add_hline(y=len(y_labels) - 1.5, line=dict(color=DARKGRAY, width=2, dash="dot"))

    children.append(dbc.Row([dbc.Col(graph_png(figure=fig, id="chart-heatmap"), width=12)], className="mb-3"))

    top_asesores = (
        heat.groupby("_vendedor")["_valor"].sum().sort_values(ascending=False)
    )
    summary_data = []
    for name, val in top_asesores.items():
        pct = val / vp * 100 if vp else 0
        summary_data.append({
            "Asesor": str(name), "Valor Total": fmt_p(val), "% Part": f"{pct:.1f}%",
            "Valor Prom Mensual": fmt_p(val / n_meses) if n_meses else "-",
        })
    summary_table = dash_table.DataTable(
        columns=[{"name": "Asesor", "id": "Asesor"}, {"name": "Valor Total", "id": "Valor Total"},
                 {"name": "% Part", "id": "% Part"}, {"name": "Prom. Mensual", "id": "Valor Prom Mensual"}],
        data=summary_data,
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "5px 10px", "fontSize": "0.78rem", "fontFamily": "Segoe UI, Arial, sans-serif"},
        style_header={"fontWeight": "bold", "backgroundColor": DARKGRAY, "color": "white"},
        page_size=20,
    )
    children.append(html.Div([
        html.H6("● Resumen por Asesor", className="fw-bold mb-2", style={"color": NAVY, "fontSize": "0.85rem"}),
        summary_table,
        html.Hr(),
    ]))

    return children


def pagina_proyeccion(data):
    import numpy as np
    if "_fecha" not in data.columns or data["_fecha"].isna().all():
        return [section_title("Proyeccion de Cierre", "Sin datos"), html.P("No hay fechas disponibles.", className="text-muted")]

    evol = data.groupby(data["_fecha"].dt.to_period("M")).agg(
        Valor=("_valor", "sum"),
    ).reset_index().sort_values("_fecha")
    evol["Periodo"] = range(len(evol))

    if "_valor_sec" in data.columns:
        evol_c = data.groupby(data["_fecha"].dt.to_period("M"))["_valor_sec"].sum().reset_index()
        evol_c = evol_c.rename(columns={"_valor_sec": "Comprometido"}).sort_values("_fecha")
        evol["Comprometido"] = evol_c["Comprometido"].values

    if len(evol) < 3:
        return [section_title("Proyeccion de Cierre", "Datos insuficientes"),
                html.P(f"Se requieren al menos 3 meses. Hay {len(evol)}.", className="text-muted")]

    n_meses = len(evol)
    coef = np.polyfit(evol["Periodo"], evol["Valor"], 1)
    trend = np.poly1d(coef)
    evol["Tendencia"] = trend(evol["Periodo"])

    residuos = evol["Valor"] - evol["Tendencia"]
    std_err = np.std(residuos)

    proy_next = trend(n_meses)
    proy_low = trend(n_meses) - 1.28 * std_err
    proy_high = trend(n_meses) + 1.28 * std_err

    evol["MM3"] = evol["Valor"].rolling(3, min_periods=1).mean()
    growth_rate = (coef[0] / evol["Valor"].mean() * 100) if evol["Valor"].mean() > 0 else 0

    presup_anual = 0
    try:
        from budget import cargar_ptto_company
        from config import RUTA_PRESUPUESTO_COMPANY
        ptto = cargar_ptto_company(str(RUTA_PRESUPUESTO_COMPANY))
        presup_anual = sum(v.get("ppto", 0) for v in ptto.values() if isinstance(v, dict))
    except Exception:
        presup_anual = 0

    proy_annual = trend(len(evol) + 5) if len(evol) >= 6 else proy_next * 12
    ppto_pct = (proy_annual / presup_anual * 100) if presup_anual else 0

    title_sub = f"{n_meses} meses | {'Crecimiento' if growth_rate > 0 else 'Decrecimiento'} {growth_rate:+.1f}%/mes"
    children = [section_title("Proyeccion de Cierre", title_sub)]

    kpi_row = dbc.Row([
        dbc.Col(kpi_card("Proyeccion Prox. Mes", fmt_pm(proy_next), f"Rango: {fmt_pm(proy_low)} – {fmt_pm(proy_high)}",
            color=GREEN if growth_rate > 0 else RED), width=3),
        dbc.Col(kpi_card("Tendencia", f"{growth_rate:+.1f}%/mes", f"R²={np.corrcoef(evol['Periodo'], evol['Valor'])[0,1]**2:.3f}",
            color=BLUE), width=3),
        dbc.Col(kpi_card("Proy. Anual", fmt_pm(proy_annual), f"vs Ppto: {ppto_pct:.1f}%" if presup_anual else "Sin presupuesto anual",
            color=GREEN if ppto_pct >= 85 else AMBER if ppto_pct >= 60 else RED), width=3),
        dbc.Col(kpi_card("Volatilidad", fmt_pm(std_err), f"{std_err/proy_next*100:.1f}% de la proyeccion" if proy_next else "",
            color=GRAY), width=3),
    ], className="mb-4 g-3")
    children.append(kpi_row)

    fig = go.Figure()
    fig.add_trace(go.Bar(x=evol["_fecha"].astype(str), y=evol["Valor"] / 1e6,
        name="Real", marker_color=BLUE, opacity=0.85,
        hovertemplate="<b>%{x}</b><br>Real: $%{y:.1f}M<extra></extra>"))

    if "Comprometido" in evol.columns:
        fig.add_trace(go.Bar(x=evol["_fecha"].astype(str), y=evol["Comprometido"] / 1e6,
            name="Comprometido", marker_color=GREEN, opacity=0.7,
            hovertemplate="<b>%{x}</b><br>Comprometido: $%{y:.1f}M<extra></extra>"))

    fig.add_trace(go.Scatter(x=evol["_fecha"].astype(str), y=evol["Tendencia"] / 1e6,
        name="Tendencia lineal", mode="lines", line=dict(width=2, color=RED, dash="dash"),
        hovertemplate="<b>%{x}</b><br>Tendencia: $%{y:.1f}M<extra></extra>"))

    fig.add_trace(go.Scatter(x=evol["_fecha"].astype(str), y=evol["MM3"] / 1e6,
        name="Media movil 3M", mode="lines+markers", line=dict(width=2, color=AMBER),
        marker=dict(size=4), hovertemplate="<b>%{x}</b><br>MM3: $%{y:.1f}M<extra></extra>"))

    prox_periodo = f"Prox"
    fig.add_trace(go.Scatter(x=[prox_periodo], y=[proy_next / 1e6],
        mode="markers", name="Proyeccion", marker=dict(size=14, color=RED, symbol="diamond"),
        hovertemplate="Proyeccion: $%{y:.1f}M<extra></extra>"))

    fig.add_trace(go.Scatter(x=[prox_periodo, prox_periodo],
        y=[proy_low / 1e6, proy_high / 1e6],
        mode="lines", name="Rango 80%", line=dict(width=6, color="rgba(233, 97, 75, 0.25)"),
        hoverinfo="skip"))

    fig.update_layout(**fig_layout("Proyeccion de Cierre (millones $)", height=420,
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center", font=dict(size=9))))
    fig.update_xaxes(tickangle=-45, tickfont=dict(size=9))
    fig.update_yaxes(title="$ millones", automargin=True)

    children.append(dbc.Row([dbc.Col(graph_png(figure=fig), width=12)], className="mb-3"))

    evol_table = dash_table.DataTable(
        columns=[{"name": "Mes", "id": "Mes"}, {"name": "Valor", "id": "Valor"},
                 {"name": "MM3", "id": "MM3"}, {"name": "Tendencia", "id": "Tendencia"},
                 {"name": "Crec.", "id": "Crec"}],
        data=[{
            "Mes": str(r["_fecha"]),
            "Valor": fmt_pm(r["Valor"]),
            "MM3": fmt_pm(r["MM3"]),
            "Tendencia": fmt_pm(r["Tendencia"]),
            "Crec": f"{((r['Valor']/evol['Valor'].shift(1).iloc[i] - 1)*100):+.1f}%" if i > 0 and evol['Valor'].iloc[i-1] > 0 else "-"
        } for i, (_, r) in enumerate(evol.iterrows())],
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "5px 10px", "fontSize": "0.78rem", "fontFamily": "Segoe UI, Arial, sans-serif"},
        style_header={"fontWeight": "bold", "backgroundColor": DARKGRAY, "color": "white"},
        page_size=20,
    )
    children.append(html.Div([
        html.H6("● Evolucion Mensual", className="fw-bold mb-2", style={"color": NAVY, "fontSize": "0.85rem"}),
        evol_table,
        html.Hr(),
    ]))

    return children
