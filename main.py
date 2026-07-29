"""
PROCESO AUTOMATIZADO DE PEDIDOS SIESA
======================================
1. Descarga el archivo desde SIESA
2. Colocalo en la carpeta 'entrada/'
3. Ejecuta: python main.py
4. Todo se procesa automaticamente

UNA SOLA TABLA MAESTRA → todos los informes derivados
"""
import shutil
import json
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np
from config import (
    CARPETA_ENTRADA, CARPETA_BASE, CARPETA_ASESORES, CARPETA_GERENCIA,
    CARPETA_DASHBOARD, CARPETA_LOGS, CARPETA_REPORTES_SIESA,
    ARCHIVO_BASE, ARCHIVO_LOG, HOJA_SIESA,
    COLUMNAS_REQUERIDAS, COLUMNAS_NUMERICAS, LLAVE_UNICA, MESES_ES
)
import warnings
warnings.filterwarnings("ignore")

CARPETA_BACKUPS = CARPETA_BASE / "backups"
CARPETA_BACKUPS.mkdir(parents=True, exist_ok=True)

# ============================================================
# 1. DETECTAR ARCHIVO
# ============================================================
def detectar_archivo(ruta=None):
    if ruta:
        ruta = Path(ruta)
        if ruta.exists():
            return ruta
        raise FileNotFoundError(f"Archivo no encontrado: {ruta}")

    for carpeta in [CARPETA_ENTRADA, CARPETA_REPORTES_SIESA]:
        archivos = sorted(carpeta.glob("*.xlsx"))
        if archivos:
            src = archivos[-1]
            if carpeta == CARPETA_REPORTES_SIESA:
                dst = CARPETA_ENTRADA / src.name
                if not dst.exists():
                    shutil.copy2(src, dst)
                    print(f"  Copiado desde reportes SIESA: {src.name}")
                return dst
            return src

    raise FileNotFoundError(
        "No se encontro archivo Excel. Coloca el archivo en 'entrada/'"
    )


# ============================================================
# 2. VALIDAR ESTRUCTURA
# ============================================================
def validar_estructura(ruta):
    errores = []
    xls = pd.ExcelFile(ruta)
    sheet = HOJA_SIESA if HOJA_SIESA in xls.sheet_names else xls.sheet_names[0]
    try:
        df = pd.read_excel(ruta, sheet_name=sheet, nrows=0)
    except Exception as e:
        return False, [f"No se pudo leer el archivo: {e}"], sheet

    columnas_siesa = [c.strip() for c in df.columns]
    COLUMNAS_ESENCIALES = ["Fecha", "Razon social cliente factura", "Valor pendiente subtotal"]
    faltantes = [c for c in COLUMNAS_ESENCIALES if c not in columnas_siesa]

    if faltantes:
        errores.append(
            f"ERROR DE VALIDACION\n"
            f"Archivo: {ruta.name}\n"
            f"Campos faltantes (esenciales): {', '.join(faltantes)}\n"
            f"Columnas encontradas: {', '.join(columnas_siesa[:20])}\n"
            f"La Base_Maestra_Pedidos NO fue modificada."
        )
        return False, errores, sheet

    return True, [], sheet


# ============================================================
# 3. CARGAR Y LIMPIAR
# ============================================================
def cargar_y_limpiar(ruta, sheet_name=None):
    if sheet_name is None:
        xls = pd.ExcelFile(ruta)
        sheet_name = HOJA_SIESA if HOJA_SIESA in xls.sheet_names else xls.sheet_names[0]
    df = pd.read_excel(ruta, sheet_name=sheet_name)
    cols = [c for c in COLUMNAS_REQUERIDAS if c in df.columns]
    df = df[cols].copy() if cols else df.copy()

    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype(str).str.strip().replace("nan", "").replace("None", "")

    if "Fecha" in df.columns:
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")

    for c in COLUMNAS_NUMERICAS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    df = df.dropna(how="all").reset_index(drop=True)
    return df


