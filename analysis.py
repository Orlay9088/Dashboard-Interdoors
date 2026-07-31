import pandas as pd
import numpy as np
import requests
import time
from dash import html
from pages.components import fmt_p, fmt_pm, DARKGRAY, BLUE, GOLD, TEAL


def _company_context():
    return "Interdoors S.A.S., empresa colombiana con 30+ anos en carpinteria arquitectonica (puertas, muebles de cocina, banos, closets). Reportas a gerencia general con datos del ERP SIESA Enterprise."


def _build_projection_data(tipo, page, data):
    """Compute time-series and projection data for AI analysis."""
    lines = []
    vp = data["_valor"].sum() if "_valor" in data.columns else 0
    if "_fecha" not in data.columns or data["_fecha"].isna().all():
        return lines

    evol = data.groupby(data["_fecha"].dt.to_period("M")).agg(
        Valor=("_valor", "sum"),
    ).reset_index().sort_values("_fecha")
    if "_valor_sec" in data.columns:
        evol_c = data.groupby(data["_fecha"].dt.to_period("M")).agg(
            Comprometido=("_valor_sec", "sum"),
        ).reset_index().sort_values("_fecha")
        evol["Comprometido"] = evol_c["Comprometido"]

    if len(evol) < 2:
        return lines

    lines.append("")
    lines.append("--- DATOS DE TENDENCIA Y PROYECCION ---")

    last_n = evol.tail(6)
    lines.append("Evolucion mensual (millones COP, ultimos 6 meses):")
    for _, r in last_n.iterrows():
        v_m = round(r["Valor"] / 1e6)
        c_m = round(r["Comprometido"] / 1e6) if "Comprometido" in r else 0
        mes_str = str(r["_fecha"])
        line = f"  {mes_str}: ${v_m}M"
        if c_m > 0:
            line += f" (comprometido: ${c_m}M)"
        lines.append(line)

    prom = evol["Valor"].mean()
    best = evol.loc[evol["Valor"].idxmax()]
    worst = evol.loc[evol["Valor"].idxmin()]
    lines.append(f"Promedio mensual: {fmt_pm(prom)} | Mejor mes: {str(best['_fecha'])} ({fmt_pm(best['Valor'])}) | Peor: {str(worst['_fecha'])} ({fmt_pm(worst['Valor'])})")

    if len(evol) >= 3:
        coef = np.polyfit(range(len(evol)), evol["Valor"], 1)
        r2 = np.corrcoef(range(len(evol)), evol["Valor"])[0, 1] ** 2
        slope_m = round(coef[0] / 1e6, 1)
        proy = np.polyval(coef, len(evol))
        direction = "CRECIENTE" if coef[0] > 0 else "DECRECIENTE"

        lines.append(f"Regresion lineal: pendiente = {'+' if coef[0]>0 else ''}{slope_m}M COP/mes, R² = {r2:.3f}")
        strength = "fuerte" if r2 > 0.6 else "moderada" if r2 > 0.3 else "debil"
        lines.append(f"Tendencia: {direction} ({strength}, R²={r2:.3f})")
        lines.append(f"Proyeccion proximo mes: {fmt_pm(proy)}")

        # 3-month projection
        proy3 = np.polyval(coef, len(evol) + 2)
        lines.append(f"Proyeccion en 3 meses: {fmt_pm(proy3)}")

        # Compare with budget
        try:
            from budget import cargar_ptto_company
            from config import RUTA_PRESUPUESTO_COMPANY
            ptto = cargar_ptto_company(str(RUTA_PRESUPUESTO_COMPANY))
            if ptto:
                annual = sum(v.get("ppto", 0) for v in ptto.values() if isinstance(v, dict))
                if annual > 0:
                    proy_annual = np.polyval(coef, len(evol) + 5)
                    pct = proy_annual / annual * 100
                    lines.append(f"Presupuesto anual: {fmt_pm(annual)} | Proyeccion cierre: {fmt_pm(proy_annual)} ({pct:.1f}% del ppto)")
                    if pct < 85:
                        lines.append("   ALERTA: Proyeccion por debajo del 85% del presupuesto. Se requiere plan de aceleracion.")
                    elif pct > 105:
                        lines.append("   OPORTUNIDAD: Proyeccion supera el presupuesto en mas del 5%.")
        except Exception:
            pass

    # Page-specific data
    if tipo == "pedidos" and page in ("resumen", "participacion"):
        if "_canal" in data.columns:
            canales = data.groupby("_canal")["_valor"].sum().sort_values(ascending=False)
            lines.append("")
            lines.append("Distribucion por canal:")
            for c, v in canales.items():
                pct = v / vp * 100 if vp else 0
                lines.append(f"  {c}: {fmt_pm(v)} ({pct:.1f}%)")

    if tipo == "pedidos" and page == "pareto":
        pg = data.groupby("_cliente")["_valor"].sum().sort_values(ascending=False)
        lines.append("")
        lines.append("Top 5 clientes (valor y concentracion):")
        pg_acum = (pg.cumsum() / vp * 100) if vp else pd.Series()
        for i, (cl, vl) in enumerate(pg.head(5).items()):
            ac = pg_acum.iloc[i] if len(pg_acum) > i else 0
            lines.append(f"  #{i+1} {cl[:30]}: {fmt_pm(vl)} ({vl/vp*100:.1f}%, acum {ac:.1f}%)")
        h80 = (pg_acum <= 80).sum()
        lines.append(f"Clientes para 80% del valor: {h80} de {len(pg)}")

    if tipo == "pedidos" and page == "ranking":
        rank = data.groupby("_vendedor").agg(Valor=("_valor", "sum")).reset_index().sort_values("Valor", ascending=False)
        lines.append("")
        lines.append("Top 5 asesores:")
        for _, r in rank.head(5).iterrows():
            lines.append(f"  {r['_vendedor'][:25]}: {fmt_pm(r['Valor'])} ({r['Valor']/vp*100:.1f}%)")
        brecha = rank.iloc[0]["Valor"] / rank["Valor"].mean() if len(rank) > 1 and rank["Valor"].mean() > 0 else 1
        lines.append(f"Brecha #1 vs promedio: {brecha:.1f}x {'(ALTA concentracion)' if brecha > 2 else ''}")

    if tipo == "pedidos" and page == "embudo":
        funnel = data.groupby("_estado")["_valor"].sum().sort_values(ascending=False)
        lines.append("")
        lines.append("Pipeline por estado:")
        for est, val in funnel.items():
            lines.append(f"  {est[:20]}: {fmt_pm(val)} ({val/vp*100:.1f}%)")

    return lines


