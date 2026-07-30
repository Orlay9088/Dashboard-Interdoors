from dash import html, dcc
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
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

# ============================================================
# KAHOOT-STYLE PODIUM with 3D flip cards
# ============================================================
PODIUM_CSS = """
.podium-wrapper { display: flex; justify-content: center; align-items: flex-end; padding: 12px 0; gap: 12px; }
.podium-card { perspective: 700px; cursor: pointer; flex: 1; max-width: 185px; min-height: 260px; transition: transform 0.25s ease, box-shadow 0.25s ease; }
.podium-card:hover { transform: translateY(-6px); }
.podium-card:nth-child(2) { margin-bottom: 28px; }
.podium-card-inner { position: relative; width: 100%; height: 100%; transition: transform 0.5s ease-in-out; transform-style: preserve-3d; }
.podium-card.flipped .podium-card-inner { transform: rotateY(180deg); }
.podium-front, .podium-back { position: absolute; width: 100%; height: 100%; backface-visibility: hidden; border-radius: 12px; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; padding: 14px 10px; box-sizing: border-box; box-shadow: 0 4px 16px rgba(0,0,0,0.08); }
.podium-back { transform: rotateY(180deg); justify-content: center; }
.podium-flip-btn { margin-top: 10px; padding: 5px 14px; border-radius: 20px; border: 1.5px solid rgba(255,255,255,0.4); background: rgba(255,255,255,0.12); color: inherit; cursor: pointer; font-size: 0.65rem; font-weight: bold; transition: background 0.2s; }
.podium-flip-btn:hover { background: rgba(255,255,255,0.25); }
"""

def kahoot_podium(rank_df, flipped=None):
    top3 = rank_df.head(3).reset_index(drop=True)
    bg_colors = [LIGHTBLUE, GOLD, CORAL]
    dk_colors = ["#4A6DB0", "#9A7400", "#C04A38"]
    tx_colors = ["white", DARKGRAY, "white"]
    orders = [1, 0, 2]
    labels = ["#2", "#1", "#3"]
    cards = []

    for i in range(3):
        r = top3.iloc[orders[i]]
        initials = "".join([w[0] for w in str(r["_vendedor"]).split()[:2]]).upper()
        bg, dk, tx = bg_colors[i], dk_colors[i], tx_colors[i]
        flipped_class = "flipped" if flipped is not None and flipped == i else ""

        presup = r.get("% Presup", 0)
        progr = min(100, max(0, presup))

        # ---- FRONT FACE ----
        front = html.Div([
            dmc.Badge(labels[i], variant="filled", color="dark", style={"position": "absolute", "top": "8px", "right": "8px",
                      "fontSize": "0.7rem", "fontWeight": "bold"}),
            dmc.Avatar(initials, radius="xl", size="md", color=dk,
                       style={"marginTop": "6px", "marginBottom": "8px"}),
            html.Div(str(r["_vendedor"]), style={"fontSize": "0.68rem", "fontWeight": "bold", "textAlign": "center",
                     "color": tx, "lineHeight": "1.15", "wordBreak": "break-word", "minHeight": "28px"}),
            html.Div(fmt_pm(r["Valor"]), style={"fontSize": "1.15rem", "fontWeight": "900", "textAlign": "center",
                     "color": tx, "marginBottom": "1px"}),
            html.Div(f"{r.get('% Part', 0):.1f}% participacion", style={"fontSize": "0.65rem", "textAlign": "center",
                     "color": tx, "opacity": "0.85", "marginBottom": "8px"}),
            html.Div([
                html.Div(f"Ppto: {presup:.0f}%" if presup > 0 else "Sin ppto", style={"fontSize": "0.65rem",
                         "fontWeight": "500", "textAlign": "center", "color": tx, "marginBottom": "3px", "opacity": "0.85"}),
                dmc.Progress(value=progr, color="white", size="sm",
                             style={"width": "80%", "margin": "0 auto", "backgroundColor": "rgba(255,255,255,0.2)"}),
            ], style={"width": "100%", "textAlign": "center"}),
        ], className="podium-front", style={"background": bg, "color": tx})

        # ---- BACK FACE ----
        back = html.Div([
            html.Div(str(r["_vendedor"]), style={"fontSize": "0.7rem", "fontWeight": "bold", "textAlign": "center",
                     "color": tx, "marginBottom": "6px", "lineHeight": "1.2"}),
            html.Div(f"Comprometido: {fmt_p(r.get('Comprometido', 0))}", style={"fontSize": "0.62rem", "textAlign": "center",
                     "color": tx, "opacity": "0.9"}),
            html.Div(f"Cumplimiento: {r.get('% Cumpl', 0):.1f}%", style={"fontSize": "0.62rem", "textAlign": "center",
                     "color": tx, "opacity": "0.7", "marginBottom": "8px"}),
            dmc.Progress(value=progr, color="white", size="sm",
                         style={"width": "75%", "margin": "0 auto 4px auto", "backgroundColor": "rgba(255,255,255,0.2)"}),
            html.Div(f"vs Presupuesto: {presup:.0f}%" if presup > 0 else "Sin presupuesto",
                     style={"fontSize": "0.75rem", "fontWeight": "700", "textAlign": "center", "color": tx}),
            html.Div(f"{int(r.get('Pedidos', 0)):,} pedidos | {int(r.get('Clientes', 0))} clientes",
                     style={"fontSize": "0.6rem", "color": tx, "opacity": "0.65", "textAlign": "center", "marginTop": "8px"}),
            html.Button("  Volver  ", className="podium-flip-btn",
                        id={"type": "podium-flip", "index": i},
                        style={"color": tx}),
        ], className="podium-back", style={"background": bg, "color": tx})

        cards.append(html.Div([
            html.Div([front, back], className="podium-card-inner"),
        ], id={"type": "podium-card", "index": i}, className=f"podium-card {flipped_class}"))

    return html.Div([
        dcc.Markdown(f"<style>{PODIUM_CSS}</style>", dangerously_allow_html=True),
        html.Div(cards, className="podium-wrapper"),
    ], style={"margin": "12px 0 20px 0"})
