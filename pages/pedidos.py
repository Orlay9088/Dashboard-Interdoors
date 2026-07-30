from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import plotly.graph_objects as go
import pandas as pd
from pages.components import (
    section_title, kpi_card, fmt_p, fmt_pm, fig_layout,
    NAVY, BLUE, AMBER, GREEN, RED, GRAY, DARKGRAY, GOLD, kahoot_podium,
)


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
        dbc.Col(kpi_card("Construccion", f"{data[data['_canal']=='CNST - CONSTRUCCION']['_valor'].sum()/vp*100:.2f}%" if vp else "0%", "% del total", color=AMBER), width=3),
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

    part_const = (data[data["_canal"] == "CNST - CONSTRUCCION"]["_valor"].sum() / vp * 100) if vp else 0
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
        style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
        page_size=12,
    )

    children.append(dbc.Row([
        dbc.Col(dcc.Graph(figure=fig_evol), width=6),
        dbc.Col(html.Div([
            html.H6("Indicadores Clave", className="fw-bold", style={"color": NAVY}),
            html.Ul([
                html.Li(f"Participacion Construccion: {part_const:.1f}%"),
                html.Li(f"Top 3 clientes concentran: {top3_pct:.1f}%"),
                html.Li(f"Cumplimiento general: {cumpl_val:.1f}%"),
            ], className="small"),
            html.Hr(),
            dcc.Graph(figure=fig_asesores, style={"height": "300px"}),
        ]), width=6),
    ], className="mb-3 g-3"))

    children.append(evol_table)

    children.append(html.Hr())

    return children


def pagina_participacion(data):
    vp = data["_valor"].sum()
    children = [section_title("Participacion Comercial", "Distribucion por canal, asesor y linea")]

    canales = data.groupby("_canal").agg(
        Valor=("_valor", "sum"),
    ).reset_index().sort_values("Valor", ascending=False)
    canales["%"] = (canales["Valor"] / vp * 100).round(2)

    fig_canal = go.Figure(go.Pie(labels=canales["_canal"], values=canales["Valor"],
        hole=0.4, textinfo="label+percent", marker=dict(colors=[BLUE, GREEN, "#f59e0b", RED, "#8b5cf6"])))
    fig_canal.update_layout(**fig_layout("Por Canal", height=380))

    asesores = data.groupby("_vendedor").agg(
        Valor=("_valor", "sum"),
    ).reset_index().sort_values("Valor", ascending=False)
    asesores["%"] = (asesores["Valor"] / vp * 100).round(2)

    fig_ase = go.Figure(go.Bar(x=asesores["_vendedor"].head(10), y=asesores["Valor"].head(10) / 1e6,
        marker_color=BLUE, text=[f"{r:.1f}%" for r in asesores["%"].head(10)], textposition="outside"))
    fig_ase.update_layout(**fig_layout("Top 10 Asesores (millones $)", height=380))
    fig_ase.update_xaxes(tickangle=-45, tickfont=dict(size=9))
    fig_ase.update_yaxes(automargin=True)

    lineas = data.groupby("_linea").agg(
        Valor=("_valor", "sum"),
    ).reset_index().sort_values("Valor", ascending=False)
    lineas["%"] = (lineas["Valor"] / vp * 100).round(2)

    fig_lin = go.Figure(go.Bar(x=lineas["_linea"].head(10), y=lineas["Valor"].head(10) / 1e6,
        marker_color=GREEN, text=[f"{r:.1f}%" for r in lineas["%"].head(10)], textposition="outside"))
    fig_lin.update_layout(**fig_layout("Top 10 Lineas (millones $)", height=380))
    fig_lin.update_xaxes(tickangle=-45, tickfont=dict(size=9))
    fig_lin.update_yaxes(automargin=True)

    children.append(dbc.Row([
        dbc.Col(dcc.Graph(figure=fig_canal), width=4),
        dbc.Col(dcc.Graph(figure=fig_ase), width=4),
        dbc.Col(dcc.Graph(figure=fig_lin), width=4),
    ], className="mb-3 g-3"))

    children.append(html.Hr())

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
        style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
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
        dbc.Col(dcc.Graph(figure=fig, style={"height": "460px"}), width=8),
        dbc.Col(top10, width=4),
    ], className="mb-3 g-3"))
    children.append(table)
    children.append(html.Hr())
    return children