def _build_analysis_prompt(tipo, page, data):
    ctx = _company_context()
    vp = data["_valor"].sum() if "_valor" in data.columns else 0
    n = len(data)

    metrics = [f"- Valor total: {fmt_p(vp)} ({fmt_pm(vp)})", f"- Registros: {n:,}"]

    if "_fecha" in data.columns and data["_fecha"].notna().any():
        fmin = data["_fecha"].min().strftime("%b %Y") if pd.notna(data["_fecha"].min()) else "N/A"
        fmax = data["_fecha"].max().strftime("%b %Y") if pd.notna(data["_fecha"].max()) else "N/A"
        metrics.append(f"- Periodo: {fmin} a {fmax}")

    if "_cliente" in data.columns:
        clientes = data["_cliente"].nunique()
        metrics.append(f"- Clientes activos: {clientes}")
    if "_vendedor" in data.columns:
        asesores = data["_vendedor"].nunique()
        metrics.append(f"- Vendedores activos: {asesores}")
    if "_documento" in data.columns:
        docs = data["_documento"].nunique()
        metrics.append(f"- Documentos: {docs:,}")

    if tipo == "pedidos":
        vc = data["_valor_sec"].sum() if "_valor_sec" in data.columns else 0
        cumpl = (vc / vp * 100) if vp else 0
        metrics.append(f"- Valor comprometido: {fmt_p(vc)} ({cumpl:.1f}% cumplimiento)")
        if "_canal" in data.columns:
            for c in data["_canal"].dropna().unique():
                pct = data[data["_canal"] == c]["_valor"].sum() / vp * 100 if vp else 0
                if pct > 1:
                    metrics.append(f"- Canal {c}: {pct:.1f}% del total")
        if "_cliente" in data.columns:
            top3 = data.groupby("_cliente")["_valor"].sum().sort_values(ascending=False)
            if len(top3) >= 3:
                t3p = top3.head(3).sum() / vp * 100 if vp else 0
                metrics.append(f"- Top 3 clientes concentran: {t3p:.1f}%")
            pg_acum = (top3.cumsum() / vp * 100) if vp else pd.Series()
            h80 = (pg_acum <= 80).sum()
            metrics.append(f"- Clientes para 80% del valor: {h80}")
        if "_estado" in data.columns:
            estados = data.groupby("_estado")["_valor"].sum().sort_values(ascending=False)
            estado_parts = []
            for est, val in estados.items():
                pct = val / vp * 100 if vp else 0
                estado_parts.append(f"{est[:15]} {pct:.0f}%")
            metrics.append("- Por estado: " + " | ".join(estado_parts[:5]))

    if tipo == "facturas":
        costo = data["_costo"].sum() if "_costo" in data.columns else 0
        margen = (vp - costo) / vp * 100 if vp and costo else 0
        docs = data["_documento"].nunique() if "_documento" in data.columns else 0
        ticket = vp / docs if docs else 0
        metrics.append(f"- Margen global: {margen:.1f}%")
        metrics.append(f"- Ticket promedio: {fmt_p(ticket)}")

    if tipo == "inventario":
        existencia = data["_cantidad"].sum() if "_cantidad" in data.columns else 0
        disponible = data["_cantidad_com"].sum() if "_cantidad_com" in data.columns else 0
        comprometido = data["_cantidad_pen"].sum() if "_cantidad_pen" in data.columns else 0
        refs = data["_referencia"].nunique() if "_referencia" in data.columns else 0
        bodegas = data["_bodega"].nunique() if "_bodega" in data.columns else 0
        metrics.append(f"- Referencias: {refs:,} en {bodegas} bodegas")
        metrics.append(f"- Existencia: {existencia:,.0f} und | Disponible: {disponible:,.0f} | Comprometido: {comprometido:,.0f}")

    # Page-specific analytical questions
    questions = _page_questions(tipo, page, data)

    # Module-specific business context
    biz_context = {
        "pedidos": "Son pedidos pendientes de despacho. Canales: CNST=Construccion, DIST=Distribucion, EXPO=Exportacion. Estados: Comprometido, Aprobado, Retenido, En elaboracion.",
        "facturas": "Son facturas de venta emitidas. Incluyen margen de venta, costo, y canal de distribucion.",
        "inventario": "Es inventario fisico en bodega. Incluye existencia, comprometido, disponible y valorizacion.",
    }.get(tipo, "")

    projection = _build_projection_data(tipo, page, data)
    proj_text = chr(10).join(projection) if projection else ""

    prompt = f"""ROL: Eres analista senior de inteligencia comercial. {ctx}

NEGOCIO: {biz_context}

SECCION: {tipo.upper()} - {page.upper()}

METRICAS DEL PERIODO:
{chr(10).join(metrics)}

{proj_text}

PREGUNTAS A RESPONDER:
{chr(10).join(questions)}

PROYECCION Y RECOMENDACION GERENCIAL:
Con base en los datos de tendencia y proyeccion, responde:
1. Cual es el escenario mas probable para el cierre del periodo? (incluye numeros)
2. Que 2 decisiones gerenciales concretas recomendarias HOY para mejorar los resultados?
3. Que KPI requiere atencion inmediata y por que?

INSTRUCCIONES:
- Responde en ESPANOL.
- Usa EXACTAMENTE este formato:

**Hallazgos Clave**
* [hallazgo 1 con datos concretos]

**Proyeccion**
* [escenario mas probable con numeros y plazo]

**Riesgos u Oportunidades**
* [punto 1]
* [punto 2]

**Decisiones Gerenciales**
* [decision concreta 1]
* [decision concreta 2]

- Incluye DATOS NUMERICOS en cada punto (valores en COP, porcentajes, tendencias).
- NO uses bloques de codigo ```. Solo texto con * y **. Se directo y accionable."""

    return prompt


