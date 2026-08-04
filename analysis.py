import pandas as pd
import numpy as np
import requests
import time
from dash import html
from pages.components import fmt_p, fmt_pm, DARKGRAY, BLUE, GOLD


def _company_context():
    return (
        "Interdoors S.A.S., empresa colombiana con 30+ anos en carpinteria arquitectonica "
        "(puertas, muebles de cocina, banos, closets). Reportas a gerencia general con datos del ERP SIESA Enterprise. "
        "La empresa opera en 3 canales: Construccion (CNST), Distribucion (DIST) y Exportacion (EXPO). "
        "Margenes saludables en el sector estan entre 25-35%. Una concentracion de clientes superior al 50% en "
        "el top 3 es riesgo. La tasa de cierre saludable en el sector es >60%. "
        "El presupuesto anual se revisa mensualmente contra la realidad."
    )


def _build_projection_data(tipo, page, data):
    """Compute time-series, trend, and projection data for AI analysis."""
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

    evol["Crec %"] = evol["Valor"].pct_change() * 100
    evol["MM3"] = evol["Valor"].rolling(3, min_periods=1).mean()

    n = len(evol)
    last = evol.iloc[-1]
    prev = evol.iloc[-2] if n >= 2 else None
    growth = last["Crec %"] if not pd.isna(last["Crec %"]) else 0

    lines.append("--- TENDENCIA Y PROYECCION ---")
    lines.append(f"Evolucion mensual (millones COP):")
    for _, r in evol.tail(6).iterrows():
        c_str = f" (comp: ${round(r['Comprometido']/1e6)}M)" if "Comprometido" in r and not pd.isna(r.get("Comprometido")) else ""
        g_str = f" [{r['Crec %']:+.1f}%]" if not pd.isna(r.get("Crec %")) else ""
        lines.append(f"  {str(r['_fecha'])}: ${round(r['Valor']/1e6)}M{g_str}{c_str}")

    prom = evol["Valor"].mean()
    best = evol.loc[evol["Valor"].idxmax()]
    worst = evol.loc[evol["Valor"].idxmin()]
    mm3_last = last["MM3"]
    lines.append(f"Promedio mensual: {fmt_pm(prom)} | Media movil 3M: {fmt_pm(mm3_last)}")
    lines.append(f"Mejor mes: {str(best['_fecha'])} ({fmt_pm(best['Valor'])}) | Peor: {str(worst['_fecha'])} ({fmt_pm(worst['Valor'])})")
    lines.append(f"Ultimo mes: {fmt_pm(last['Valor'])} | Crecimiento vs mes anterior: {growth:+.1f}%")

    if n >= 3:
        coef = np.polyfit(range(n), evol["Valor"], 1)
        r2 = np.corrcoef(range(n), evol["Valor"])[0, 1] ** 2
        slope_m = round(coef[0] / 1e6, 1)
        residuos = evol["Valor"] - np.polyval(coef, range(n))
        std_err = np.std(residuos)

        proy = np.polyval(coef, n)
        proy_low = proy - 1.28 * std_err
        proy_high = proy + 1.28 * std_err
        proy3 = np.polyval(coef, n + 2)
        proy6 = np.polyval(coef, n + 5)
        direction = "creciente" if coef[0] > 0 else "decreciente"

        strength = "fuerte" if r2 > 0.7 else "moderada" if r2 > 0.4 else "debil"
        lines.append(f"Regresion lineal: {direction} a {slope_m:+.1f}M COP/mes | R² = {r2:.3f} ({strength})")
        lines.append(f"Volatilidad (error estandar): {fmt_pm(std_err)} ({std_err/proy*100:.1f}% de la proyeccion)")
        lines.append(f"Proyeccion proximo mes: {fmt_pm(proy)} (rango 80%: {fmt_pm(proy_low)} a {fmt_pm(proy_high)})")
        lines.append(f"Proyeccion en 3 meses: {fmt_pm(proy3)} | Proyeccion en 6 meses: {fmt_pm(proy6)}")

        # Budget comparison
        try:
            from budget import cargar_ptto_company
            from config import RUTA_PRESUPUESTO_COMPANY
            ptto = cargar_ptto_company(str(RUTA_PRESUPUESTO_COMPANY))
            if ptto:
                annual = sum(v.get("ppto", 0) for v in ptto.values() if isinstance(v, dict))
                if annual > 0:
                    proy_annual = np.polyval(coef, n + 11)
                    pct = proy_annual / annual * 100
                    monthly_needed = (annual - evol["Valor"].sum()) / max(12 - n, 1)
                    lines.append(f"Presupuesto anual: {fmt_pm(annual)} | Proyeccion cierre: {fmt_pm(proy_annual)} ({pct:.1f}% del ppto)")
                    lines.append(f"Para cumplir el presupuesto faltan {fmt_pm(annual - evol['Valor'].sum())} en {12-n} meses -> necesario {fmt_pm(monthly_needed)}/mes")
                    if pct < 85:
                        lines.append("   ⚠ ALERTA: Proyeccion de cierre por debajo del 85% del presupuesto. Accion requerida.")
                    elif pct < 95:
                        lines.append("   ⚡ ATENCION: Proyeccion entre 85-95%. Se necesita aceleracion moderada.")
                    elif pct > 105:
                        lines.append("   ✅ OPORTUNIDAD: Proyeccion supera presupuesto. Evaluar si ajustar meta al alza.")
        except Exception:
            pass

    # Page-specific enrichment
    if tipo == "pedidos" and page == "embudo":
        funnel = data.groupby("_estado")["_valor"].sum().sort_values(ascending=False)
        lines.append("")
        lines.append("--- PIPELINE POR ESTADO ---")
        for est, val in funnel.items():
            lines.append(f"  {est[:20]}: {fmt_pm(val)} ({val/vp*100:.1f}%)")

    if tipo == "pedidos" and page == "pareto":
        pg = data.groupby("_cliente")["_valor"].sum().sort_values(ascending=False)
        pg_acum = (pg.cumsum() / vp * 100) if vp else pd.Series()
        h80 = (pg_acum <= 80).sum()
        h50 = (pg_acum <= 50).sum()
        lines.append("")
        lines.append("--- ANALISIS DE CONCENTRACION ---")
        lines.append(f"Total clientes activos: {len(pg)}")
        lines.append(f"Clientes para 50% del valor: {h50} | Para 80%: {h80}")
        lines.append(f"Top 3 concentran: {pg.head(3).sum()/vp*100:.1f}% | Top 5 concentran: {pg.head(5).sum()/vp*100:.1f}%")

    return lines


