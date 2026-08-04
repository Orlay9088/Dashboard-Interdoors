from dash import html, dcc
from copy import deepcopy
import dash_mantine_components as dmc
import pandas as pd

def graph_png(figure, className=None, style=None, id=None):
    props = dict(figure=figure, className=className, style=style,
        config={
            "displayModeBar": True,
            "modeBarButtonsToAdd": ["toImage"],
            "toImageButtonOptions": {
                "format": "png",
                "filename": "grafico_interdoors",
                "height": 900,
                "width": 1600,
                "scale": 2,
            },
            "displaylogo": False,
        })
    if id is not None:
        props["id"] = id
    return dcc.Graph(**props)

# ============================================================
# INTERDOORS BRAND COLORS (Manual de Marca ID 2025)
# ============================================================
BLACK = "#000000"
GOLD = "#F3C615"
DARKGRAY = "#323232"
NAVYBLUE = "#323955"
LIGHTBLUE = "#6985D6"
TEAL = "#0C8E82"
CORAL = "#E9614B"

NAVY = DARKGRAY
BLUE = LIGHTBLUE
GREEN = TEAL
AMBER = GOLD
RED = CORAL
GRAY = "#6B7280"
SLATE = "#9CA3AF"

HEX_TO_RGB = {
    DARKGRAY: (50, 50, 50), LIGHTBLUE: (105, 133, 214),
    GOLD: (243, 198, 21), TEAL: (12, 142, 130),
    CORAL: (233, 97, 75), NAVYBLUE: (50, 57, 85),
    BLACK: (0, 0, 0), "#6B7280": (107, 114, 128),
}

METRIC_ICONS = {
    "valor": "$", "pedidos": "#", "clientes": "",
    "pendiente": "", "promedio": "", "cumplimiento": "",
    "construccion": "", "stock": "", "productos": "",
    "existencia": "", "comprometido": "", "ventas": "",
    "facturas": "", "ticket": "", "margen": "",
    "rendimiento": "", "ranking": "", "proyeccion": "",
    "bodega": "", "linea": "",
}

def rgba(color, alpha):
    rgb = HEX_TO_RGB.get(color)
    if rgb:
        return f"rgba({rgb[0]},{rgb[1]},{rgb[2]},{alpha})"
    return color

PLOTLY_TEMPLATE = dict(
    layout=dict(
        paper_bgcolor="#F7F7F7", plot_bgcolor="#F7F7F7",
        font=dict(family="'Inter', 'Segoe UI', Arial, sans-serif", color=DARKGRAY, size=12),
        hoverlabel=dict(bgcolor=DARKGRAY, font_color="white", font_size=11),
        xaxis=dict(gridcolor="#f3f4f6", zeroline=False, showline=True, linecolor="#e5e7eb",
                   automargin=True, tickfont=dict(size=9)),
        yaxis=dict(gridcolor="#f3f4f6", zeroline=False, showline=True, linecolor="#e5e7eb",
                   automargin=True, tickfont=dict(size=9)),
        colorway=[BLUE, GOLD, GREEN, RED, NAVYBLUE],
    )
)

def fig_layout(title="", height=400, **overrides):
    layout = {}
    layout.update(deepcopy(PLOTLY_TEMPLATE["layout"]))
    layout.update({
        "title": dict(text=title, font=dict(size=14, color=DARKGRAY), x=0.02, y=0.97),
        "height": height, "margin": dict(t=40, b=50, l=80, r=40),
        "hovermode": "x unified", "autosize": True,
    })
    layout.update(overrides)
    return layout

def section_title(title, sub=""):
    return html.Div([
        html.Div(style={
            "width": "4px", "height": "24px", "backgroundColor": GOLD,
            "borderRadius": "2px", "display": "inline-block",
            "verticalAlign": "middle", "marginRight": "10px",
        }),
        html.Div([
            html.H5(title, className="fw-bold m-0", style={"color": DARKGRAY, "display": "inline"}),
            html.P(sub, className="small m-0 mt-1", style={"color": GRAY}) if sub else "",
        ], style={"display": "inline-block", "verticalAlign": "middle"}),
    ], className="mb-4")