def _page_questions(tipo, page, data):
    vp = data["_valor"].sum() if "_valor" in data.columns else 0
    clientes = data["_cliente"].nunique() if "_cliente" in data.columns else 0
    asesores = data["_vendedor"].nunique() if "_vendedor" in data.columns else 0

    pages = {
        ("pedidos", "resumen"): [
            "1. La distribucion entre canales es saludable o hay sobredependencia de uno?",
            "2. El nivel de cumplimiento es adecuado para el sector?",
            "3. Que patron temporal se observa en la evolucion mensual?",
            "4. Hay estacionalidad o tendencia que amerite atencion gerencial?",
        ],
        ("pedidos", "participacion"): [
            f"1. La distribucion entre los {asesores} asesores es equilibrada?",
            "2. Que canal merece mas inversion comercial?",
            "3. Hay oportunidades de crecimiento en lineas de producto especificas?",
        ],
        ("pedidos", "pareto"): [
            f"1. Con {clientes} clientes activos, la concentracion es saludable o riesgosa?",
            "2. Que clientes del top 20 tienen mayor potencial de crecimiento?",
            "3. Recomiendas diversificar la base de clientes o profundizar en los actuales?",
        ],
        ("pedidos", "ranking"): [
            f"1. Los {asesores} asesores tienen rendimiento equilibrado?",
            "2. El asesor #1 tiene participacion excesiva o es liderazgo saludable?",
            "3. Que acciones de capacitacion o incentivos recomendarias?",
        ],
        ("pedidos", "embudo"): [
            "1. La tasa de cierre (comprometido/total) es competitiva?",
            "2. Donde se estanca el pipeline de pedidos?",
            "3. Que acciones acelerarian el cierre de pedidos?",
        ],
        ("pedidos", "heatmap"): [
            f"1. Hay asesores con rendimiento inconsistente entre meses?",
            "2. Que meses son historicamente mas debiles?",
            "3. Como se puede nivelar el desempeno del equipo?",
        ],
        ("pedidos", "proyeccion"): [
            "1. La tendencia de cierre es realista frente al presupuesto anual?",
            "2. Que factores externos podrian alterar la proyeccion?",
            "3. Que meta recomendarias para el proximo trimestre?",
        ],
        ("facturas", "resumen_ventas"): [
            f"1. El ticket promedio es competitivo en el sector?",
            "2. El margen global es saludable o hay presion de costos?",
            "3. Hay estacionalidad en las ventas que permita planificar mejor?",
        ],
        ("facturas", "margenes"): [
            "1. Que canal o vendedor tiene el mejor margen?",
            "2. Hay productos con margen negativo que requieran ajuste de precio?",
            "3. Recomiendas enfocar esfuerzos en lineas de alto margen?",
        ],
        ("facturas", "mix_producto"): [
            "1. La mezcla de producto esta alineada con la estrategia comercial?",
            "2. Hay lineas o grupos sub-representados con potencial?",
            "3. Que categoria deberia priorizarse en la proxima campana?",
        ],
        ("facturas", "precio_promedio"): [
            "1. La evolucion del precio promedio es consistente con la inflacion?",
            "2. Hay categorias con erosion de precio que requieran atencion?",
            "3. Recomiendas ajustar precios en alguna linea especifica?",
        ],
        ("inventario", "resumen_stock"): [
            "1. El nivel de comprometido vs disponible es saludable?",
            "2. Hay bodegas con exceso de inventario de bajo movimiento?",
            "3. Que porcentaje del inventario esta en riesgo de obsolescencia?",
        ],
        ("inventario", "por_bodega"): [
            "1. La distribucion de inventario entre bodegas es eficiente?",
            "2. Hay productos concentrados en bodegas incorrectas?",
            "3. Recomiendas redistribuir stock entre ubicaciones?",
        ],
        ("inventario", "criticos"): [
            "1. Cuales son los 3 productos mas criticos y por que?",
            "2. Hay riesgo de desabastecimiento en productos de alta rotacion?",
            "3. Que plan de accion inmediato recomiendas para los criticos?",
        ],
    }
    key = (tipo, page)
    if key in pages:
        return [f"{q}" for q in pages[key]]
    return [f"1. Cuales son los principales hallazgos de esta seccion?",
            "2. Que riesgos identificas?", "3. Que recomiendas a gerencia?"]


