import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from config import CARPETA_DASHBOARD, ARCHIVO_BASE, CARPETA_ENTRADA

st.set_page_config(page_title="Dashboard Ejecutivo - Pedidos", layout="wide", page_icon="")

# ─── BOOTSTRAP 5 CDN ───
st.markdown("""<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
""", unsafe_allow_html=True)

# ─── PALETA DE COLORES ───
NAVY = "#1e3a5f"
BLUE = "#3b82f6"
AMBER = "#f59e0b"
GREEN = "#10b981"
RED = "#ef4444"
GRAY = "#64748b"
LIGHT_BG = "#f1f5f9"
CARD_BG = "#ffffff"

COLORS = px.colors.qualitative.Set2

# ─── CSS ───
st.markdown(f"""
<style>
    .block-container {{ padding-top: 1.2rem; padding-bottom: 1rem; }}

    /* KPI Cards - Bootstrap card + custom */
    .kpi-card {{
        border: 1px solid #e8ecf1 !important;
        border-radius: 16px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.02);
        transition: all 0.2s ease;
        background: white;
    }}
    .kpi-card:hover {{
        box-shadow: 0 8px 25px rgba(30,58,95,0.10);
        transform: translateY(-2px);
        border-color: #cdd5e0 !important;
    }}
    .kpi-icon {{ font-size: 1.6rem; line-height: 1; }}
    .kpi-label {{ font-size: 0.7rem; color: {GRAY}; letter-spacing: 0.4px; text-transform: uppercase; font-weight: 600; }}
    .kpi-value {{ font-size: 1.6rem; font-weight: 700; color: {NAVY}; line-height: 1.2; }}
    .kpi-sub {{ font-size: 0.7rem; color: {GRAY}; }}

    /* Sidebar */
    .sidebar-title {{ font-weight: 700; color: {NAVY}; font-size: 1.1rem; }}
    .sidebar-sub {{ font-size: 0.7rem; color: {GRAY}; }}

    /* Navigation buttons */
    .st-key-nav_resumen button, .st-key-nav_participacion button,
    .st-key-nav_pareto button, .st-key-nav_ranking button,
    .st-key-nav_embudo button, .st-key-nav_heatmap button,
    .st-key-nav_proyeccion button {{
        border: 1px solid #e2e8f0 !important;
        border-radius: 10px !important;
        padding: 8px 12px !important;
        font-size: 0.85rem !important;
        transition: all 0.15s ease;
        background: white !important;
        color: #334155 !important;
        text-align: left !important;
    }}
    .st-key-nav_resumen button:hover, .st-key-nav_participacion button:hover,
    .st-key-nav_pareto button:hover, .st-key-nav_ranking button:hover,
    .st-key-nav_embudo button:hover, .st-key-nav_heatmap button:hover,
    .st-key-nav_proyeccion button:hover {{
        background: #f1f5f9 !important;
        border-color: #cbd5e1 !important;
    }}
    .st-key-nav_resumen button:focus, .st-key-nav_participacion button:focus,
    .st-key-nav_pareto button:focus, .st-key-nav_ranking button:focus,
    .st-key-nav_embudo button:focus, .st-key-nav_heatmap button:focus,
    .st-key-nav_proyeccion button:focus {{
        box-shadow: none !important;
    }}

    /* Section headers */
    .section-title {{
        font-size: 1.3rem; font-weight: 700; color: {NAVY};
        padding-bottom: 0.3rem;
        border-bottom: 3px solid {BLUE}; display: inline-block;
        margin-bottom: 0.2rem;
    }}
    .section-sub {{ font-size: 0.8rem; color: {GRAY}; margin-bottom: 1rem; }}

    /* Info box */
    .info-box {{
        background: #f8fafc; border-radius: 12px; padding: 14px 16px;
        border: 1px solid #e2e8f0; font-size: 0.8rem;
    }}

    /* Hide Streamlit elements */
    #MainMenu {{ visibility: hidden; }}
    footer {{ display: none; }}
    .stDeployButton {{ display: none; }}
    /* Radio inline fix */
    div[data-testid="stRadio"] > div {{ gap: 6px; }}
    div[data-testid="stRadio"] label {{
        border: 1px solid #e2e8f0; border-radius: 20px;
        padding: 4px 16px; font-size: 0.8rem;
    }}
    div[data-testid="stRadio"] label[data-baseweb="tag"] {{
        background: {NAVY}; color: white; border-color: {NAVY};
    }}
    /* Filter labels smaller */
    .stSelectbox label, .stDateInput label {{ font-size: 0.75rem !important; }}
</style>
""", unsafe_allow_html=True)