def kpi_card(label, value, sub="", color=None, icon=None, delta=None):
    if color is None:
        color = DARKGRAY
    if icon is None:
        label_lower = label.lower()
        for key, ico in METRIC_ICONS.items():
            if key in label_lower:
                icon = ico; break
        if icon is None:
            icon = ""
    delta_html = ""
    if delta is not None and isinstance(delta, (int, float)) and delta != 0:
        arrow = "▲" if delta > 0 else "▼"
        dcolor = GREEN if delta > 0 else RED
        delta_html = html.Span(f" {arrow} {abs(delta):.1f}%", style={
            "fontSize": "0.65rem", "color": dcolor, "fontWeight": "600",
            "marginLeft": "6px", "verticalAlign": "middle",
        })
    return html.Div([
        html.Div(style={
            "height": "3px", "background": color,
            "borderRadius": "0", "marginBottom": "14px",
        }),
        html.Div([
            html.Span(icon, style={"fontSize": "0.9rem", "marginRight": "6px"}),
            html.Span(label, style={"fontSize": "0.65rem", "textTransform": "uppercase",
                                     "color": GRAY, "fontWeight": "600", "letterSpacing": "1px"}),
        ], className="mb-2"),
        html.Div([
            html.Span(value, style={"fontSize": "1.4rem", "fontWeight": "800",
                                     "color": color, "lineHeight": "1.2",
                                     "fontFamily": "'Gilroy', 'Inter', 'Segoe UI', Arial, sans-serif"}),
            delta_html,
        ]),
        html.Div(sub, style={"fontSize": "0.65rem", "color": SLATE, "marginTop": "4px"}) if sub else "",
    ], style={
        "background": "white", "borderRadius": "12px",
        "padding": "14px 16px 16px 16px",
        "boxShadow": "0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)",
        "height": "100%", "transition": "box-shadow 0.2s",
    })

def safe_int(valor):
    import numpy as np
    if pd.isna(valor) or np.isinf(valor):
        return 0
    try:
        return int(valor)
    except Exception:
        return 0

def fmt_p(valor):
    if pd.isna(valor):
        return "$ 0"
    neg = valor < 0
    s = f"{abs(valor):,.0f}".replace(",", ".")
    return f"-$ {s}" if neg else f"$ {s}"

def fmt_pm(valor):
    if pd.isna(valor):
        return "$ 0"
    neg = valor < 0
    v = round(abs(valor) / 1e6)
    s = f"{v:,}".replace(",", ".")
    return f"-$ {s}M" if neg else f"$ {s}M"

def apply_filters(data, filters_dict):
    if data.empty:
        return data
    active = False
    for key, val in filters_dict.items():
        if key == "rango" and len(val) == 2 and val[0] and val[1]:
            active = True; break
        if val and val != "Todos":
            active = True; break
    if not active:
        return data
    d = data.copy()
    rango = filters_dict.get("rango", [])
    if len(rango) == 2 and rango[0] and rango[1]:
        try:
            inicio = pd.Timestamp(rango[0]).date()
            fin = pd.Timestamp(rango[1]).date()
            mask = d["_fecha"].notna() & (d["_fecha"].dt.date >= inicio) & (d["_fecha"].dt.date <= fin)
            d = d[mask]
        except (ValueError, TypeError, AttributeError):
            pass
    asesor = filters_dict.get("asesor", "Todos")
    if asesor and asesor != "Todos" and "_vendedor" in d.columns:
        d = d[d["_vendedor"] == asesor]
    canal = filters_dict.get("canal", "Todos")
    if canal and canal != "Todos" and "_canal" in d.columns:
        d = d[d["_canal"] == canal]
    estado = filters_dict.get("estado", "Todos")
    if estado and estado != "Todos" and "_estado" in d.columns:
        d = d[d["_estado"] == estado]
    linea = filters_dict.get("linea", "Todos")
    if linea and linea != "Todos" and "_linea" in d.columns:
        d = d[d["_linea"] == linea]
    sublinea = filters_dict.get("sublinea", "Todos")
    if sublinea and sublinea != "Todos" and "_sublinea" in d.columns:
        d = d[d["_sublinea"] == sublinea]
    return d