def generar_analisis(tipo, page, data):
    if data.empty:
        return html.Div("Sin datos para analizar.", className="text-muted")
    if tipo == "pedidos":
        return _analisis_pedidos(page, data)
    elif tipo == "facturas":
        return _analisis_facturas(page, data)
    elif tipo == "inventario":
        return _analisis_inventario(page, data)
    else:
        return _analisis_generico(data)


def _analisis_pedidos(page, data):
    vp = data["_valor"].sum()
    vc = data["_valor_sec"].sum()
    clientes = data["_cliente"].nunique()
    pedidos = data["_documento"].nunique()
    asesores = data["_vendedor"].nunique()
    cumpl = (vc / vp * 100) if vp else 0

    if page == "resumen":
        part_cnst = 0
        if "_canal" in data.columns:
            mask = data["_canal"].str.contains("CNST|CONSTR", case=False, na=False)
            part_cnst = data.loc[mask, "_valor"].sum() / vp * 100 if vp else 0
        top3 = data.groupby("_cliente")["_valor"].sum().sort_values(ascending=False)
        top3_pct = top3.iloc[:3].sum() / vp * 100 if vp and len(top3) > 0 else 0
        meses = data["_fecha"].dt.to_period("M").nunique() if "_fecha" in data.columns else 0
        return html.Div(children=[
            html.P([html.Strong("   Resumen Ejecutivo")], style={"color": DARKGRAY}, className="fw-bold mb-2"),
            html.Ul([
                html.Li(f"Valor total de {fmt_p(vp)} en {pedidos:,} pedidos de {clientes} clientes, {asesores} asesores."),
                html.Li(f"Canal Construccion: {part_cnst:.1f}% del valor total."),
                html.Li(f"Top 3 clientes concentran {top3_pct:.1f}% del valor."),
                html.Li(f"Cumplimiento general: {cumpl:.1f}% ({fmt_p(vc)} de {fmt_p(vp)})."),
                html.Li(f"Periodo analizado: {meses} meses."),
            ], style={"paddingLeft": "1.2rem"}),
        ])
    elif page == "participacion":
        canales = data["_canal"].nunique() if "_canal" in data.columns else 0
        return html.Div(children=[html.P([html.Strong("   Participacion Comercial")], style={"color": DARKGRAY}, className="fw-bold mb-2"), html.Ul([
            html.Li(f"Distribucion en {canales} canales de venta."),
            html.Li(f"{asesores} asesores con actividad en el periodo."),
            html.Li(f"Valor promedio por asesor: {fmt_p(vp / asesores) if asesores else 0}."),
        ], style={"paddingLeft": "1.2rem"})])
    elif page == "pareto":
        pg = data.groupby("_cliente")["_valor"].sum().sort_values(ascending=False)
        pg_acum = (pg.cumsum() / vp * 100) if vp else pd.Series()
        hasta_80 = (pg_acum <= 80).sum()
        top3 = pg.head(3).sum() / vp * 100 if vp else 0
        return html.Div(children=[html.P([html.Strong("   Analisis Pareto")], style={"color": DARKGRAY}, className="fw-bold mb-2"), html.Ul([
            html.Li(f"{clientes} clientes activos en el periodo."),
            html.Li(f"Se requieren {hasta_80} clientes para alcanzar el 80%."),
            html.Li(f"Top 3 concentran {top3:.1f}% del valor."),
            html.Li(f"{'ALERTA: Alta concentracion.' if hasta_80 < 20 else 'Distribucion moderada.'}"),
        ], style={"paddingLeft": "1.2rem"})])
    elif page == "ranking":
        rank = data.groupby("_vendedor").agg(Valor=("_valor", "sum")).reset_index().sort_values("Valor", ascending=False)
        top = rank.iloc[0] if not rank.empty else None
        return html.Div(children=[html.P([html.Strong("   Ranking de Asesores")], style={"color": DARKGRAY}, className="fw-bold mb-2"), html.Ul([
            html.Li(f"#1 {top['_vendedor']}: {fmt_p(top['Valor'])}." if top is not None else "Sin datos."),
            html.Li(f"Total: {len(rank)} asesores activos."),
            html.Li(f"Promedio: {fmt_p(vp / asesores) if asesores else 0} por asesor."),
        ], style={"paddingLeft": "1.2rem"})])
    elif page == "embudo":
        return html.Div(children=[html.P([html.Strong("   Embudo de Pedidos")], style={"color": DARKGRAY}, className="fw-bold mb-2"), html.Ul([
            html.Li(f"Tasa de cierre: {cumpl:.1f}% del valor total."),
            html.Li(f"Valor pendiente: {fmt_p(vp - vc)} por comprometer."),
        ], style={"paddingLeft": "1.2rem"})])
    elif page == "heatmap":
        return html.Div(children=[html.P([html.Strong("   Heatmap de Rendimiento")], style={"color": DARKGRAY}, className="fw-bold mb-2"), html.Ul([
            html.Li(f"{asesores} asesores con desempeno registrado."),
            html.Li(f"Valor total distribuido: {fmt_p(vp)}."),
        ], style={"paddingLeft": "1.2rem"})])
    elif page == "proyeccion":
        evol = data.groupby(data["_fecha"].dt.to_period("M")).agg(Valor=("_valor", "sum")).reset_index()
        coef = np.polyfit(range(len(evol)), evol["Valor"], 1) if len(evol) >= 3 else [0, 0]
        proy = np.polyval(coef, len(evol)) if len(evol) >= 3 else 0
        direction = "creciente" if coef[0] > 0 else "decreciente"
        return html.Div(children=[html.P([html.Strong("   Proyeccion de Cierre")], style={"color": DARKGRAY}, className="fw-bold mb-2"), html.Ul([
            html.Li(f"Tendencia {direction} (pendiente: {coef[0]/1e6:.1f}M/mes)."),
            html.Li(f"Proyeccion proximo mes: {fmt_p(proy)}."),
        ], style={"paddingLeft": "1.2rem"})])
    return html.Div("Analisis no disponible.", className="text-muted")