# ============================================================
# 4. CAMPOS AUXILIARES
# ============================================================
def generar_campos_auxiliares(df):
    df["Anio"] = 0
    df["Mes"] = 0
    df["Nombre_Mes"] = ""
    df["Trimestre"] = 0
    df["Semana"] = 0
    if "Fecha" in df.columns:
        f = df["Fecha"]
        mask = f.notna()
        df.loc[mask, "Anio"] = f.loc[mask].dt.year.astype(int)
        df.loc[mask, "Mes"] = f.loc[mask].dt.month.astype(int)
        df.loc[mask, "Nombre_Mes"] = f.loc[mask].dt.month.map(MESES_ES).fillna("")
        df.loc[mask, "Trimestre"] = f.loc[mask].dt.quarter.astype(int)
        df.loc[mask, "Semana"] = f.loc[mask].dt.isocalendar().week.astype(int)
    return df


# ============================================================
# 5. LLAVE UNICA (a nivel de linea/item)
# ============================================================
def generar_llave(df):
    llaves = []
    for c in LLAVE_UNICA:
        if c in df.columns:
            llaves.append(df[c].astype(str).str.strip())
        else:
            llaves.append(pd.Series([""] * len(df)))

    # Incluye cantidad para diferenciar lineas identicas con distinta cantidad
    if "Cant. pedida" in df.columns:
        llaves.append(df["Cant. pedida"].astype(str))

    df["_llave"] = llaves[0]
    for p in llaves[1:]:
        df["_llave"] = df["_llave"] + "||" + p
    return df


# ============================================================
# 6. DEDUPLICACION
# ============================================================
def deduplicar(df_nuevo, df_existente=None):
    if df_existente is None or df_existente.empty:
        return df_nuevo, pd.DataFrame()

    llaves_exist = set(df_existente["_llave"].unique())
    mask_nuevo = ~df_nuevo["_llave"].isin(llaves_exist)
    df_agregar = df_nuevo[mask_nuevo].copy()
    df_duplicados = df_nuevo[~mask_nuevo].copy()
    return df_agregar, df_duplicados


# ============================================================
# 7. BACKUP Y ACTUALIZACION DE BASE MAESTRA
# ============================================================
def respaldar_base():
    if not ARCHIVO_BASE.exists():
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = CARPETA_BACKUPS / f"Base_Maestra_Pedidos_{ts}.parquet"
    shutil.copy2(ARCHIVO_BASE, backup)
    # Mantener solo los 5 backups mas recientes
    backups = sorted(CARPETA_BACKUPS.glob("Base_Maestra_Pedidos_*.parquet"))
    for b in backups[:-5]:
        b.unlink()


def actualizar_base_maestra(df_agregar, df_nuevo_completo):
    ARCHIVO_BASE.parent.mkdir(parents=True, exist_ok=True)
    df_existente = pd.DataFrame()
    if ARCHIVO_BASE.exists():
        df_existente = pd.read_parquet(ARCHIVO_BASE)

    if df_existente.empty:
        df_final = df_nuevo_completo.copy()
    else:
        respaldar_base()
        df_final = pd.concat([df_existente, df_agregar], ignore_index=True)

    if "Fecha" in df_final.columns:
        df_final = df_final.sort_values(["Fecha", "Nro documento"]).reset_index(drop=True)

    from time import sleep
    for intento in range(3):
        try:
            df_final.to_parquet(ARCHIVO_BASE, index=False)
            break
        except PermissionError as e:
            if intento < 2:
                sleep(1)
                continue
            raise RuntimeError(f"Archivo bloqueado tras {intento+1} intentos: {e}")

    ruta_xlsx = CARPETA_BASE / "Base_Maestra_Pedidos.xlsx"
    for intento in range(3):
        try:
            df_final.to_excel(ruta_xlsx, index=False, engine="openpyxl")
            break
        except PermissionError as e:
            if intento < 2:
                sleep(1)
                continue
            print(f"  Advertencia: No se pudo escribir Excel (archivo abierto?): {e}")

    return df_final