def _build_analysis_prompt(tipo, page, data):
    ctx = _company_context()
    vp = data["_valor"].sum() if "_valor" in data.columns else 0
    vc = data["_valor_sec"].sum() if "_valor_sec" in data.columns else 0
    n = len(data)
    cumpl = (vc / vp * 100) if vp else 0

    metrics = []
    if "_fecha" in data.columns and data["_fecha"].notna().any():
        fmin = data["_fecha"].min().strftime("%b %Y") if pd.notna(data["_fecha"].min()) else "N/A"
        fmax = data["_fecha"].max().strftime("%b %Y") if pd.notna(data["_fecha"].max()) else "N/A"
        metrics.append(f"- Periodo analizado: {fmin} a {fmax}")
    metrics.append(f"- Valor total: {fmt_p(vp)} ({fmt_pm(vp)})")
    metrics.append(f"- Registros procesados: {n:,}")
    if vc > 0:
        metrics.append(f"- Valor comprometido: {fmt_p(vc)} ({cumpl:.1f}% del total)")

    if "_cliente" in data.columns:
        clientes = data["_cliente"].nunique()
        metrics.append(f"- Clientes activos: {clientes}")
    if "_vendedor" in data.columns:
        asesores = data["_vendedor"].nunique()
        metrics.append(f"- Vendedores activos: {asesores}")
    if "_documento" in data.columns:
        docs = data["_documento"].nunique()
        metrics.append(f"- Documentos: {docs:,}")

    # Canal detail for pedidos
    if tipo == "pedidos" and "_canal" in data.columns:
        for c in data["_canal"].dropna().unique():
            pct = data[data["_canal"] == c]["_valor"].sum() / vp * 100 if vp else 0
            if pct > 1:
                metrics.append(f"- Canal {c}: {pct:.1f}% del total")
        top3 = data.groupby("_cliente")["_valor"].sum().sort_values(ascending=False)
        if len(top3) >= 3:
            t3p = top3.head(3).sum() / vp * 100 if vp else 0
            metrics.append(f"- Top 3 clientes concentran: {t3p:.1f}%")
            pg_acum = (top3.cumsum() / vp * 100) if vp else pd.Series()
            h80 = (pg_acum <= 80).sum()
            metrics.append(f"- Clientes necesarios para el 80%: {h80}")

    # Ranking-specific data
    ranking_context = ""
    if tipo == "pedidos" and page == "ranking":
        rank = data.groupby("_vendedor").agg(
            Valor=("_valor", "sum"), Comprometido=("_valor_sec", "sum"),
            Pedidos=("_documento", "nunique"), Clientes=("_cliente", "nunique"),
        ).reset_index().sort_values("Valor", ascending=False)
        rank["% Part"] = (rank["Valor"] / vp * 100).round(1) if vp else 0
        rank["Ticket"] = (rank["Valor"] / rank["Pedidos"].replace(0, 1)).round(0)
        brecha = (rank["Valor"].iloc[0] / rank["Valor"].mean()) if len(rank) > 1 and rank["Valor"].mean() > 0 else 1

        try:
            from budget import cargar_presupuesto_asesores, get_budget_for
            from config import RUTA_PRESUPUESTO, RUTA_PRESUPUESTO_ASESORES
            budgets = cargar_presupuesto_asesores(str(RUTA_PRESUPUESTO))
            if not budgets:
                budgets = cargar_presupuesto_asesores(str(RUTA_PRESUPUESTO_ASESORES))
        except Exception:
            budgets = {}

        lines = ["", "--- RANKING DETALLADO ---"]
        lines.append(f"Asesores activos: {len(rank)} | Brecha #1 vs promedio: {brecha:.1f}x")
        lines.append(f"Valor total del equipo: {fmt_pm(vp)}")
        for _, r in rank.head(6).iterrows():
            n = str(r["_vendedor"])[:25]
            pp = get_budget_for(str(r["_vendedor"]), budgets)
            pp_pct = (r["Valor"] / pp * 100) if pp > 0 else 0
            ticket = r["Ticket"]
            cump = (r["Comprometido"] / pp * 100) if pp > 0 else 0
            line = f"  #{r.name+1} {n}: {fmt_pm(r['Valor'])} ({r['% Part']:.1f}% part) | Ticket prom: {fmt_p(ticket)}"
            if pp > 0:
                line += f" | vs Meta: {pp_pct:.1f}% | % Cumpl: {cump:.1f}%"
            lines.append(line)
        ranking_context = "\n".join(lines)

    # Proyeccion data
    projection = _build_projection_data(tipo, page, data)
    proj_text = "\n".join(projection) if projection else ""

    # Biz context
    biz_context = {
        "pedidos": "Pedidos pendientes de despacho. Canales: CNST=Construccion, DIST=Distribucion, EXPO=Exportacion. Estados: Comprometido, Aprobado, Retenido, En elaboracion. % Cumpl mide lo realmente comprometido vs la meta anual.",
        "facturas": "Facturas de venta emitidas. Incluyen margen de venta, costo, y canal de distribucion.",
        "inventario": "Inventario fisico en bodega. Incluye existencia, comprometido, disponible y valorizacion.",
    }.get(tipo, "")

    prompt = f"""ERES UN DIRECTOR COMERCIAL SENIOR con 20 anos de experiencia en el sector de carpinteria arquitectonica en Colombia. Reportas directamente a la junta directiva. Tu analisis debe ser estrategico, basado en datos, y orientado a la accion.

CONTEXTO DE LA EMPRESA:
{ctx}

DATOS DE LA SECCION ACTUAL: {tipo.upper()} - {page.upper()}
{biz_context}

METRICAS CLAVE:
{chr(10).join(metrics)}

{proj_text}

{ranking_context}

TAREA: Realiza un analisis ejecutivo en ESPANOL con el siguiente formato EXACTO. Cada seccion debe tener datos numericos concretos. NO uses frases genericas como "se recomienda mejorar". Cada recomendacion debe ser especifica y cuantificable.

**📊 HALLAZGOS CLAVE**
* [2-3 hallazgos con datos precisos. Ej: "El canal Construccion concentra el 65% del valor ($5.200M), pero solo representa el 40% de los pedidos, indicando tickets mas altos que en Distribucion."]

**📈 PROYECCION DE CIERRE**
* [Escenario base con numeros, metodo usado (regresion/tendencia), y nivel de confianza segun R². Ej: "Con R²=0.87, la proyeccion de cierre es $18.500M para el proximo mes, con banda de confianza 80% entre $16.000M y $21.000M."]
* [Comparacion vs presupuesto anual si hay datos. Ej: "Esto representa un 88% del presupuesto anual de $21.000M. Al ritmo actual, el cierre de ano se proyecta en $22.200M (106% de la meta)."]

**⚠️ RIESGOS Y OPORTUNIDADES**
* [2-3 riesgos concretos con impacto estimado en pesos o %. Ej: "RIESGO: El asesor #1 (Zuleta) concentra el 37.3% del valor total. Si este asesor sale de la empresa, se pierden $3.061M en pipeline. Recomiendo plan de retencion inmediato."]
* [2-3 oportunidades cuantificadas. Ej: "OPORTUNIDAD: Posada tiene un ticket promedio 3x mayor que Gonzalez ($18.3M vs $5.7M). Si Gonzalez mejora su ticket al promedio del equipo, el valor total aumentaria en $420M."]

**🎯 DECISIONES GERENCIALES (TOP 3)**
* [Decision 1 con impacto estimado, responsable sugerido y plazo. Ej: "REDISTRIBUIR CARTERA: Asignar 3 clientes top de Zuleta a Pulgarin y Garces para reducir concentracion. Impacto estimado: reduccion de brecha de 2.2x a 1.5x en 60 dias."]
* [Decision 2 con impacto estimado, responsable sugerido y plazo]
* [Decision 3 con impacto estimado, responsable sugerido y plazo]

**🔍 KPI EN RIESGO**
* [1 KPI que requiere atencion inmediata, con valor actual, umbral critico y plan de correccion. Ej: "% Cumplimiento general: 4.2% vs umbral minimo aceptable de 15%. Causa probable: V.COMPROMETIDO no se esta registrando en SIESA."]

INSTRUCCIONES:
- Responde en ESPANOL, lenguaje profesional pero directo
- Cada punto DEBE incluir minimo 1 dato numerico (pesos, %, unidades, ratios)
- Nombra asesores, canales, clientes ESPECIFICOS cuando aplique
- Las Decisiones Gerenciales deben ser ACCIONABLES (quien, que, cuando, impacto esperado)
- Si no hay datos de presupuesto, omite comparaciones presupuestarias
- NO uses markdown avanzado, solo **negritas** y * para bullets
- NO uses emojis diferentes a los indicados
- Se conciso. Maximo 5 bullets por seccion"""

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
    vc = data["_valor_sec"].sum() if "_valor_sec" in data.columns else 0
    clientes = data["_cliente"].nunique()
    pedidos = data["_documento"].nunique()
    asesores = data["_vendedor"].nunique()
    cumpl = (vc / vp * 100) if vp else 0
    meses = data["_fecha"].dt.to_period("M").nunique() if "_fecha" in data.columns else 0

    title = {
        "home": "Dashboard Ejecutivo", "resumen": "Resumen Ejecutivo",
        "participacion": "Participación Comercial", "pareto": "Pareto de Clientes",
        "ranking": "Ranking de Asesores", "embudo": "Embudo de Pedidos",
        "heatmap": "Heatmap de Rendimiento", "proyeccion": "Proyección de Cierre",
    }.get(page, "Análisis")

    items = []

    # ---- Common header ----
    items.append(html.P([html.Strong(f"   {title}")], style={"color": DARKGRAY}, className="fw-bold mb-2"))

    if page == "home" or page == "resumen":
        part_cnst = 0
        if "_canal" in data.columns:
            mask = data["_canal"].str.contains("CNST|CONSTR", case=False, na=False)
            part_cnst = data.loc[mask, "_valor"].sum() / vp * 100 if vp else 0
        top3 = data.groupby("_cliente")["_valor"].sum().sort_values(ascending=False)
        top3_pct = top3.iloc[:3].sum() / vp * 100 if vp and len(top3) > 0 else 0
        items.append(html.P("📊 HALLAZGOS CLAVE", style={"fontWeight": "bold", "fontSize": "0.78rem", "marginBottom": "4px"}))
        items.append(html.Ul([
            html.Li(f"Pipeline total de {fmt_p(vp)} en {pedidos:,} pedidos de {clientes} clientes, equipo de {asesores} asesores."),
            html.Li(f"Canal Construcción: {part_cnst:.1f}% del valor. Top 3 clientes concentran {top3_pct:.1f}%."),
            html.Li(f"Cumplimiento: {cumpl:.1f}% ({fmt_p(vc)} comprometido de {fmt_p(vp)}). Periodo: {meses} meses."),
        ], style={"paddingLeft": "1.2rem", "fontSize": "0.8rem"}))
        if top3_pct > 50:
            items.append(html.P(f"⚠ Riesgo: alta concentración de clientes. Top 3 concentran {top3_pct:.1f}%. Recomendable diversificar.", style={"fontSize": "0.75rem", "color": RED}))
        if cumpl < 30:
            items.append(html.P(f"⚠ Riesgo: bajo cumplimiento ({cumpl:.1f}%). Priorizar cierre de pedidos en pipeline.", style={"fontSize": "0.75rem", "color": RED}))

    elif page == "participacion":
        canales = data["_canal"].nunique() if "_canal" in data.columns else 0
        top_canal = data.groupby("_canal")["_valor"].sum().idxmax() if "_canal" in data.columns else "N/D"
        top_pct = data.groupby("_canal")["_valor"].sum().max() / vp * 100 if vp else 0
        items.append(html.Ul([
            html.Li(f"{canales} canales activos. Principal: {str(top_canal)[:25]} ({top_pct:.1f}% del total)."),
            html.Li(f"Equipo de {asesores} asesores. Promedio: {fmt_pm(vp/asesores) if asesores else 0} por asesor."),
            html.Li(f"Líneas de producto: {data['_linea'].nunique() if '_linea' in data.columns else 0}. Ticket promedio: {fmt_p(vp/pedidos) if pedidos else 0}."),
        ], style={"paddingLeft": "1.2rem", "fontSize": "0.8rem"}))

    elif page == "pareto":
        pg = data.groupby("_cliente")["_valor"].sum().sort_values(ascending=False)
        pg_acum = (pg.cumsum() / vp * 100) if vp else pd.Series()
        h80 = (pg_acum <= 80).sum()
        h50 = (pg_acum <= 50).sum()
        top3_pct = pg.head(3).sum() / vp * 100 if vp else 0
        items.append(html.Ul([
            html.Li(f"{clientes} clientes activos. {h50} clientes concentran el 50% del valor, {h80} para el 80%."),
            html.Li(f"Top 3 clientes concentran {top3_pct:.1f}%. Top 10: {pg.head(10).sum()/vp*100:.1f}%."),
        ], style={"paddingLeft": "1.2rem", "fontSize": "0.8rem"}))
        if h80 < 20:
            items.append(html.P(f"⚠ Riesgo de concentración: solo {h80} clientes representan el 80% del valor. Dependencia crítica de pocos clientes.", style={"fontSize": "0.75rem", "color": RED}))
        elif h80 > 50:
            items.append(html.P(f"✅ Distribución saludable: se necesitan {h80} clientes para el 80%. Base diversificada.", style={"fontSize": "0.75rem", "color": GREEN}))

    elif page == "ranking":
        rank = data.groupby("_vendedor").agg(
            Valor=("_valor", "sum"), Pedidos=("_documento", "nunique"),
            Clientes=("_cliente", "nunique"), Comprometido=("_valor_sec", "sum"),
        ).reset_index().sort_values("Valor", ascending=False)
        brecha = (rank["Valor"].iloc[0] / rank["Valor"].mean()) if len(rank) > 1 and rank["Valor"].mean() > 0 else 1

        try:
            from budget import cargar_presupuesto_asesores, get_budget_for
            from config import RUTA_PRESUPUESTO, RUTA_PRESUPUESTO_ASESORES
            budgets = cargar_presupuesto_asesores(str(RUTA_PRESUPUESTO))
            if not budgets:
                budgets = cargar_presupuesto_asesores(str(RUTA_PRESUPUESTO_ASESORES))
        except Exception:
            budgets = {}

        items.append(html.P("📊 DESEMPEÑO DEL EQUIPO", style={"fontWeight": "bold", "fontSize": "0.78rem", "marginBottom": "4px"}))
        lines = [html.Li(f"{len(rank)} asesores activos. Valor total: {fmt_p(vp)}. Brecha #1 vs promedio: {brecha:.1f}x.")]
        if brecha > 2:
            lines.append(html.Li(f"⚠ Alta concentración: el #1 concentra {(rank['Valor'].iloc[0]/vp*100):.1f}% del valor total."))

        top_ppto = 0
        for _, r in rank.head(3).iterrows():
            n = str(r["_vendedor"])[:20]
            pp = get_budget_for(str(r["_vendedor"]), budgets)
            if pp > 0:
                top_ppto += 1
                pp_pct = r["Valor"] / pp * 100
                cp_pct = r["Comprometido"] / pp * 100
                lines.append(html.Li(f"{n}: {fmt_pm(r['Valor'])} ({r['Valor']/vp*100:.1f}% part) | vs Meta: {pp_pct:.1f}% | % Cumpl: {cp_pct:.1f}%"))
            else:
                lines.append(html.Li(f"{n}: {fmt_pm(r['Valor'])} ({r['Valor']/vp*100:.1f}% part) | Sin meta asignada"))
        lines.append(html.Li(f"Cumplimiento promedio: {rank['Comprometido'].sum()/vp*100:.1f}% del pipeline comprometido."))
        items.append(html.Ul(lines, style={"paddingLeft": "1.2rem", "fontSize": "0.8rem"}))

        if brecha > 2:
            items.append(html.P("🎯 Recomendación: Redistribuir clientes del #1 hacia asesores con menor carga para balancear el equipo.", style={"fontSize": "0.75rem", "color": GOLD}))
        if top_ppto < 3:
            items.append(html.P("🎯 Recomendación: Asignar metas de presupuesto a los asesores sin meta para poder medir su rendimiento.", style={"fontSize": "0.75rem", "color": GOLD}))

    elif page == "embudo":
        funnel = data.groupby("_estado").agg(
            Valor=("_valor", "sum"), Pedidos=("_documento", "nunique"),
        ).reset_index().sort_values("Valor", ascending=False)
        total = funnel["Valor"].sum()
        comp = funnel[funnel["_estado"].str.contains("Comprometido|Cumplid|Despac", na=False, case=False)]["Valor"].sum()
        rate = comp / total * 100 if total else 0
        items.append(html.Ul([
            html.Li(f"Pipeline: {fmt_p(vp)} en {len(funnel)} estados. Tasa de cierre: {rate:.1f}%."),
            html.Li(f"Pendiente por comprometer: {fmt_p(vp - vc)} ({100-rate:.1f}% del pipeline)."),
            html.Li(f"Estados principales: {funnel.iloc[0]['_estado'][:20]} ({funnel.iloc[0]['Valor']/total*100:.1f}%), {funnel.iloc[1]['_estado'][:20]} ({funnel.iloc[1]['Valor']/total*100:.1f}%)."),
        ], style={"paddingLeft": "1.2rem", "fontSize": "0.8rem"}))
        if rate < 40:
            items.append(html.P(f"⚠ Tasa de cierre baja ({rate:.1f}%). Priorizar aceleración de pedidos en estados iniciales.", style={"fontSize": "0.75rem", "color": RED}))

    elif page == "heatmap":
        meses_n = data["_fecha"].dt.to_period("M").nunique() if "_fecha" in data.columns else 0
        items.append(html.Ul([
            html.Li(f"{asesores} asesores activos en {meses_n} meses analizados."),
            html.Li(f"Valor total distribuido: {fmt_p(vp)}. Promedio por asesor/mes: {fmt_p(vp/asesores/meses_n) if asesores and meses_n else 0}."),
        ], style={"paddingLeft": "1.2rem", "fontSize": "0.8rem"}))

    elif page == "proyeccion":
        evol = data.groupby(data["_fecha"].dt.to_period("M")).agg(Valor=("_valor", "sum")).reset_index()
        if len(evol) >= 3:
            coef = np.polyfit(range(len(evol)), evol["Valor"], 1)
            r2 = np.corrcoef(range(len(evol)), evol["Valor"])[0, 1] ** 2
            proy = np.polyval(coef, len(evol))
            direction = "creciente" if coef[0] > 0 else "decreciente"
            growth_pct = (coef[0] / evol["Valor"].mean() * 100) if evol["Valor"].mean() > 0 else 0
            items.append(html.Ul([
                html.Li(f"Tendencia {direction} ({growth_pct:+.1f}%/mes) con R²={r2:.3f}."),
                html.Li(f"Proyección próximo mes: {fmt_p(proy)} ({fmt_pm(proy)})."),
                html.Li(f"Meses analizados: {len(evol)}. Mes pico: {fmt_pm(evol['Valor'].max())} ({evol.loc[evol['Valor'].idxmax(), '_fecha']})."),
            ], style={"paddingLeft": "1.2rem", "fontSize": "0.8rem"}))
            if r2 < 0.3:
                items.append(html.P(f"⚠ Baja confiabilidad (R²={r2:.3f}). La proyección es indicativa. Se recomienda monitorear.", style={"fontSize": "0.75rem", "color": AMBER}))
        else:
            items.append(html.Ul([html.Li(f"Datos insuficientes: {len(evol)} meses. Se requieren al menos 3 para proyección.")], style={"paddingLeft": "1.2rem", "fontSize": "0.8rem"}))

    return html.Div(children=items)


