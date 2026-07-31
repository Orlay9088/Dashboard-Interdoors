from pathlib import Path

PROYECTO = Path(__file__).parent

CARPETA_ENTRADA = PROYECTO / "entrada"
CARPETA_BASE = PROYECTO / "base"
CARPETA_ASESORES = PROYECTO / "salida" / "asesores"
CARPETA_GERENCIA = PROYECTO / "salida" / "gerencia"
CARPETA_DASHBOARD = PROYECTO / "dashboard_data"
CARPETA_LOGS = PROYECTO / "logs"
CARPETA_ACTIVOS = Path("/mnt/c/Users/USUARIO/Desktop/Proyectos Activos")
if not CARPETA_ACTIVOS.exists():
    CARPETA_ACTIVOS = Path(r"C:\Users\USUARIO\Desktop\Proyectos Activos")

CARPETA_REPORTES_SIESA = CARPETA_ACTIVOS / "Reportes" / "Reportes de ventas - Pedidos"

ARCHIVO_BASE = CARPETA_BASE / "Base_Maestra_Pedidos.parquet"
ARCHIVO_LOG = CARPETA_LOGS / "procesamiento.log"

RUTA_PRESUPUESTO = PROYECTO / "presupuesto por asesor.xlsx"
RUTA_PRESUPUESTO_ASESORES = CARPETA_ACTIVOS / "presupuesto por asesor.xlsx"
RUTA_PRESUPUESTO_COMPANY = CARPETA_ACTIVOS / "Ptto 2026 (1).xlsx"

HOJA_SIESA = "Tabla principal"

COLUMNAS_REQUERIDAS = [
    "Fecha", "Estado movto.", "Nombre vendedor", "Vendedor",
    "Nro documento", "Cliente despacho", "Desc. sucursal despacho",
    "Referencia", "Cant. pedida", "Cant. pendiente", "Cant. comprom.",
    "Valor pendiente subtotal", "V.UNIDAD", "V.COMPROMETIDO",
    "Valor pendiente neto", "Valor subtotal local", "Desc. item",
    "LINEA", "SUB-LINEA", "CANAL DISTRIBUCION", "ESTADO",
    "Razon social cliente factura"
]

COLUMNAS_NUMERICAS = [
    "Cant. pedida", "Cant. pendiente", "Cant. comprom.",
    "Valor pendiente subtotal", "V.COMPROMETIDO",
    "Valor pendiente neto", "Valor subtotal local", "V.UNIDAD"
]

LLAVE_UNICA = ["Nro documento", "Referencia", "Cliente despacho", "Vendedor"]

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

for p in [CARPETA_ENTRADA, CARPETA_BASE, CARPETA_ASESORES,
          CARPETA_GERENCIA, CARPETA_DASHBOARD, CARPETA_LOGS]:
    p.mkdir(parents=True, exist_ok=True)