# ─── CARGA DE DATOS ───
@st.cache_data(ttl=120)
def cargar_base():
    if ARCHIVO_BASE.exists():
        df = pd.read_parquet(ARCHIVO_BASE)
    else:
        return pd.DataFrame()
    for c in ["Cant. pedida", "Cant. pendiente", "Cant. comprom.",
              "Valor pendiente subtotal", "V.COMPROMETIDO"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    if "Fecha" in df.columns:
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    return df

df = cargar_base()

if df.empty:
    st.warning("No hay datos. Procesa un archivo SIESA con `python main.py`")
    st.stop()

# ─── SIDEBAR ───
with st.sidebar:
    st.markdown(f'<div class="sidebar-title"> Dashboard Ejecutivo</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sidebar-sub">Pedidos SIESA · {df["Nro documento"].nunique():,} pedidos</div>',
                unsafe_allow_html=True)

    st.markdown("### Filtros")
    fechas = df["Fecha"].dropna()
    rango = None
    if not fechas.empty:
        f_min = fechas.min().date()
        f_max = fechas.max().date()
        rango = st.date_input("Periodo", [f_min, f_max], label_visibility="collapsed")

    asesor_opts = ["Todos"] + sorted(df["Nombre vendedor"].dropna().unique())
    canal_opts = ["Todos"] + sorted(df["CANAL DISTRIBUCION"].dropna().unique())
    estado_opts = ["Todos"] + sorted(df["Estado movto."].dropna().unique())

    col1, col2 = st.columns(2)
    with col1:
        asesor_sel = st.selectbox("Asesor", asesor_opts, label_visibility="collapsed")
    with col2:
        canal_sel = st.selectbox("Canal", canal_opts, label_visibility="collapsed")

    estado_sel = st.selectbox("Estado", estado_opts, label_visibility="collapsed")

    d = df.copy()
    if rango and len(rango) == 2:
        d = d[(d["Fecha"].dt.date >= rango[0]) & (d["Fecha"].dt.date <= rango[1])]
    if asesor_sel != "Todos":
        d = d[d["Nombre vendedor"] == asesor_sel]
    if canal_sel != "Todos":
        d = d[d["CANAL DISTRIBUCION"] == canal_sel]
    if estado_sel != "Todos":
        d = d[d["Estado movto."] == estado_sel]

    st.markdown("---")
    st.markdown("### Navegacion")

    menu_items = [
        " Resumen Ejecutivo",
        " Participacion",
        " Pareto",
        " Ranking",
        " Embudo",
        " Heatmap",
        " Proyeccion",
    ]
    menu_keys = ["resumen", "participacion", "pareto", "ranking", "embudo", "heatmap", "proyeccion"]

    if "pagina" not in st.session_state:
        st.session_state.pagina = "resumen"

    for key, label in zip(menu_keys, menu_items):
        active = st.session_state.pagina == key
        cls = "nav-item nav-active" if active else "nav-item"
        if st.button(label, key=f"nav_{key}", use_container_width=True,
                     type="primary" if active else "secondary"):
            st.session_state.pagina = key
            st.rerun()

    st.markdown("---")
    st.markdown("###  Cargar archivo SIESA")

    archivo_subido = st.file_uploader(
        "Selecciona archivo .xlsx de SIESA",
        type=["xlsx"],
        label_visibility="collapsed",
    )

    if archivo_subido is not None:
        ruta_temp = CARPETA_ENTRADA / archivo_subido.name
        with open(ruta_temp, "wb") as f:
            f.write(archivo_subido.getbuffer())

        if st.button(" Procesar archivo", type="primary", use_container_width=True):
            with st.spinner("Procesando..."):
                try:
                    sys.path.insert(0, str(Path(__file__).parent))
                    from main import procesar
                    procesar(str(ruta_temp))
                    st.success(" Procesado correctamente")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    st.markdown("---")
    st.markdown(f'<div class="info-box card bg-light border-0">'
                f'<div class="card-body p-2"><b>Base Maestra</b><br>{len(df):,} registros<br>',
                unsafe_allow_html=True)
    if ARCHIVO_BASE.exists():
        st.markdown(
            f'<span style="color:{GREEN}">Actualizada: '
            f'{datetime.fromtimestamp(ARCHIVO_BASE.stat().st_mtime).strftime("%Y-%m-%d %H:%M")}</span>'
            f'<br>Mostrando: {len(d):,} registros</div></div>',
            unsafe_allow_html=True)

# ─── FUNCIONES DE GRAFICOS ───
def fig_layout(title="", height=400, **overrides):
    layout = dict(
        title=dict(text=title, font=dict(size=14, color=NAVY), x=0.02, y=0.97),
        height=height, margin=dict(t=36, b=40, l=10, r=10),
        paper_bgcolor="white", plot_bgcolor="white",
        hovermode="x unified",
        font=dict(color="#334155"),
        xaxis=dict(gridcolor="#f1f5f9", zeroline=False),
        yaxis=dict(gridcolor="#f1f5f9", zeroline=False),
    )
    layout.update(overrides)
    return layout

def kpi_card(icon, label, value, sub=""):
    return f"""<div class="card kpi-card p-3 text-center" style="border:none">
        <div class="kpi-icon mb-1">{icon}</div>
        <div class="kpi-label mb-1">{label}</div>
        <div class="kpi-value">{value}</div>
        {f'<div class="kpi-sub mt-1">{sub}</div>' if sub else ''}
    </div>"""

# ─── PAGINA: RESUMEN EJECUTIVO ───
def pagina_resumen(data):
    st.markdown(f'<div class="section-title"> Resumen Ejecutivo</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-sub">Indicadores principales y tendencia general</div>',
                unsafe_allow_html=True)

    vp = data["Valor pendiente subtotal"].sum()
    vc = data["V.COMPROMETIDO"].sum()
    total_pedidos = data["Nro documento"].nunique()
    total_clientes = data["Razon social cliente factura"].nunique()
    cant_pedida = data["Cant. pedida"].sum()
    cant_pendiente = data["Cant. pendiente"].sum()
    cumpl = (vc / vp * 100) if vp else 0

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(kpi_card("", "Valor Total", f"${vp:,.0f}",
                             f"${vp/1e6:.1f}M"), unsafe_allow_html=True)
    with k2:
        st.markdown(kpi_card("", "Pedidos", f"{total_pedidos:,}",
                             f"{cant_pedida:,.0f} unidades"), unsafe_allow_html=True)
    with k3:
        st.markdown(kpi_card("", "Clientes Activos", f"{total_clientes}",
                             f"{data['Nombre vendedor'].nunique()} asesores"), unsafe_allow_html=True)
    with k4:
        pct_pend = (cant_pendiente / cant_pedida * 100) if cant_pedida else 0
        st.markdown(kpi_card("", "Valor Pendiente", f"${vp:,.0f}",
                             f"{pct_pend:.1f}% del pedido"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Evolucion mensual + tarjetas de cumplimiento
    col_left, col_right = st.columns([1.6, 1])

    with col_left:
        evol = data.groupby(data["Fecha"].dt.to_period("M")).agg(
            Valor_pendiente=("Valor pendiente subtotal", "sum"),
            Comprometido=("V.COMPROMETIDO", "sum"),
            Pedidos=("Nro documento", "nunique"),
        ).reset_index()
        evol["Fecha"] = evol["Fecha"].astype(str)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=evol["Fecha"], y=evol["Valor_pendiente"] / 1e6,
            mode="lines+markers", name="Valor Pendiente",
            line=dict(width=3, color=BLUE),
            marker=dict(size=6, color=BLUE),
        ))
        fig.add_trace(go.Scatter(
            x=evol["Fecha"], y=evol["Comprometido"] / 1e6,
            mode="lines+markers", name="Comprometido",
            line=dict(width=3, color=GREEN),
            marker=dict(size=6, color=GREEN),
        ))
        fig.update_layout(**fig_layout("Evolucion Mensual (millones $)", height=380))
        fig.update_layout(legend=dict(orientation="h", y=1.1, x=0.7))
        fig.update_xaxes(tickangle=-45)
        st.plotly_chart(fig, width='stretch')

    with col_right:
        # Acumulado por ano
        st.markdown("#### Acumulado por Ano")
        anual = data.groupby("Anio").agg(
            Valor=("Valor pendiente subtotal", "sum"),
            Comprometido=("V.COMPROMETIDO", "sum"),
        ).reset_index()
        anual["% Cumpl"] = (anual["Comprometido"] / anual["Valor"] * 100).round(1)
        for _, row in anual.iterrows():
            col_a, col_b, col_c = st.columns([1, 1.2, 1])
            col_a.markdown(f"**{int(row['Anio'])}**")
            col_b.markdown(f"${row['Valor']/1e6:.1f}M")
            pct = row["% Cumpl"]
            badge = f'<span class="badge bg-success">{pct}%</span>' if pct > 20 else \
                    f'<span class="badge bg-light text-secondary">{pct}%</span>'
            col_c.markdown(badge, unsafe_allow_html=True)

        st.markdown("---")

        # KPIs secundarios
        st.markdown("#### Indicadores Clave")
        part_const = (data[data["CANAL DISTRIBUCION"] == "CNST - CONSTRUCCION"]["Valor pendiente subtotal"].sum() / vp * 100) if vp else 0
        top3 = data.groupby("Razon social cliente factura")["Valor pendiente subtotal"].sum().sort_values(ascending=False)
        top3_pct = (top3.iloc[:3].sum() / vp * 100) if vp else 0

        st.metric("% Canal Construccion", f"{part_const:.1f}%")
        st.metric("Top 3 Clientes concentran", f"{top3_pct:.1f}%")
        st.metric("% Cumplimiento", f"{cumpl:.1f}%")

# ─── PAGINA: PARTICIPACION ───
def pagina_participacion(data):
    st.markdown(f'<div class="section-title"> Participacion Comercial</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-sub">Distribucion del valor por asesor, canal y estructura</div>',
                unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        # Participacion por Asesor
        asesor = data.groupby("Nombre vendedor").agg(
            Valor=("Valor pendiente subtotal", "sum")
        ).reset_index().sort_values("Valor", ascending=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=asesor["Valor"] / 1e6, y=asesor["Nombre vendedor"],
            orientation="h", marker_color=COLORS,
            text=[f"${v/1e6:.1f}M" for v in asesor["Valor"]],
            textposition="outside",
        ))
        fig.update_layout(**fig_layout("Por Asesor (millones $)", height=360))
        fig.update_xaxes(title="$ millones")
        st.plotly_chart(fig, width='stretch')

    with col2:
        # Participacion por Canal
        canal = data.groupby("CANAL DISTRIBUCION").agg(
            Valor=("Valor pendiente subtotal", "sum")
        ).reset_index()
        canal = canal[canal["Valor"] > 0]
        fig = px.pie(
            canal, values="Valor", names="CANAL DISTRIBUCION",
            hole=0.45, color_discrete_sequence=COLORS,
        )
        fig.update_traces(textinfo="label+percent", textposition="outside")
        fig.update_layout(**fig_layout("Por Canal", height=360))
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, width='stretch')

    col3, col4 = st.columns(2)

    with col3:
        # Participacion por Estructura (LINEA)
        linea = data.groupby("LINEA").agg(
            Valor=("Valor pendiente subtotal", "sum")
        ).reset_index().sort_values("Valor", ascending=True)
        linea = linea[linea["Valor"] > 0].tail(15)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=linea["Valor"] / 1e6, y=linea["LINEA"],
            orientation="h", marker_color=BLUE,
            text=[f"${v/1e6:.1f}M" for v in linea["Valor"]],
            textposition="outside",
        ))
        fig.update_layout(**fig_layout("Por Linea de Producto (millones $)", height=400))
        fig.update_xaxes(title="$ millones")
        st.plotly_chart(fig, width='stretch')

    with col4:
        # Tabla resumen de participacion
        st.markdown("#### Resumen de Participacion")
        resumen = data.groupby("CANAL DISTRIBUCION").agg(
            Valor=("Valor pendiente subtotal", "sum"),
            Comprometido=("V.COMPROMETIDO", "sum"),
            Pedidos=("Nro documento", "nunique"),
            Clientes=("Razon social cliente factura", "nunique"),
        ).reset_index()
        resumen["% Participacion"] = (resumen["Valor"] / resumen["Valor"].sum() * 100).round(1)
        resumen = resumen.sort_values("Valor", ascending=False)
        resumen_display = resumen.copy()
        resumen_display["Valor"] = resumen_display["Valor"].apply(lambda x: f"${x:,.0f}")
        resumen_display["Comprometido"] = resumen_display["Comprometido"].apply(lambda x: f"${x:,.0f}")
        resumen_display["% Participacion"] = resumen_display["% Participacion"].apply(lambda x: f"{x}%")
        st.dataframe(resumen_display, width='stretch', hide_index=True)