# ============================================================
# KAHOOT-STYLE PODIUM with 3D flip cards
# ============================================================
def kahoot_podium(rank_df):
    top3 = rank_df.head(3).reset_index(drop=True)
    n = len(top3)
    if n == 0:
        return None
    colors = {
        0: {"bg": GOLD, "dk": "#9A7400", "tx": DARKGRAY, "ring": GOLD, "medal": "🥇", "label": "#1"},
        1: {"bg": "#6B7280", "dk": "#4B5563", "tx": "white", "ring": "#6B7280", "medal": "🥈", "label": "#2"},
        2: {"bg": NAVYBLUE, "dk": "#232840", "tx": "white", "ring": NAVYBLUE, "medal": "🥉", "label": "#3"},
    }
    heights = {0: "240px", 1: "200px", 2: "188px"}

    if n == 1: order_map = [(0, 0)]
    elif n == 2: order_map = [(0, 1), (1, 0)]
    else: order_map = [(0, 1), (1, 0), (2, 2)]
    cards = []
    for display_i, data_i in order_map:
        r = top3.iloc[data_i]
        initials = "".join([w[0] for w in str(r["_vendedor"]).split()[:2]]).upper()
        c = colors[display_i]
        is_top = data_i == 0

        presup = r.get("% Presup", 0)
        progr = min(100, max(0, presup))
        progr_color = GREEN if progr >= 100 else GOLD if progr >= 70 else RED
        has_ppto = r.get("Presupuesto", 0) > 0

        card = html.Div([
            html.Div([
                html.Span(c["medal"], style={"fontSize": "1rem", "marginRight": "4px"}),
                html.Span(c["label"], style={
                    "fontSize": "0.6rem", "fontWeight": "800", "color": c["tx"],
                    "textTransform": "uppercase", "letterSpacing": "0.5px", "opacity": "0.8",
                }),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "8px"}),
            dmc.Avatar(initials, radius="xl", size="lg", style={
                "backgroundColor": c["dk"], "color": c["tx"],
                "marginBottom": "10px", "border": f"2px solid {c['ring']}",
                "boxShadow": f"0 0 16px {c['ring']}55" if is_top else "none",
            }),
            html.Div(str(r["_vendedor"]), style={
                "fontSize": "0.68rem", "fontWeight": "700", "textAlign": "center",
                "color": c["tx"], "lineHeight": "1.25", "marginBottom": "4px",
                "minHeight": "30px", "maxWidth": "175px", "overflow": "hidden", "textOverflow": "ellipsis",
            }),
            html.Div(fmt_pm(r["Valor"]), style={
                "fontSize": "1.3rem", "fontWeight": "900", "textAlign": "center",
                "color": c["tx"], "marginBottom": "2px",
                "fontFamily": "'Gilroy', 'Inter', 'Segoe UI', Arial, sans-serif",
            }),
            html.Div(f"{r.get('% Part', 0):.1f}% del total", style={
                "fontSize": "0.65rem", "textAlign": "center", "color": c["tx"],
                "opacity": "0.85", "marginBottom": "6px",
            }),
            html.Div(f"Meta: {fmt_pm(r.get('Presupuesto', 0))}" if has_ppto else "Sin meta", style={
                "fontSize": "0.65rem", "fontWeight": "600", "textAlign": "center",
                "color": c["tx"], "marginBottom": "5px", "opacity": "0.85",
            }),
            html.Div(style={
                "width": "75%", "height": "3px", "borderRadius": "2px",
                "backgroundColor": "rgba(0,0,0,0.15)" if c.get("tx") == "white" else "rgba(255,255,255,0.2)",
                "margin": "0 auto 4px",
                "overflow": "hidden",
            }, children=[
                html.Div(style={
                    "width": f"{min(progr, 100)}%", "height": "100%",
                    "borderRadius": "2px",
                    "backgroundColor": c["tx"],
                    "opacity": "0.7",
                })
            ]),
            html.Div(f"Alcance: {presup:.0f}%" if has_ppto else "", style={
                "fontSize": "0.62rem", "fontWeight": "700", "textAlign": "center",
                "color": c["tx"], "marginBottom": "4px", "opacity": "0.85",
            }),
            html.Div(f"Comprometido: {r.get('% Cumpl', 0):.1f}%" if has_ppto else "Sin datos", style={
                "fontSize": "0.65rem", "fontWeight": "600", "textAlign": "center",
                "color": c["tx"], "opacity": "0.85",
            }),
        ], style={
            "position": "relative",
            "width": "200px", "minHeight": heights[display_i],
            "background": c["bg"], "color": c["tx"],
            "borderRadius": "14px",
            "padding": "16px 12px 14px 12px",
            "display": "flex", "flexDirection": "column",
            "alignItems": "center",
            "boxShadow": f"0 8px 32px rgba(243,198,21,0.3)" if is_top else "0 4px 16px rgba(0,0,0,0.12)",
            "transition": "transform 0.2s, box-shadow 0.2s",
            "cursor": "default",
        })
        cards.append(card)

    return html.Div([
        html.Div([
            html.Span("● ", style={"color": GOLD, "fontSize": "0.85rem"}),
            html.Span("RANKING DE ASESORES", style={
                "fontSize": "0.7rem", "fontWeight": "700", "color": GRAY,
                "letterSpacing": "2px", "textTransform": "uppercase",
            }),
        ], style={"textAlign": "center", "marginBottom": "16px"}),
        html.Div(cards, style={
            "display": "flex", "justifyContent": "center",
            "alignItems": "flex-end", "gap": "16px",
            "padding": "8px 0 4px 0",
        }),
    ], style={"margin": "12px 0 24px 0"})