def _analisis_facturas(page, data):
    ventas = data["_valor"].sum()
    facturas = data["_documento"].nunique()
    clientes = data["_cliente"].nunique()
    vendedores = data["_vendedor"].nunique()
    costo = data["_costo"].sum() if "_costo" in data.columns else 0
    margen_pct = (ventas - costo) / ventas * 100 if ventas else 0
    ticket = ventas / facturas if facturas else 0
    return html.Div(children=[html.P([html.Strong("   Analisis de Facturacion")], style={"color": DARKGRAY}, className="fw-bold mb-2"), html.Ul([
        html.Li(f"Ventas totales: {fmt_p(ventas)} en {facturas:,} facturas ({clientes} clientes)."),
        html.Li(f"Ticket promedio: {fmt_p(ticket)}. Margen global: {margen_pct:.1f}%."),
        html.Li(f"Equipo de {vendedores} vendedores activos."),
        html.Li(f"Costo total: {fmt_p(costo)} ({100-margen_pct:.1f}% de las ventas)."),
    ], style={"paddingLeft": "1.2rem"})])


def _analisis_inventario(page, data):
    valor_total = data["_valor"].sum()
    productos = data["_referencia"].nunique()
    bodegas = data["_bodega"].nunique() if "_bodega" in data.columns else 0
    existencia = data["_cantidad"].sum() if "_cantidad" in data.columns else 0
    disponible = data["_cantidad_com"].sum() if "_cantidad_com" in data.columns else 0
    comprometido = data["_cantidad_pen"].sum() if "_cantidad_pen" in data.columns else 0
    return html.Div(children=[html.P([html.Strong("   Analisis de Inventario")], style={"color": DARKGRAY}, className="fw-bold mb-2"), html.Ul([
        html.Li(f"Valor total inventariado: {fmt_p(valor_total)} en {productos:,} referencias."),
        html.Li(f"Distribuido en {bodegas} bodegas con {existencia:,.0f} unidades."),
        html.Li(f"Disponible: {disponible:,.0f} und. Comprometido: {comprometido:,.0f} und."),
        html.Li(f"Valor promedio por producto: {fmt_p(valor_total / productos) if productos else 0}."),
    ], style={"paddingLeft": "1.2rem"})])