# ─── PAGINA: CLIENTES ───
def pagina_clientes(data):
    st.markdown(f'<div class="section-title"> Pareto de Clientes</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-sub">Analisis de concentracion por cliente y por canal</div>',
                unsafe_allow_html=True)

    # Selector de canal independiente del filtro del sidebar
    canales_pareto = ["TODOS LOS CANALES"] + sorted(data["CANAL DISTRIBUCION"].dropna().unique())
    canal_pareto = st.radio(
        "Canal", canales_pareto, horizontal=True,
        key="canal_pareto",
        label_visibility="collapsed",
    )

    if canal_pareto == "TODOS LOS CANALES":
        filtro = data
        titulo = "Pareto General"
    else:
        filtro = data[data["CANAL DISTRIBUCION"] == canal_pareto]
        titulo = f"Pareto - {canal_pareto}"

    if filtro.empty:
        st.info("No hay datos para este canal con los filtros aplicados.")
        return

    vp_total = filtro["Valor pendiente subtotal"].sum()
    pg = filtro.groupby("Razon social cliente factura").agg(
        Valor=("Valor pendiente subtotal", "sum"),
        Comprometido=("V.COMPROMETIDO", "sum"),
        Pedidos=("Nro documento", "nunique"),
        Cantidad=("Cant. pedida", "sum"),
    ).reset_index().sort_values("Valor", ascending=False).reset_index(drop=True)

    if pg.empty:
        st.info("No hay datos de clientes para esta seleccion.")
        return

    pg["% Participacion"] = (pg["Valor"] / vp_total * 100).round(2)
    pg["% Acumulado"] = pg["% Participacion"].cumsum()
    pg.insert(0, "Ranking", range(1, len(pg) + 1))

    top_n = st.slider("Numero de clientes a mostrar", 5, min(50, len(pg)), 15, key="top_pareto")

    col1, col2 = st.columns([1.6, 1])

    with col1:
        data_top = pg.head(top_n)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=data_top["Razon social cliente factura"],
            y=data_top["Valor"],
            marker_color=BLUE, name="Valor Pendiente",
            text=[f"${v/1e6:.1f}M" for v in data_top["Valor"]],
            textposition="outside",
        ))
        fig.add_trace(go.Scatter(
            x=data_top["Razon social cliente factura"],
            y=data_top["% Acumulado"], name="% Acumulado",
            yaxis="y2", marker_color=RED, mode="lines+markers",
            line=dict(width=3),
        ))
        fig.add_hline(y=80, line_dash="dash", line_color=AMBER,
                      annotation_text="80%", annotation_position="left")
        fig.update_layout(**fig_layout(titulo, height=420,
            yaxis=dict(title="$", gridcolor="#f1f5f9", zeroline=False),
            yaxis2=dict(title="%", overlaying="y", side="right", range=[0, 105]),
        ))
        fig.update_xaxes(tickangle=-45)
        st.plotly_chart(fig, width='stretch')

    with col2:
        st.markdown("#### Top 10 Clientes")
        for i, (_, r) in enumerate(pg.head(10).iterrows()):
            st.markdown(
                f"**{i+1}. {r['Razon social cliente factura'][:45]}**  \n"
                f"${r['Valor']:,.0f} | {r['% Participacion']:.1f}% acum: {r['% Acumulado']:.1f}%"
            )

        st.markdown("---")
        top3_sum = pg.head(3)["% Participacion"].sum()
        hasta_80 = (pg["% Acumulado"] <= 80).sum()
        st.metric("Top 3 concentran", f"{top3_sum:.1f}%")
        st.metric("Clientes hasta 80%", hasta_80)
        st.metric("Total Clientes", len(pg))

    st.markdown("---")
    st.dataframe(
        pg.style.format({
            "Valor": "${:,.0f}", "Comprometido": "${:,.0f}",
            "Cantidad": "{:,.0f}", "% Participacion": "{:.2f}%",
            "% Acumulado": "{:.2f}%",
        }),
        width='stretch', hide_index=True,
    )

    # ─── COMPARATIVO: Pareto por cada canal ───
    st.markdown("---")
    st.markdown(f'<div class="section-title"> Comparativo por Canal</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-sub">Top 5 clientes de cada canal</div>', unsafe_allow_html=True)

    canales = data["CANAL DISTRIBUCION"].dropna().unique()
    tabs_canal = st.tabs(sorted(canales))

    for tab, canal in zip(tabs_canal, sorted(canales)):
        with tab:
            d_canal = data[data["CANAL DISTRIBUCION"] == canal]
            vp_canal = d_canal["Valor pendiente subtotal"].sum()
            if vp_canal == 0:
                st.caption("Sin datos")
                continue
            pc = d_canal.groupby("Razon social cliente factura").agg(
                Valor=("Valor pendiente subtotal", "sum"),
            ).reset_index().sort_values("Valor", ascending=False).head(10)
            pc["%"] = (pc["Valor"] / vp_canal * 100).round(1)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=pc["Razon social cliente factura"],
                y=pc["Valor"],
                marker_color=COLORS[0],
                text=[f"${v/1e6:.1f}M" for v in pc["Valor"]],
                textposition="outside",
            ))
            fig.add_trace(go.Scatter(
                x=pc["Razon social cliente factura"],
                y=pc["%"], name="% Participacion",
                yaxis="y2", marker_color=RED, mode="lines+markers",
                line=dict(width=3),
            ))
            fig.update_layout(**fig_layout(f"Top 10 - {canal}", height=350,
                yaxis=dict(gridcolor="#f1f5f9", zeroline=False, title="$"),
                yaxis2=dict(title="%", overlaying="y", side="right", range=[0, 105]),
            ))
            fig.update_xaxes(tickangle=-45)
            st.plotly_chart(fig, width='stretch')

            st.dataframe(
                pc.style.format({"Valor": "${:,.0f}", "%": "{:.1f}%"}),
                width='stretch', hide_index=True,
            )

