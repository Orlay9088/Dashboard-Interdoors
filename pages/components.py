from dash import html, dcc
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
.podium-wrapper { display: flex; justify-content: center; align-items: flex-end; padding: 20px 0; gap: 16px; }
.podium-card { perspective: 800px; cursor: pointer; flex: 1; max-width: 220px; min-height: 340px; }
.podium-card:nth-child(2) { margin-bottom: 40px; }
.podium-card-inner { position: relative; width: 100%; height: 100%; transition: transform 0.6s cubic-bezier(0.4,0,0.2,1); transform-style: preserve-3d; }
.podium-card.flipped .podium-card-inner { transform: rotateY(180deg); }
.podium-front, .podium-back { position: absolute; width: 100%; height: 100%; backface-visibility: hidden; border-radius: 14px; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 18px 12px; box-sizing: border-box; }
.podium-back { transform: rotateY(180deg); }
.podium-avatar { width: 52px; height: 52px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 1.1rem; color: white; margin-bottom: 10px; }
.podium-badge { font-size: 1.3rem; font-weight: 900; margin: 6px 0; letter-spacing: 1px; }
.podium-progress { width: 80%; height: 8px; border-radius: 4px; background: rgba(255,255,255,0.3); margin: 8px 0; overflow: hidden; }
.podium-progress-bar { height: 100%; border-radius: 4px; background: rgba(255,255,255,0.8); transition: width 0.8s ease; }
.podium-flip-btn { margin-top: 12px; padding: 6px 16px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.5); background: rgba(255,255,255,0.15); color: inherit; cursor: pointer; font-size: 0.7rem; font-weight: bold; }
"""

def kahoot_podium(rank_df, flipped=None):
    from dash import html
    top3 = rank_df.head(3).reset_index(drop=True)
    colors_bg = [LIGHTBLUE, GOLD, CORAL]   # #2, #1, #3 (left, center, right)
    colors_dk = ["#4A6DB0", "#B8860B", "#C04A38"]
    colors_tx = ["white", DARKGRAY, "white"]
    orders = [1, 0, 2]
    labels = ["#2", "#1", "#3"]

    cards = []
    for i in range(3):
        r = top3.iloc[orders[i]]
        initials = "".join([w[0] for w in str(r["_vendedor"]).split()[:2]]).upper()
        color = colors_bg[i]
        dk = colors_dk[i]
        tx = colors_tx[i]
        flipped_class = "flipped" if flipped is not None and flipped == i else ""

        # Budget progress
        presup = r.get("% Presup", 0)
        progress_width = min(100, max(0, presup))

        front = html.Div([
            html.Div(initials, className="podium-avatar", style={"background": dk}),
            html.Div(str(r["_vendedor"]), style={"fontSize": "0.7rem", "fontWeight": "bold", "textAlign": "center",
                    "color": tx, "wordBreak": "break-word", "lineHeight": "1.2", "marginBottom": "6px"}),
            html.Div(fmt_pm(r["Valor"]), style={"fontSize": "1.3rem", "fontWeight": "900", "color": tx, "marginBottom": "2px"}),
            html.Div(f"{r.get('% Part', 0):.1f}% participacion", style={"fontSize": "0.65rem", "color": tx, "opacity": "0.85"}),
            html.Div(labels[i], className="podium-badge", style={"color": tx, "opacity": "0.6"}),
        ], className="podium-front", style={"background": color})

        back = html.Div([
            html.Div(str(r["_vendedor"]), style={"fontSize": "0.72rem", "fontWeight": "bold", "textAlign": "center",
                    "color": tx, "wordBreak": "break-word", "marginBottom": "8px"}),
            html.Div([
                html.Div(f"Comprometido: {fmt_p(r.get('Comprometido', 0))}", style={"fontSize": "0.62rem", "color": tx, "opacity": "0.9"}),
                html.Div(f"({r.get('% Cumpl', 0):.1f}% cumplimiento)", style={"fontSize": "0.6rem", "color": tx, "opacity": "0.7"}),
            ], style={"marginBottom": "8px", "textAlign": "center"}),
            html.Div([
                html.Div(f"vs Presupuesto:", style={"fontSize": "0.6rem", "color": tx, "opacity": "0.7", "textAlign": "center"}),
                html.Div([
                    html.Div(className="podium-progress-bar",
                             style={"width": f"{progress_width}%", "background": "rgba(255,255,255,0.9)"}),
                ], className="podium-progress"),
                html.Div(f"{presup:.0f}%" if presup > 0 else "Sin presupuesto",
                         style={"fontSize": "0.75rem", "fontWeight": "bold", "color": tx, "textAlign": "center"}),
            ], style={"marginBottom": "8px"}),
            html.Div(f"{int(r.get('Pedidos', 0)):,} pedidos | {int(r.get('Clientes', 0))} clientes",
                     style={"fontSize": "0.58rem", "color": tx, "opacity": "0.7", "textAlign": "center"}),
            html.Button("  Volver  ", className="podium-flip-btn",
                        id={"type": "podium-flip", "index": i},
                        style={"color": tx}),
        ], className="podium-back", style={"background": color})

        card_id = {"type": "podium-card", "index": i}
        cards.append(html.Div([
            html.Div([front, back], className="podium-card-inner"),
        ], id=card_id, className=f"podium-card {flipped_class}"))

    rank_title = f"   Podio {rank_df.attrs.get('title', 'de Asesores')}" if hasattr(rank_df, 'attrs') else "   Podio de Asesores"
    return html.Div([
        dcc.Markdown(f"<style>{PODIUM_CSS}</style>", dangerously_allow_html=True),
        html.Div(cards, className="podium-wrapper"),
    ], style={"margin": "16px 0 24px 0"})