def _analisis_facturas(page, data):
    ventas = data["_valor"].sum()
    facturas = data["_documento"].nunique()
    clientes = data["_cliente"].nunique()
    vendedores = data["_vendedor"].nunique() if "_vendedor" in data.columns else 0
    costo = data["_costo"].sum() if "_costo" in data.columns else 0
    margen_pct = (ventas - costo) / ventas * 100 if ventas else 0
    ticket = ventas / facturas if facturas else 0
    has_costo = "_costo" in data.columns and costo > 0
    has_margen = "_margen" in data.columns

    items = []
    title = {"resumen_ventas": "Resumen de Ventas", "margenes": "Márgenes",
             "mix_producto": "Mix de Producto", "precio_promedio": "Precio Promedio"}.get(page, "Análisis")
    items.append(html.P([html.Strong(f"   {title}")], style={"color": DARKGRAY}, className="fw-bold mb-2"))
    items.append(html.P("📊 HALLAZGOS CLAVE", style={"fontWeight": "bold", "fontSize": "0.78rem", "marginBottom": "4px"}))

    lines = [html.Li(f"Ventas totales: {fmt_p(ventas)} en {facturas:,} facturas ({clientes} clientes).")]
    lines.append(html.Li(f"Ticket promedio: {fmt_p(ticket)}.{' Margen global: ' + str(round(margen_pct,1)) + '%' if has_costo else ''}"))
    if vendedores:
        lines.append(html.Li(f"Equipo de {vendedores} vendedores activos. Promedio: {fmt_p(ventas/vendedores) if vendedores else 0} por vendedor."))

    if has_costo:
        lines.append(html.Li(f"Costo total: {fmt_p(costo)} ({100-margen_pct:.1f}% de las ventas). Utilidad bruta: {fmt_p(ventas - costo)}."))
        if margen_pct < 20:
            lines.append(html.Li(f"⚠ Margen bajo ({margen_pct:.1f}%). Revisar costos o ajustar precios."))
        elif margen_pct > 35:
            lines.append(html.Li(f"✅ Margen saludable ({margen_pct:.1f}%)."))

    if has_margen and "_canal" in data.columns:
        canal_top = data.groupby("_canal")["_margen"].mean().idxmax()
        canal_mgn = data.groupby("_canal")["_margen"].mean().max()
        lines.append(html.Li(f"Mejor margen por canal: {str(canal_top)[:20]} ({canal_mgn:.1f}%)."))

    if has_margen and "_vendedor" in data.columns:
        vend_top = data.groupby("_vendedor")["_margen"].mean().idxmax()
        vend_mgn = data.groupby("_vendedor")["_margen"].mean().max()
        lines.append(html.Li(f"Mejor margen por vendedor: {str(vend_top)[:20]} ({vend_mgn:.1f}%)."))

    items.append(html.Ul(lines, style={"paddingLeft": "1.2rem", "fontSize": "0.8rem"}))
    return html.Div(children=items)