# ─── PAGINA: RANKING ───
def pagina_ranking(data):
    st.markdown(f'<div class="section-title"> Ranking de Asesores</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-sub">Rendimiento general y participacion en Construccion</div>',
                unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    # Ranking General
    rank = data.groupby("Nombre vendedor").agg(
        Valor=("Valor pendiente subtotal", "sum"),
        Comprometido=("V.COMPROMETIDO", "sum"),
        Pedidos=("Nro documento", "nunique"),
        Clientes=("Razon social cliente factura", "nunique"),
    ).reset_index()
    rank["% Cumpl"] = (rank["Comprometido"] / rank["Valor"] * 100).round(1)
    rank = rank.sort_values("Valor", ascending=True)

    with col1:
        fig = go.Figure()
        colors_rank = [GREEN if v > 20 else AMBER for v in rank["% Cumpl"]]
        fig.add_trace(go.Bar(
            x=rank["Valor"] / 1e6, y=rank["Nombre vendedor"],
            orientation="h", marker_color=COLORS[:len(rank)],
            text=[f"${v/1e6:.1f}M" for v in rank["Valor"]],
            textposition="outside",
        ))
        fig.update_layout(**fig_layout("Ranking General - Valor Total (millones $)", height=360))
        fig.update_xaxes(title="$ millones")
        st.plotly_chart(fig, width='stretch')

    with col2:
        st.markdown("#### Resumen por Asesor")
        rank_display = rank.sort_values("Valor", ascending=False).copy()
        rank_display["Valor"] = rank_display["Valor"].apply(lambda x: f"${x:,.0f}")
        rank_display["Comprometido"] = rank_display["Comprometido"].apply(lambda x: f"${x:,.0f}")
        rank_display["% Cumpl"] = rank_display["% Cumpl"].apply(lambda x: f"{x}%")
        st.dataframe(rank_display, width='stretch', hide_index=True)

    st.markdown("---")

    # Ranking Canal Construccion
    st.markdown(f'<div class="section-title"> Ranking Canal Construccion</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-sub">Participacion de cada asesor en el canal CNST - CONSTRUCCION con variacion</div>',
                unsafe_allow_html=True)

    cnst = data[data["CANAL DISTRIBUCION"] == "CNST - CONSTRUCCION"].copy()
    vp_cnst = cnst["Valor pendiente subtotal"].sum()

    if vp_cnst > 0 and not cnst.empty:
        cnst_rank = cnst.groupby("Nombre vendedor").agg(
            Valor=("Valor pendiente subtotal", "sum"),
            Comprometido=("V.COMPROMETIDO", "sum"),
        ).reset_index()
        cnst_rank["% Participacion"] = (cnst_rank["Valor"] / vp_cnst * 100).round(1)
        cnst_rank["% Cumpl"] = (cnst_rank["Comprometido"] / cnst_rank["Valor"] * 100).round(1)
        cnst_rank = cnst_rank.sort_values("% Participacion", ascending=False).reset_index(drop=True)

        # Variacion vs mes anterior
        mes_actual = cnst["Fecha"].max()
        if pd.notna(mes_actual):
            inicio_mes = mes_actual.replace(day=1)
            mes_anterior = inicio_mes - timedelta(days=1)
            inicio_anterior = mes_anterior.replace(day=1)

            cnst_actual = cnst[cnst["Fecha"] >= inicio_mes]
            cnst_anterior = cnst[(cnst["Fecha"] >= inicio_anterior) & (cnst["Fecha"] < inicio_mes)]

            if not cnst_anterior.empty:
                actual_agg = cnst_actual.groupby("Nombre vendedor")["Valor pendiente subtotal"].sum().reset_index()
                ant_agg = cnst_anterior.groupby("Nombre vendedor")["Valor pendiente subtotal"].sum().reset_index()
                actual_agg.columns = ["Nombre vendedor", "Valor_actual"]
                ant_agg.columns = ["Nombre vendedor", "Valor_anterior"]
                var_df = actual_agg.merge(ant_agg, on="Nombre vendedor", how="outer").fillna(0)
                var_df["Var%"] = var_df.apply(
                    lambda r: ((r["Valor_actual"] - r["Valor_anterior"]) / r["Valor_anterior"] * 100)
                    if r["Valor_anterior"] > 0 else (100 if r["Valor_actual"] > 0 else 0),
                    axis=1,
                )
                cnst_rank = cnst_rank.merge(var_df[["Nombre vendedor", "Var%"]], on="Nombre vendedor", how="left")

        col_a, col_b = st.columns([1.3, 1])

        with col_a:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=cnst_rank["Valor"] / 1e6, y=cnst_rank["Nombre vendedor"],
                orientation="h",
                marker_color=BLUE,
                text=[f"${v/1e6:.1f}M" for v in cnst_rank["Valor"]],
                textposition="outside",
            ))
            fig.update_layout(**fig_layout("Valor en Construccion (millones $)", height=320))
            fig.update_xaxes(title="$ millones")
            st.plotly_chart(fig, width='stretch')

        with col_b:
            st.markdown("#### Detalle Construccion")
            display_df = cnst_rank.copy()
            display_df["Valor"] = display_df["Valor"].apply(lambda x: f"${x:,.0f}")
            display_df["% Participacion"] = display_df["% Participacion"].apply(lambda x: f"{x}%")
            if "Var%" in display_df.columns:
                display_df["Variacion"] = display_df["Var%"].apply(
                    lambda x: f' {x:+.1f}%' if pd.notna(x) else " N/A"
                )
            st.dataframe(display_df, width='stretch', hide_index=True)
    else:
        st.info("No hay datos del canal Construccion con los filtros actuales.")

