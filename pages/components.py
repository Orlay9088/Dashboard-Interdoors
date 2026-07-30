import dash_bootstrap_components as dbc
from dash import html
import pandas as pd

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
        paper_bgcolor="#F5F5F0", plot_bgcolor="#F5F5F0",
        font=dict(family="Segoe UI, Arial, sans-serif", color=DARKGRAY, size=12),
        hoverlabel=dict(bgcolor=DARKGRAY, font_color="white", font_size=12),
        xaxis=dict(gridcolor="#e5e7eb", zeroline=False, showline=True, linecolor="#d1d5db",
                   automargin=True, tickfont=dict(size=10)),
        yaxis=dict(gridcolor="#e5e7eb", zeroline=False, showline=True, linecolor="#d1d5db",
                   automargin=True, tickfont=dict(size=10)),
        colorway=[LIGHTBLUE, GOLD, TEAL, CORAL, NAVYBLUE],
    )
)

def fig_layout(title="", height=400, **overrides):
    layout = dict(
        title=dict(text=title, font=dict(size=14, color=DARKGRAY), x=0.02, y=0.97),
        height=height, margin=dict(t=40, b=50, l=80, r=40),
        hovermode="x unified", autosize=True,
    )
    layout.update(PLOTLY_TEMPLATE["layout"])
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

def kpi_card(label, value, sub="", color=None, icon=None):
    if color is None:
        color = DARKGRAY
    if icon is None:
        label_lower = label.lower()
        for key, ico in METRIC_ICONS.items():
            if key in label_lower:
                icon = ico; break
        if icon is None:
            icon = ""
    return html.Div([
        html.Div(style={
            "height": "3px", "background": color,
            "borderRadius": "3px 3px 0 0", "marginBottom": "12px",
        }),
        html.Div([
            html.Span(icon, style={"fontSize": "1.1rem", "marginRight": "6px"}),
            html.Span(label, style={"fontSize": "0.7rem", "textTransform": "uppercase",
                                     "color": GRAY, "fontWeight": "600", "letterSpacing": "0.5px"}),
        ], className="mb-2"),
        html.Div(value, style={"fontSize": "1.6rem", "fontWeight": "bold",
                                "color": color, "lineHeight": "1.2"}),
        html.Div(sub, style={"fontSize": "0.7rem", "color": SLATE, "marginTop": "4px"}) if sub else "",
    ], style={
        "background": "white", "borderRadius": "8px",
        "padding": "14px 16px 16px 16px",
        "boxShadow": "0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)",
        "height": "100%", "transition": "box-shadow 0.2s",
    })

def fmt_p(valor):
    if pd.isna(valor) or valor == 0:
        return "$ 0"
    s = f"{abs(valor):,.0f}".replace(",", ".")
    return f"$ {s}"

def fmt_pm(valor):
    if pd.isna(valor) or valor == 0:
        return "$ 0"
    v = round(valor / 1e6)
    s = f"{abs(v):,}".replace(",", ".")
    return f"$ {s}M"

def apply_filters(data, filters_dict):
    if data.empty:
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
    return d
