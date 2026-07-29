import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash import html, dcc
import pandas as pd

NAVY = "#1e3a5f"
BLUE = "#3b82f6"
AMBER = "#f59e0b"
GREEN = "#10b981"
RED = "#ef4444"
GRAY = "#64748b"

HEX_TO_RGB = {
    "#1e3a5f": (30, 58, 95), "#3b82f6": (59, 130, 246),
    "#10b981": (16, 185, 129), "#f59e0b": (245, 158, 11),
    "#ef4444": (239, 68, 68), "#64748b": (100, 116, 139),
}


def rgba(color, alpha):
    rgb = HEX_TO_RGB.get(color)
    if rgb:
        return f"rgba({rgb[0]},{rgb[1]},{rgb[2]},{alpha})"
    return color


PLOTLY_TEMPLATE = dict(
    layout=dict(
        paper_bgcolor="#f8fafc", plot_bgcolor="#f8fafc",
        font=dict(family="Segoe UI, Arial, sans-serif", color="#334155"),
        hoverlabel=dict(bgcolor=NAVY, font_color="white", font_size=12),
        xaxis=dict(gridcolor="#e2e8f0", zeroline=False, showline=True, linecolor="#cbd5e1"),
        yaxis=dict(gridcolor="#e2e8f0", zeroline=False, showline=True, linecolor="#cbd5e1"),
    )
)


def fig_layout(title="", height=400, **overrides):
    layout = dict(
        title=dict(text=title, font=dict(size=14, color=NAVY), x=0.02, y=0.97),
        height=height, margin=dict(t=36, b=40, l=10, r=10),
        hovermode="x unified",
    )
    layout.update(PLOTLY_TEMPLATE["layout"])
    layout.update(overrides)
    return layout


def section_title(title, sub=""):
    return html.Div([
        html.H5(title, className="fw-bold m-0", style={"color": NAVY}),
        html.P(sub, className="text-muted small m-0") if sub else "",
    ], className="mb-3")


def kpi_card(label, value, sub=""):
    return dmc.Card([
        dmc.CardSection([
            html.Div(label, className="text-center text-uppercase small text-muted fw-semibold"),
            html.Div(value, className="text-center fw-bold", style={"fontSize": "1.5rem", "color": NAVY}),
            html.Div(sub, className="text-center small text-muted mt-1") if sub else "",
        ]),
    ], withBorder=True, shadow="sm", padding="lg", radius="md", className="h-100")


def fmt_p(valor):
    if pd.isna(valor) or valor == 0:
        return "$ 0"
    s = f"{abs(valor):,.0f}".replace(",", ".")
    return f"$ {s}"


def fmt_pm(valor):
    if pd.isna(valor) or valor == 0:
        return "$ 0"
    v = valor / 1e6
    s = f"{abs(v):,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"$ {s}M"


def build_podium(rank_df, title, value_col, pct_col, extra_col=None):
    top3 = rank_df.head(3).reset_index(drop=True)
    labels = ["#1", "#2", "#3"]
    colors = ["#FFD700", "#C0C0C0", "#CD7F32"]
    badges = ["#B8860B", "#696969", "#8B4513"]
    heights = ["180px", "140px", "110px"]
    offsets = ["0px", "40px", "70px"]
    cols = []
    for i in range(3):
        r = top3.iloc[i]
        cols.append(dbc.Col([
            html.Div([
                html.Div(labels[i], style={
                    "fontSize": "1.6rem", "fontWeight": "bold", "color": "white",
                    "background": badges[i], "borderRadius": "50%", "width": "44px",
                    "height": "44px", "display": "flex", "alignItems": "center",
                    "justifyContent": "center", "margin": "0 auto 4px auto",
                }),
                html.Div(r["_vendedor"], className="fw-bold small",
                         style={"wordBreak": "break-word", "lineHeight": "1.1"}),
                html.Div(fmt_p(r[value_col]), className="fw-bold",
                         style={"color": NAVY, "fontSize": "1rem"}),
                html.Div(f"{r[pct_col]:.1f}%", className="text-muted small"),
            ], style={
                "background": f"linear-gradient(180deg, {colors[i]}22, white)",
                "borderTop": f"4px solid {colors[i]}",
                "borderRadius": "12px 12px 0 0", "height": heights[i],
                "marginTop": offsets[i], "display": "flex", "flexDirection": "column",
                "alignItems": "center", "justifyContent": "flex-start",
                "padding": "0.75rem 0.5rem", "textAlign": "center",
            })
        ], width=4, className="px-1"))
    return html.Div([
        html.H6(title, className="fw-bold text-center mb-2", style={"color": NAVY}),
        dbc.Row([cols[1], cols[0], cols[2]], className="g-0", style={"alignItems": "flex-end"}),
    ], className="mb-3")


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