# ─── PAGINA: EMBUDO ───
def pagina_embudo(data):
    st.markdown(f'<div class="section-title"> Embudo de Pedidos</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-sub">Pipeline: desde elaboracion hasta comprometido</div>',
                unsafe_allow_html=True)

    estado_map = {
        "En elaboracion": "1. En Elaboracion",
        "Aprobado": "2. Aprobado",
        "Retenido": "3. Retenido",
        "Comprometido parcial": "4. Comprometido Parcial",
        "Comprometido": "5. Comprometido",
    }
    funnel = data.groupby("Estado movto.").agg(
        Valor=("Valor pendiente subtotal", "sum"),
        Pedidos=("Nro documento", "nunique"),
        Cantidad=("Cant. pedida", "sum"),
    ).reset_index()
    funnel["Stage"] = funnel["Estado movto."].map(estado_map).fillna(funnel["Estado movto."])
    stage_order = ["1. En Elaboracion", "2. Aprobado", "3. Retenido",
                   "4. Comprometido Parcial", "5. Comprometido"]
    funnel["Stage_order"] = funnel["Stage"].apply(
        lambda x: stage_order.index(x) if x in stage_order else 99
    )
    funnel = funnel.sort_values("Stage_order")

    col1, col2 = st.columns([1.6, 1.2])

    with col1:
        fig = go.Figure()
        fig.add_trace(go.Funnel(
            y=funnel["Stage"],
            x=funnel["Valor"],
            text=[f"${v/1e6:.2f}M" for v in funnel["Valor"]],
            textposition="inside",
            textinfo="value+percent previous",
            marker=dict(color=[BLUE, AMBER, RED, GREEN, "#10b981"]),
            connector=dict(line=dict(color="#e2e8f0", width=2)),
        ))
        fig.update_layout(**fig_layout("Embudo de Valor (USD)", height=450))
        st.plotly_chart(fig, width='stretch')

    with col2:
        st.markdown("#### Desglose por Estado")
        for _, row in funnel.iterrows():
            st.markdown(
                f"**{row['Estado movto.']}**  \n"
                f"${row['Valor']:,.0f} | {row['Pedidos']:,} pedidos | {row['Cantidad']:,.0f} unidades"
            )
            st.markdown("---")

        st.markdown("#### Indicadores")
        total_valor = funnel["Valor"].sum()
        comprometido = funnel[funnel["Estado movto."].str.contains("Comprometido", na=False)]["Valor"].sum()
        en_proceso = funnel[funnel["Estado movto."].isin(["En elaboracion", "Aprobado"])]["Valor"].sum()
        retenido = funnel[funnel["Estado movto."] == "Retenido"]["Valor"].sum()

        st.metric("En Proceso", f"${en_proceso:,.0f}", f"{en_proceso/total_valor*100:.1f}%" if total_valor else "0%")
        st.metric("Comprometido", f"${comprometido:,.0f}", f"{comprometido/total_valor*100:.1f}%" if total_valor else "0%")
        st.metric("Retenido", f"${retenido:,.0f}", f"{retenido/total_valor*100:.1f}%" if total_valor else "0%")