# ============================================================
# 8. REPORTES POR ASESOR (filtro sobre tabla maestra)
# ============================================================
def generar_reportes_asesores(df):
    for asesor in sorted(df["Nombre vendedor"].dropna().unique()):
        if not asesor.strip():
            continue
        da = df[df["Nombre vendedor"] == asesor].copy()

        with pd.ExcelWriter(CARPETA_ASESORES / f"{asesor}.xlsx", engine="openpyxl") as w:
            # Resumen
            resumen = pd.DataFrame({
                "Indicador": [
                    "Total Pedidos", "Valor Total", "Cantidad Total",
                    "Clientes", "Valor Pendiente", "Cantidad Pendiente",
                    "Comprometido", "% Cumplimiento"
                ],
                "Valor": [
                    da["Nro documento"].nunique(),
                    da["Valor pendiente subtotal"].sum(),
                    da["Cant. pedida"].sum(),
                    da["Razon social cliente factura"].nunique(),
                    da["Valor pendiente subtotal"].sum(),
                    da["Cant. pendiente"].sum(),
                    da["V.COMPROMETIDO"].sum(),
                    f"{(da['V.COMPROMETIDO'].sum()/da['Valor pendiente subtotal'].sum()*100) if da['Valor pendiente subtotal'].sum() else 0:.1f}%"
                ]
            })
            resumen.to_excel(w, sheet_name="Resumen", index=False)

            # Clientes
            clientes = da.groupby("Razon social cliente factura").agg(
                Pedidos=("Nro documento", "nunique"),
                Cantidad=("Cant. pedida", "sum"),
                Valor=("Valor pendiente subtotal", "sum"),
                Comprometido=("V.COMPROMETIDO", "sum")
            ).sort_values("Valor", ascending=False).reset_index()
            tv = clientes["Valor"].sum()
            clientes["% Participacion"] = (clientes["Valor"] / tv * 100).round(2) if tv else 0
            clientes["% Acumulado"] = clientes["% Participacion"].cumsum()
            clientes.insert(0, "Ranking", range(1, len(clientes) + 1))
            clientes.to_excel(w, sheet_name="Clientes", index=False)

            # Canal
            canal = da.groupby("CANAL DISTRIBUCION").agg(
                Cantidad=("Cant. pedida", "sum"),
                Valor=("Valor pendiente subtotal", "sum"),
                Comprometido=("V.COMPROMETIDO", "sum")
            ).sort_values("Valor", ascending=False).reset_index()
            tc = canal["Valor"].sum()
            canal["% Participacion"] = (canal["Valor"] / tc * 100).round(2) if tc else 0
            canal.to_excel(w, sheet_name="Canal", index=False)

            # Estructura (LINEA)
            estructura = da.groupby("LINEA").agg(
                Cantidad=("Cant. pedida", "sum"),
                Valor=("Valor pendiente subtotal", "sum")
            ).sort_values("Valor", ascending=False).reset_index()
            estructura.to_excel(w, sheet_name="Estructura", index=False)

            # Historico por año
            historico = da.groupby("Anio").agg(
                Pedidos=("Nro documento", "nunique"),
                Valor=("Valor pendiente subtotal", "sum"),
                Cantidad=("Cant. pedida", "sum"),
                Comprometido=("V.COMPROMETIDO", "sum")
            ).reset_index().sort_values("Anio")
            historico.to_excel(w, sheet_name="Historico", index=False)