def _analisis_generico(data):
    n = len(data)
    cols = [c for c in data.columns if not c.startswith("_")]
    return html.Div(children=[html.P([html.Strong("   Analisis Exploratorio")], style={"color": DARKGRAY}, className="fw-bold mb-2"), html.Ul([
        html.Li(f"Dataset con {n:,} registros y {len(cols)} columnas."),
        html.Li(f"Columnas: {', '.join(cols[:10])}"),
    ], style={"paddingLeft": "1.2rem"})])


def _format_ai_response(text, source_label, source_color):
    """Convert **bold** markers to html.Strong, clean up fences."""
    import re
    text = text.replace("```html", "").replace("```", "").strip()
    parts = re.split(r'(\*\*[^*]+\*\*)', text)
    formatted = []
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            formatted.append(html.Strong(part[2:-2]))
        else:
            formatted.append(part)
    return html.Div([
        html.P([html.Strong(f"   {source_label}")], style={"color": source_color}, className="fw-bold mb-2"),
        html.Div(formatted, className="small", style={"lineHeight": "1.6"}),
    ])


def generar_con_gemini(tipo, page, data, api_key):
    if not api_key or data.empty:
        return None
    prompt = _build_analysis_prompt(tipo, page, data)
    for attempt in range(3):
        try:
            resp = requests.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
                params={"key": api_key},
                json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
            if resp.ok:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                return _format_ai_response(text, "Gemini AI", BLUE)
            elif resp.status_code == 429 and attempt < 2:
                time.sleep(2 ** attempt)
        except Exception:
            if attempt < 2:
                time.sleep(2 ** attempt)
    return None


def generar_con_opencode(tipo, page, data, api_key):
    if not api_key or data.empty:
        return None
    prompt = _build_analysis_prompt(tipo, page, data)
    for attempt in range(2):
        try:
            resp = requests.post("https://api.opencode.ai/v1/chat/completions",
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": prompt}]},
                headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
            if resp.ok:
                text = resp.json()["choices"][0]["message"]["content"]
                return _format_ai_response(text, "OpenCode AI", GOLD)
            elif resp.status_code == 429 and attempt < 1:
                time.sleep(3)
        except Exception:
            if attempt < 1:
                time.sleep(2)
    return None