def pagina_ranking(data):
    children = [section_title("Ranking de Asesores", "Comparativa de rendimiento")]

    rank = data[~data["_vendedor"].isin(["VENTAS CORPORATIVAS", "VENTAS INTERNACIONALES"])].groupby("_vendedor").agg(
        Valor=("_valor", "sum"), Pedidos=("_documento", "nunique"),
        Clientes=("_cliente", "nunique"), Comprometido=("_valor_sec", "sum"),
    ).reset_index().sort_values("Valor", ascending=False).reset_index(drop=True)

    tv = rank["Valor"].sum()
    rank["% Part"] = (rank["Valor"] / tv * 100).round(2) if tv else 0

    from budget import cargar_presupuesto_asesores, get_budget_for
    from config import RUTA_PRESUPUESTO_ASESORES
    try:
        budgets = cargar_presupuesto_asesores(str(RUTA_PRESUPUESTO_ASESORES))
    except Exception:
        budgets = {}
    rank["Presupuesto"] = rank["_vendedor"].apply(lambda x: get_budget_for(x, budgets))
    rank["% Presup"] = rank.apply(lambda r: round(r["Valor"] / r["Presupuesto"] * 100, 2) if r["Presupuesto"] > 0 else 0, axis=1)
    rank["% Cumpl"] = rank.apply(lambda r: round(r["Comprometido"] / r["Presupuesto"] * 100, 2) if r["Presupuesto"] > 0 else 0, axis=1)
    rank.insert(0, "#", range(1, len(rank) + 1))

    # Kahoot-style podium with flip cards
    top3 = rank.head(3)
    children.append(kahoot_podium(top3))

    presup_total = rank["Presupuesto"].sum()

    # Summary KPI row
    presup_total = rank["Presupuesto"].sum()
    presup_pct = (tv / presup_total * 100) if presup_total else 0
    presup_color = GREEN if presup_pct >= 100 else AMBER if presup_pct >= 70 else RED
    kpi_row = dbc.Row([
        dbc.Col(kpi_card("Asesores Activos", f"{len(rank)}", "", color=BLUE), width=3),
        dbc.Col(kpi_card("Valor Total", fmt_p(tv), fmt_pm(tv), color=NAVY), width=3),
        dbc.Col(kpi_card("vs Presupuesto", f"{presup_pct:.1f}%", f"Meta: {fmt_pm(presup_total)}" if presup_total else "Sin datos", color=presup_color), width=3),
        dbc.Col(kpi_card("Cumpl. Prom.", f"{rank['% Cumpl'].mean():.1f}%", f"Top 3: {rank.head(3)['% Part'].sum():.1f}%", color=GREEN if rank['% Cumpl'].mean() > 50 else AMBER), width=3),
    ], className="mb-4 g-3")
    children.append(kpi_row)

    # Bar chart - all sellers sorted desc
    fig = go.Figure()
    top_show = rank.head(10)
    fig.add_trace(go.Bar(
        x=top_show["Valor"] / 1e6,
        y=top_show["_vendedor"],
        orientation="h",
        marker=dict(
            color=[BLUE if i > 0 else "#FFD700" for i in range(len(top_show))],
            line=dict(color="white", width=1),
        ),
        text=[fmt_pm(v) for v in top_show["Valor"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Valor: %{text}<br>Participacion: %{customdata}%<extra></extra>",
        customdata=top_show["% Part"].tolist(),
    ))
    fig.update_layout(**fig_layout("Top 10 Asesores por Valor (millones $)", height=380,
        margin=dict(t=40, b=20, l=20, r=40)))
    fig.update_xaxes(title="$ millones", showgrid=True, gridcolor="#e2e8f0")
    fig.update_yaxes(automargin=True, tickfont=dict(size=10))

    children.append(dbc.Row([dbc.Col(dcc.Graph(figure=fig), width=12)], className="mb-3"))

    # Ranking table
    table = dash_table.DataTable(
        columns=[{"name": c, "id": c} for c in ["#", "_vendedor", "Valor_total", "% Part", "% Presup", "Pedidos", "Clientes", "% Cumpl"]],
        data=[{"#": r["#"], "_vendedor": r["_vendedor"], "Valor_total": fmt_p(r["Valor"]),
               "% Part": f"{r['% Part']:.1f}%",
               "% Presup": f"{r['% Presup']:.1f}%" if r["Presupuesto"] > 0 else "-",
               "Pedidos": f"{int(r['Pedidos']):,}",
               "Clientes": f"{int(r['Clientes'])}", "% Cumpl": f"{r['% Cumpl']:.1f}%"}
              for _, r in rank.iterrows()],
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "0.75rem"},
        style_header={"fontWeight": "bold", "backgroundColor": "#f8fafc"},
        style_data_conditional=[
            {"if": {"filter_query": "{#} = 1", "column_id": "#"},
             "backgroundColor": "#FFF8E1", "fontWeight": "bold"},
            {"if": {"filter_query": "{#} = 2", "column_id": "#"},
             "backgroundColor": "#F5F5F5", "fontWeight": "bold"},
            {"if": {"filter_query": "{#} = 3", "column_id": "#"},
             "backgroundColor": "#FFF0E0", "fontWeight": "bold"},
        ],
        page_size=15,
        sort_action="native",
    )
    children.append(table)
    children.append(html.Hr())
    return children


def pagina_embudo(data):
    children = [section_title("Embudo de Pedidos", "Pipeline de estados")]

    funnel = data.groupby("_estado").agg(
        Valor=("_valor", "sum"), Pedidos=("_documento", "nunique"),
    ).reset_index().sort_values("Valor", ascending=False)

    fig = go.Figure(go.Funnel(
        y=funnel["_estado"], x=funnel["Valor"] / 1e6,
        text=[f"${v/1e6:.1f}M<br>{p} pedidos" for v, p in zip(funnel["Valor"], funnel["Pedidos"])],
        textposition="inside", textinfo="text",
        marker=dict(color=[BLUE, GREEN, AMBER, RED, GRAY][:len(funnel)]),
    ))
    fig.update_layout(**fig_layout("Pipeline de Pedidos (millones $)", height=380))

    total = funnel["Valor"].sum()
    comp = funnel[funnel["_estado"].str.contains("Comprometido", na=False)]["Valor"].sum()
    rate = comp / total * 100 if total else 0

    children.append(dbc.Row([dbc.Col(dcc.Graph(figure=fig), width=12)], className="mb-3"))
    children.append(html.Div([
        html.P([html.Strong(f"Tasa de cierre: {rate:.1f}% del valor total comprometido.")], className="mb-2"),
    ]))
    children.append(html.Hr())
    return children


def pagina_heatmap(data):
    children = [section_title("Heatmap de Rendimiento", "Actividad por asesor y mes")]

    heat = data.copy()
    heat["Mes_Anio"] = heat["_fecha"].dt.to_period("M").astype(str)
    pivot = heat.pivot_table(index="_vendedor", columns="Mes_Anio", values="_valor", aggfunc="sum").fillna(0)

    fig = go.Figure(go.Heatmap(
        z=pivot.values, x=list(pivot.columns), y=list(pivot.index),
        colorscale="Blues", text=[[f"${v/1e6:.1f}M" for v in row] for row in pivot.values],
        texttemplate="%{text}", textfont={"size": 9},
    ))
    fig.update_layout(**fig_layout("Valor por Asesor y Mes (millones $)", height=420))
    fig.update_xaxes(tickangle=-45)

    children.append(dbc.Row([dbc.Col(dcc.Graph(figure=fig), width=12)], className="mb-3"))
    children.append(html.Hr())
    return children


def pagina_proyeccion(data):
    import numpy as np
    children = [section_title("Proyeccion de Cierre", "Tendencia y estimacion")]

    evol = data.groupby(data["_fecha"].dt.to_period("M")).agg(
        Valor=("_valor", "sum"),
    ).reset_index()
    evol["Periodo"] = range(len(evol))

    if len(evol) >= 3:
        coef = np.polyfit(evol["Periodo"], evol["Valor"], 1)
        trend = np.poly1d(coef)
        evol["Tendencia"] = trend(evol["Periodo"])
        proy = trend(len(evol))

        fig = go.Figure()
        fig.add_trace(go.Bar(x=evol["_fecha"].astype(str), y=evol["Valor"] / 1e6, name="Real",
            marker_color=BLUE))
        fig.add_trace(go.Scatter(x=evol["_fecha"].astype(str), y=evol["Tendencia"] / 1e6,
            name="Tendencia", mode="lines", line=dict(width=3, color=RED, dash="dash")))
        fig.update_layout(**fig_layout("Proyeccion de Cierre (millones $)", height=380))
        fig.update_xaxes(tickangle=-45)

        children.append(dbc.Row([dbc.Col(dcc.Graph(figure=fig), width=12)], className="mb-3"))
        children.append(html.Div([
            html.H5(f"Proyeccion: {fmt_p(proy)}", className="fw-bold", style={"color": NAVY}),
        ], className="text-center mb-4"))
    else:
        children.append(html.P("Se requieren al menos 3 meses de datos.", className="text-muted"))

    return children