# ============================================================
# 9. INFORME DE GERENCIA
# ============================================================
def generar_informe_gerencia(df):
    vp_total = df["Valor pendiente subtotal"].sum()
    vc_total = df["V.COMPROMETIDO"].sum()

    # Participacion construccion
    mask_cnst = df["CANAL DISTRIBUCION"] == "CNST - CONSTRUCCION"
    part_const = (df[mask_cnst]["Valor pendiente subtotal"].sum() / vp_total * 100) if vp_total else 0

    with pd.ExcelWriter(CARPETA_GERENCIA / "Informe_Gerencia.xlsx", engine="openpyxl") as w:
        # KPI Dashboard
        kpis = pd.DataFrame({
            "Indicador": [
                "Valor Total Pendiente", "Valor Comprometido", "% Cumplimiento",
                "Numero de Pedidos", "Cantidad Pedida", "Cantidad Pendiente",
                "Total Clientes", "Total Asesores",
                "Participacion Construccion %", "Rango Fechas"
            ],
            "Valor": [
                f"${vp_total:,.0f}",
                f"${vc_total:,.0f}",
                f"{(vc_total/vp_total*100) if vp_total else 0:.1f}%",
                df["Nro documento"].nunique(),
                f"{df['Cant. pedida'].sum():,.0f}",
                f"{df['Cant. pendiente'].sum():,.0f}",
                df["Razon social cliente factura"].nunique(),
                df["Nombre vendedor"].nunique(),
                f"{part_const:.1f}%",
                f"{df['Fecha'].min().strftime('%Y-%m-%d') if df['Fecha'].notna().any() else 'N/A'} a "
                f"{df['Fecha'].max().strftime('%Y-%m-%d') if df['Fecha'].notna().any() else 'N/A'}"
            ]
        })
        kpis.to_excel(w, sheet_name="KPIs", index=False)

        # Canales
        canales = df.groupby("CANAL DISTRIBUCION").agg(
            Valor=("Valor pendiente subtotal", "sum"),
            Comprometido=("V.COMPROMETIDO", "sum")
        ).reset_index()
        tc = canales["Valor"].sum()
        canales["% Participacion"] = (canales["Valor"] / tc * 100).round(2) if tc else 0
        canales["% Comprometido"] = (canales["Comprometido"] / canales["Valor"] * 100).round(2)
        canales.to_excel(w, sheet_name="Canales", index=False)

        # Ranking asesores
        rank_asesores = df.groupby("Nombre vendedor").agg(
            Valor=("Valor pendiente subtotal", "sum"),
            Pedidos=("Nro documento", "nunique"),
            Clientes=("Razon social cliente factura", "nunique"),
            Comprometido=("V.COMPROMETIDO", "sum")
        ).sort_values("Valor", ascending=False).reset_index()
        ta = rank_asesores["Valor"].sum()
        rank_asesores["% Participacion"] = (rank_asesores["Valor"] / ta * 100).round(2) if ta else 0
        rank_asesores.to_excel(w, sheet_name="Ranking_Asesores", index=False)

        # Pareto clientes
        pareto = df.groupby("Razon social cliente factura").agg(
            Valor=("Valor pendiente subtotal", "sum"),
            Pedidos=("Nro documento", "nunique"),
            Comprometido=("V.COMPROMETIDO", "sum")
        ).sort_values("Valor", ascending=False).reset_index()
        tp = pareto["Valor"].sum()
        pareto["% Participacion"] = (pareto["Valor"] / tp * 100).round(2) if tp else 0
        pareto["% Acumulado"] = pareto["% Participacion"].cumsum()
        pareto.insert(0, "Ranking", range(1, len(pareto) + 1))
        pareto.to_excel(w, sheet_name="Pareto_Clientes", index=False)

        # Evolucion anual
        evolucion = df.groupby("Anio").agg(
            Pedidos=("Nro documento", "nunique"),
            Valor=("Valor pendiente subtotal", "sum"),
            Cantidad=("Cant. pedida", "sum"),
            Comprometido=("V.COMPROMETIDO", "sum")
        ).reset_index().sort_values("Anio")
        evolucion.to_excel(w, sheet_name="Evolucion_Anual", index=False)

        # Comparativo semanal
        semana_max = df["Semana"].max()
        comparativo = df[df["Semana"].isin([semana_max, semana_max - 1])]
        if not comparativo.empty:
            comp = comparativo.groupby(["Anio", "Semana"]).agg(
                Valor=("Valor pendiente subtotal", "sum"),
                Pedidos=("Nro documento", "nunique")
            ).reset_index().sort_values(["Anio", "Semana"])
            comp.to_excel(w, sheet_name="Comparativo_Semanal", index=False)

        # Participacion construccion detallado
        cnst = df[mask_cnst].groupby(["Anio", "Nombre vendedor"]).agg(
            Valor=("Valor pendiente subtotal", "sum")
        ).reset_index()
        if not cnst.empty:
            cnst.to_excel(w, sheet_name="Construccion_Detalle", index=False)