# ─── PAGINA: HEATMAP ───
def pagina_heatmap(data):
    st.markdown(f'<div class="section-title"> Heatmap de Rendimiento</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-sub">Valor pendiente por asesor y mes (intensidad de color)</div>',
                unsafe_allow_html=True)

    heat = data.copy()
    heat["Mes_Anio"] = heat["Fecha"].dt.to_period("M").astype(str)
    pivot = heat.pivot_table(
        index="Nombre vendedor",
        columns="Mes_Anio",
        values="Valor pendiente subtotal",
        aggfunc="sum",
    ).fillna(0)

    meses = sorted(pivot.columns)
    pivot = pivot[meses]

    if not pivot.empty:
        col1, col2 = st.columns([1.6, 1])

        with col1:
            fig = go.Figure()
            fig.add_trace(go.Heatmap(
                z=pivot.values / 1e6,
                x=pivot.columns,
                y=pivot.index,
                colorscale="Blues",
                text=[["${:.1f}M".format(v) for v in row] for row in pivot.values / 1e6],
                texttemplate="%{text}",
                textfont=dict(size=9),
                hovertemplate="Asesor: %{y}<br>Mes: %{x}<br>Valor: $%{z:.1f}M<extra></extra>",
            ))
            fig.update_layout(**fig_layout("Valor Pendiente por Asesor x Mes (millones $)", height=400,
                xaxis=dict(gridcolor="#f1f5f9", zeroline=False, tickangle=-45, side="top"),
                yaxis=dict(gridcolor="#f1f5f9", zeroline=False, autorange="reversed"),
            ))
            fig.update_traces(colorbar=dict(title="$ Millones", len=0.8))
            st.plotly_chart(fig, width='stretch')

        with col2:
            st.markdown("#### Totales por Asesor")
            total_asesor = pivot.sum(axis=1).sort_values(ascending=False)
            for asesor, total in total_asesor.items():
                meses_con_datos = (pivot.loc[asesor] > 0).sum()
                st.markdown(
                    f"**{asesor}**  \n"
                    f"${total:,.0f} | {meses_con_datos} meses activo"
                )
                st.markdown("---")

            st.markdown("#### Periodo mas activo")
            max_col = pivot.max().idxmax()
            max_val = pivot[max_col].max()
            max_asesor = pivot[max_col].idxmax()
            st.markdown(f"**{max_col}**  \n{max_asesor}: ${max_val:,.0f}")
    else:
        st.info("No hay suficientes datos para generar el heatmap.")

