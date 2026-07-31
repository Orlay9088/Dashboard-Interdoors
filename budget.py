import pandas as pd
import numpy as np
import re
from pathlib import Path

ASESOR_NAMES = [
    "Mateo Posada", "Eliana Gonzalez", "Leonardo Zuleta",
    "Ines Maria Sanchez", "Laura Ochoa", "Karol", "Yudi",
]
MONTHS_ES = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
             "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]

MES_MAP = {m: i+1 for i, m in enumerate(MONTHS_ES)}


def _parse_valor(raw):
    if pd.isna(raw):
        return 0
    if isinstance(raw, (int, float, np.number)):
        return float(raw)
    s = str(raw).strip()
    s = re.sub(r"[^\d.,\-]", "", s)
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0


def cargar_presupuesto_asesores(ruta):
    if not Path(ruta).exists():
        return {}
    df = pd.read_excel(ruta, sheet_name=0, header=None)
    budget = {}
    col_pairs = [(0, 1), (3, 4), (6, 7), (9, 10), (12, 13), (15, 16), (18, 19)]
    for idx, (mes_col, val_col) in enumerate(col_pairs):
        name = ASESOR_NAMES[idx] if idx < len(ASESOR_NAMES) else f"Asesor_{idx}"
        advisor_budget = {"meses": {}, "anual": 0}
        for r in range(4, 17):
            mes_raw = df.iloc[r, mes_col]
            val_raw = df.iloc[r, val_col]
            if pd.isna(mes_raw):
                continue
            mes_str = str(mes_raw).strip().upper()
            mes_num = MES_MAP.get(mes_str)
            if mes_num is None:
                continue
            val = _parse_valor(val_raw)
            advisor_budget["meses"][mes_num] = val
        # total annual
        annual = 0
        for r in range(4, 19):
            val = _parse_valor(df.iloc[r, val_col])
            annual = max(annual, val)
        advisor_budget["anual"] = annual
        budget[name] = advisor_budget
    return budget


def cargar_ptto_company(ruta):
    if not Path(ruta).exists():
        return {}
    df = pd.read_excel(ruta, sheet_name=0, header=None)
    result = {}
    for r in range(3, 15):
        mes_raw = df.iloc[r, 1]
        real_raw = df.iloc[r, 2]
        ppto_raw = df.iloc[r, 3]
        cumpl_raw = df.iloc[r, 4]
        if pd.isna(mes_raw):
            continue
        mes_str = str(mes_raw).strip().upper()
        if mes_str in MES_MAP or mes_str.startswith("SEMESTRE"):
            result[mes_str] = {
                "real": _parse_valor(real_raw),
                "ppto": _parse_valor(ppto_raw),
                "cumpl": _parse_valor(cumpl_raw),
            }
    return result


def get_budget_for(name, budgets):
    if not budgets:
        return 0
    name = str(name).strip()
    if not name:
        return 0
    name_upper = name.upper()
    name_words = set(name_upper.split())
    for budget_name in sorted(budgets, key=lambda x: -len(x)):
        bn_upper = budget_name.upper()
        if bn_upper == name_upper:
            return budgets[budget_name]["anual"]
        bn_words = set(bn_upper.split())
        if bn_words.issubset(name_words):
            return budgets[budget_name]["anual"]
        if name_words.issubset(bn_words):
            return budgets[budget_name]["anual"]
        common = bn_words & name_words
        if len(common) >= 2 and len(common) >= len(bn_words) * 0.7:
            return budgets[budget_name]["anual"]
    return 0


def get_monthly_budget(name, mes, budgets):
    if not budgets:
        return 0
    name = str(name).strip()
    if not name:
        return 0
    name_upper = name.upper()
    name_words = set(name_upper.split())
    for budget_name in sorted(budgets, key=lambda x: -len(x)):
        bn_upper = budget_name.upper()
        if bn_upper == name_upper:
            return budgets[budget_name]["meses"].get(mes, 0)
        bn_words = set(bn_upper.split())
        if bn_words.issubset(name_words) or name_words.issubset(bn_words):
            return budgets[budget_name]["meses"].get(mes, 0)
        common = bn_words & name_words
        if len(common) >= 2 and len(common) >= len(bn_words) * 0.7:
            return budgets[budget_name]["meses"].get(mes, 0)
    return 0