# ============================================================
# 10. PREPARAR DATOS PARA DASHBOARD (cache, no fuente de verdad)
# ============================================================
def preparar_dashboard(df):
    CARPETA_DASHBOARD.mkdir(parents=True, exist_ok=True)

    df.to_parquet(CARPETA_DASHBOARD / "datos_completos.parquet", index=False)
    df.to_csv(CARPETA_DASHBOARD / "datos_completos.csv", index=False, encoding="utf-8-sig")

    mask_cnst = df["CANAL DISTRIBUCION"] == "CNST - CONSTRUCCION"
    agg = {"Cant. pedida": "sum", "Cant. comprom.": "sum",
           "Cant. pendiente": "sum", "Valor pendiente subtotal": "sum",
           "V.COMPROMETIDO": "sum"}

    # Con Razon Social (solo CNST)
    crs = df[mask_cnst].groupby("Razon social cliente factura", as_index=False).agg(agg)
    crs = crs.sort_values("Valor pendiente subtotal", ascending=False).reset_index(drop=True)
    crs.to_csv(CARPETA_DASHBOARD / "con_razon_social.csv", index=False, encoding="utf-8-sig")

    # Pareto Global
    pg = df.groupby("Razon social cliente factura", as_index=False).agg(agg)
    pg = pg.sort_values("Valor pendiente subtotal", ascending=False).reset_index(drop=True)
    t = pg["Valor pendiente subtotal"].sum()
    pg["% Participacion"] = (pg["Valor pendiente subtotal"] / t * 100).round(2) if t else 0
    pg["% Acumulado"] = pg["% Participacion"].cumsum()
    pg.to_csv(CARPETA_DASHBOARD / "pareto_global.csv", index=False, encoding="utf-8-sig")

    # Pareto Construccion
    pc = df[mask_cnst].groupby("Razon social cliente factura", as_index=False).agg(agg)
    pc = pc.sort_values("Valor pendiente subtotal", ascending=False).reset_index(drop=True)
    tc = pc["Valor pendiente subtotal"].sum()
    pc["% Participacion"] = (pc["Valor pendiente subtotal"] / tc * 100).round(2) if tc else 0
    pc["% Acumulado"] = pc["% Participacion"].cumsum()
    pc.to_csv(CARPETA_DASHBOARD / "pareto_construccion.csv", index=False, encoding="utf-8-sig")

    # Informe Canales
    inf = df.groupby("CANAL DISTRIBUCION", as_index=False).agg(agg)
    inf = inf.sort_values("Valor pendiente subtotal", ascending=False).reset_index(drop=True)
    total = df[list(agg.keys())].sum()
    total["CANAL DISTRIBUCION"] = "TOTAL GENERAL"
    inf = pd.concat([inf, total.to_frame().T], ignore_index=True)
    inf.to_csv(CARPETA_DASHBOARD / "informe_canales.csv", index=False, encoding="utf-8-sig")

    return {
        "datos_completos": df,
        "con_razon_social": crs,
        "pareto_global": pg,
        "pareto_construccion": pc,
        "informe_canales": inf,
    }


# ============================================================
# 11. LOG DE PROCESAMIENTO
# ============================================================
def registrar_log(archivo, encontrados, nuevos, duplicados,
                  total_base, errores=None):
    now = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    estado = "PROCESADO CORRECTAMENTE" if not errores else "ERROR"
    archivo_nombre = Path(archivo).name if archivo else "N/A"

    lineas = [
        "=" * 56,
        f"  Archivo procesado: {archivo_nombre}",
        f"  Fecha de procesamiento: {now}",
        f"  Registros encontrados: {encontrados}",
    ]
    if nuevos is not None:
        lineas.append(f"  Registros nuevos: {nuevos}")
    if duplicados is not None:
        lineas.append(f"  Registros duplicados: {duplicados}")
    lineas.append(f"  Total Base Maestra: {total_base}")
    lineas.append(f"  Estado: {estado}")
    if errores:
        lineas.append(f"  ERRORES:")
        for e in errores:
            lineas.append(f"    {e}")
    lineas.append("")

    CARPETA_LOGS.mkdir(parents=True, exist_ok=True)
    with open(ARCHIVO_LOG, "a", encoding="utf-8") as f:
        f.write("\n".join(lineas))

    generar_log_json(archivo_nombre, now, encontrados, nuevos, duplicados, total_base, errores)


def generar_log_json(archivo, fecha, encontrados, nuevos, duplicados, total_base, errores):
    log_json = CARPETA_LOGS / "procesamiento.json"
    registros = []
    if log_json.exists():
        with open(log_json, "r", encoding="utf-8") as f:
            try:
                registros = json.load(f)
            except:
                registros = []
    registros.append({
        "archivo": archivo,
        "fecha": fecha,
        "encontrados": encontrados,
        "nuevos": nuevos,
        "duplicados": duplicados,
        "total_base": total_base,
        "errores": errores,
        "estado": "OK" if not errores else "ERROR"
    })
    with open(log_json, "w", encoding="utf-8") as f:
        json.dump(registros, f, indent=2, ensure_ascii=False)