# ─── PAGINA: PROYECCION ───
def pagina_proyeccion(data):
    st.markdown(f'<div class="section-title"> Proyeccion de Cierre</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-sub">Estimacion de cierre del mes basada en tendencia historica</div>',
                unsafe_allow_html=True)

    evol = data.groupby(data["Fecha"].dt.to_period("M")).agg(
        Valor=("Valor pendiente subtotal", "sum"),
    ).reset_index()
    evol["Periodo"] = range(len(evol))
    evol["Fecha_str"] = evol["Fecha"].astype(str)

    if len(evol) >= 3:
        X = evol["Periodo"].values.reshape(-1, 1)
        y = evol["Valor"].values
        coef = np.polyfit(evol["Periodo"], evol["Valor"], 1)
        trend = np.poly1d(coef)

        evol["Tendencia"] = trend(evol["Periodo"])

        # Proximos 3 periodos
        ultimo_periodo = evol["Periodo"].max()
        futuros = []
        for i in range(1, 4):
            p = ultimo_periodo + i
            futuros.append({
                "Periodo": p,
                "Valor": trend(p),
                "Label": f"Proy. +{i}",
            })
        fut_df = pd.DataFrame(futuros)

        # Fecha actual
        hoy = data["Fecha"].max()
        mes_actual = hoy.to_period("M")
        datos_mes_actual = evol[evol["Fecha"] == mes_actual]
        valor_actual = datos_mes_actual["Valor"].sum() if not datos_mes_actual.empty else 0
        proy_cierre = trend(ultimo_periodo)
        dif = proy_cierre - valor_actual if not datos_mes_actual.empty else 0

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Valor Actual del Mes", f"${valor_actual:,.0f}")
        with col2:
            st.metric("Proyeccion Cierre", f"${proy_cierre:,.0f}",
                      f"{dif:+,.0f}" if dif != 0 else "")
        with col3:
            pct_proy = (proy_cierre / valor_actual * 100 - 100) if valor_actual else 0
            st.metric("Brecha vs Proyeccion", f"{pct_proy:+.1f}%")

        st.markdown("---")

        col_left, col_right = st.columns([1.6, 1])

        with col_left:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=evol["Fecha_str"], y=evol["Valor"] / 1e6,
                mode="lines+markers", name="Valor Real",
                line=dict(width=3, color=BLUE),
                marker=dict(size=8, color=BLUE),
            ))
            fig.add_trace(go.Scatter(
                x=evol["Fecha_str"], y=evol["Tendencia"] / 1e6,
                mode="lines", name="Tendencia Lineal",
                line=dict(width=2, dash="dash", color=RED),
            ))
            fig.add_trace(go.Scatter(
                x=fut_df["Label"], y=fut_df["Valor"] / 1e6,
                mode="markers+lines", name="Proyeccion",
                line=dict(width=2, dash="dot", color=GREEN),
                marker=dict(size=10, color=GREEN, symbol="diamond"),
            ))
            fig.update_layout(
                **fig_layout("Proyeccion de Valor Pendiente (millones $)", height=420),
                legend=dict(orientation="h", y=1.1),
            )
            fig.update_xaxes(tickangle=-45)
            st.plotly_chart(fig, width='stretch')

        with col_right:
            st.markdown("#### Pronostico")
            for _, r in fut_df.iterrows():
                st.metric(
                    r["Label"],
                    f"${r['Valor']:,.0f}",
                    f"${r['Valor']/1e6:.1f}M",
                )
            st.markdown("---")
            st.markdown("#### Datos de Tendencia")
            st.dataframe(
                evol.tail(12)[["Fecha_str", "Valor", "Tendencia"]]
                .style.format({"Valor": "${:,.0f}", "Tendencia": "${:,.0f}"}),
                width='stretch', hide_index=True,
            )
    else:
        st.info("Se necesitan al menos 3 meses de datos historicos para generar una proyeccion.")

# ─── RENDER PAGINA ───
if st.session_state.pagina == "resumen":
    pagina_resumen(d)
elif st.session_state.pagina == "participacion":
    pagina_participacion(d)
elif st.session_state.pagina == "pareto":
    pagina_clientes(d)
elif st.session_state.pagina == "ranking":
    pagina_ranking(d)
elif st.session_state.pagina == "embudo":
    pagina_embudo(d)
elif st.session_state.pagina == "heatmap":
    pagina_heatmap(d)
elif st.session_state.pagina == "proyeccion":
    pagina_proyeccion(d)

# ─── FOOTER ───
st.markdown("---")
st.markdown(
    f'<div style="display:flex;justify-content:space-between;color:{GRAY};font-size:0.75rem">'
    f'<span>Base Maestra: {len(df):,} registros | Mostrando: {len(d):,}</span>'
    f'<span>{datetime.now().strftime("%Y-%m-%d %H:%M")}</span>'
    f'</div>',
    unsafe_allow_html=True,
)