def _analisis_inventario(page, data):
    valor_total = data["_valor"].sum()
    productos = data["_referencia"].nunique() if "_referencia" in data.columns else 0
    bodegas = data["_bodega"].nunique() if "_bodega" in data.columns else 0
    existencia = data["_cantidad"].sum() if "_cantidad" in data.columns else 0
    disponible = data["_cantidad_com"].sum() if "_cantidad_com" in data.columns else 0
    comprometido = data["_cantidad_pen"].sum() if "_cantidad_pen" in data.columns else 0
    pct_comp = (comprometido / existencia * 100) if existencia else 0
    pct_disp = (disponible / existencia * 100) if existencia else 0

    items = []
    title = {"resumen_stock": "Resumen de Stock", "por_bodega": "Por Bodega",
             "criticos": "Productos Críticos"}.get(page, "Análisis")
    items.append(html.P([html.Strong(f"   {title}")], style={"color": DARKGRAY}, className="fw-bold mb-2"))
    items.append(html.P("📊 HALLAZGOS CLAVE", style={"fontWeight": "bold", "fontSize": "0.78rem", "marginBottom": "4px"}))

    lines = [html.Li(f"Valor total inventariado: {fmt_p(valor_total)} en {productos:,} referencias, {bodegas} bodegas.")]
    lines.append(html.Li(f"Existencia: {existencia:,.0f} und. Disponible: {disponible:,.0f} ({pct_disp:.1f}%). Comprometido: {comprometido:,.0f} ({pct_comp:.1f}%)."))
    lines.append(html.Li(f"Valor promedio por producto: {fmt_p(valor_total/productos) if productos else 0}."))

    if page == "criticos" and "_cantidad_com" in data.columns and "_cantidad" in data.columns:
        data_copy = data.copy()
        data_copy["_ratio"] = data_copy["_cantidad_com"] / data_copy["_cantidad"].replace(0, 1) * 100
        criticos = data_copy[data_copy["_ratio"] > 80]
        n_criticos = criticos["_referencia"].nunique()
        val_criticos = criticos["_valor"].sum()
        if n_criticos > 0:
            lines.append(html.Li(f"⚠ {n_criticos} productos críticos (>80% comprometido) con valor de {fmt_p(val_criticos)}."))
        bajo_stock = data[data["_cantidad"] <= 3]
        n_bajo = bajo_stock["_referencia"].nunique()
        if n_bajo > 0:
            lines.append(html.Li(f"⚠ {n_bajo} productos con stock bajo (≤3 unidades)."))

    if pct_comp > 70:
        lines.append(html.Li(f"⚠ Alto compromiso ({pct_comp:.1f}%). Riesgo de desabastecimiento. Priorizar reposición."))
    elif pct_comp < 30:
        lines.append(html.Li(f"✅ Compromiso bajo ({pct_comp:.1f}%). Stock suficiente para demanda actual."))

    items.append(html.Ul(lines, style={"paddingLeft": "1.2rem", "fontSize": "0.8rem"}))
    return html.Div(children=items)


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
        return None, "API key vacía"
    prompt = _build_analysis_prompt(tipo, page, data)
    start = time.time()

    try:
        resp = requests.post("https://api.opencode.ai/v1/chat/completions",
            json={"model": "opencode", "messages": [{"role": "user", "content": prompt}]},
            headers={"Authorization": f"Bearer {api_key}"}, timeout=45)
        elapsed = time.time() - start
        raw_text = resp.text[:500]

        if not resp.ok:
            return None, f"HTTP {resp.status_code} - {raw_text[:80]}"

        try:
            data = resp.json()
        except Exception:
            return None, f"Respuesta no es JSON: {raw_text[:100]}"

        if "choices" in data and len(data["choices"]) > 0:
            text = data["choices"][0]["message"]["content"]
            print(f"[OpenCode] OK ({elapsed:.1f}s)")
            return _format_ai_response(text, "OpenCode AI", GOLD), ""

        return None, f"Respuesta sin choices: {str(data)[:120]}"
    except Exception as e:
        elapsed = time.time() - start
        return None, f"ERROR ({elapsed:.1f}s): {str(e)[:80]}"
