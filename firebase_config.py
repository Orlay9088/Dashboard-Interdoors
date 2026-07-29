import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from pathlib import Path
import pandas as pd

_initialized = False
_db = None

RENDER_SECRET_PATH = Path("/etc/secrets/firebase-key.json")
LOCAL_KEY_PATH = Path(__file__).parent / "firebase-key.json"
LOCAL_BASE = Path(__file__).parent / "base"
LOCAL_PARQUET = {
    "pedidos": LOCAL_BASE / "pedidos.parquet",
    "facturas": LOCAL_BASE / "facturas.parquet",
    "inventario": LOCAL_BASE / "inventario.parquet",
}


def save_local(df, tipo):
    LOCAL_BASE.mkdir(parents=True, exist_ok=True)
    path = LOCAL_PARQUET.get(tipo)
    if path:
        df.to_parquet(path, index=False)
    return path


def load_local(tipo):
    path = LOCAL_PARQUET.get(tipo)
    if path and path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


def try_save(df, tipo, filename=""):
    save_local(df, tipo)
    return len(df)


def try_load(tipo):
    return load_local(tipo), "local"


def get_metadata():
    return {}


def set_metadata(doc_id, data):
    pass