# ============================================================
# ORQUESTADOR PRINCIPAL
# ============================================================
def procesar(ruta_archivo=None):
    print(f"\n{'='*50}")
    print(f"  PROCESO AUTOMATIZADO DE PEDIDOS SIESA")
    print(f"  Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")

    errores = None
    stats = {"archivo": "", "encontrados": 0, "nuevos": 0,
             "duplicados": 0, "total_base": 0}

    try:
        # 1. Detectar
        ruta = detectar_archivo(ruta_archivo)
        stats["archivo"] = str(ruta)
        print(f"\n[1/9] Archivo detectado: {ruta.name}")

        # 2. Validar
        print(f"\n[2/9] Validando estructura...")
        valido, errores_val, sheet_name = validar_estructura(ruta)
        if not valido:
            raise ValueError(errores_val[0])
        print(f"  Estructura valida (hoja: {sheet_name})")

        # 3. Cargar y limpiar
        print(f"\n[3/9] Cargando y limpiando datos...")
        df = cargar_y_limpiar(ruta, sheet_name)
        stats["encontrados"] = len(df)
        print(f"  {len(df)} registros cargados")

        # 4. Campos auxiliares
        print(f"\n[4/9] Generando campos auxiliares...")
        df = generar_campos_auxiliares(df)
        print(f"  Anios: {sorted(df['Anio'].unique())}")
        if "CANAL DISTRIBUCION" in df.columns:
            print(f"  Canales: {list(df['CANAL DISTRIBUCION'].unique())}")

        # 5. Llave unica
        print(f"\n[5/9] Generando llave unica por linea...")
        df = generar_llave(df)

        # 6. Deduplicar
        print(f"\n[6/9] Comparando contra Base_Maestra_Pedidos...")
        df_existente = pd.DataFrame()
        if ARCHIVO_BASE.exists():
            df_existente = pd.read_parquet(ARCHIVO_BASE)

        df_agregar, df_duplicados = deduplicar(df, df_existente)
        stats["nuevos"] = len(df_agregar)
        stats["duplicados"] = len(df_duplicados)
        print(f"  Nuevos: {len(df_agregar)} | Duplicados: {len(df_duplicados)}")

        # 7. Actualizar base maestra
        print(f"\n[7/9] Actualizando Base_Maestra_Pedidos...")
        if stats["nuevos"] > 0 or df_existente.empty:
            df_final = actualizar_base_maestra(df_agregar, df)
            stats["total_base"] = len(df_final)
            print(f"  Base actualizada: {len(df_final)} registros totales")
        else:
            df_final = df_existente
            stats["total_base"] = len(df_final)
            respaldar_base()
            df_final.to_parquet(ARCHIVO_BASE, index=False)
            CARPETA_BASE.joinpath("Base_Maestra_Pedidos.xlsx").unlink(missing_ok=True)
            df_final.to_excel(CARPETA_BASE / "Base_Maestra_Pedidos.xlsx", index=False, engine="openpyxl")
            print(f"  Sin cambios: {len(df_final)} registros")

        # 8. Reportes
        print(f"\n[8/9] Generando reportes desde tabla maestra...")
        print(f"  Asesores...")
        generar_reportes_asesores(df_final)
        print(f"  Informe Gerencia...")
        generar_informe_gerencia(df_final)

        print(f"\n{'='*50}")
        print(f"  PROCESO COMPLETADO EXITOSAMENTE")
        print(f"{'='*50}")

    except Exception as e:
        errores = str(e)
        print(f"\n  ERROR: {errores}")
        print(f"  La Base_Maestra_Pedidos NO fue modificada.")

    finally:
        registrar_log(
            stats["archivo"], stats["encontrados"],
            stats["nuevos"], stats["duplicados"],
            stats["total_base"],
            [errores] if errores else None,
        )

    if errores:
        raise RuntimeError(errores)
    print(f"  Dashboard listo en: http://127.0.0.1:8503")


if __name__ == "__main__":
    procesar()
