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

def get_db():
    global _initialized, _db
    if _initialized:
        return _db
    cred = None
    for path in [RENDER_SECRET_PATH, LOCAL_KEY_PATH]:
        if path.exists():
            cred = credentials.Certificate(str(path))
            break
    if cred is None:
        raw = os.environ.get("FIREBASE_KEY_JSON")
        if raw:
            cred = credentials.Certificate(json.loads(raw))
    if cred is None:
        raise RuntimeError("No se encontro firebase-key.json (buscado en /etc/secrets/, raiz del proyecto, y FIREBASE_KEY_JSON)")
    app = firebase_admin.initialize_app(cred)
    _db = firestore.client()
    _initialized = True
    return _db


def save_to_firestore(df, collection, batch_size=500):
    try:
        db = get_db()
    except Exception:
        return 0
    docs = df.to_dict(orient="records")
    total = len(docs)
    for i in range(0, total, batch_size):
        batch = db.batch()
        for doc in docs[i : i + batch_size]:
            batch.set(db.collection(collection).document(), doc)
        batch.commit()
    return total


def load_from_firestore(collection, filters=None):
    try:
        db = get_db()
    except Exception:
        return pd.DataFrame()
    ref = db.collection(collection)
    if filters:
        for field, op_val in filters.items():
            op, val = op_val
            ref = ref.where(field, op, val)
    docs = list(ref.stream())
    records = [d.to_dict() for d in docs]
    return pd.DataFrame(records) if records else pd.DataFrame()


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
    local_path = save_local(df, tipo)
    n_local = len(df)
    backend = "local"
    try:
        count = save_to_firestore(df, tipo)
        backend = "firestore"
        n_local = count
    except Exception as e:
        print(f"Firestore sync failed (quota exceeded?): {e}")

    set_metadata("ultima_actualizacion", {
        "fecha": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tipo": tipo, "registros": n_local, "archivo": filename,
        "backend": backend,
    })
    print(f"Saved {n_local} records ({backend}): {local_path}")
    return n_local


def try_load(tipo):
    df = load_local(tipo)
    if not df.empty:
        return df, "local"
    try:
        df = load_from_firestore(tipo)
        if not df.empty:
            return df, "firestore"
    except Exception:
        pass
    return pd.DataFrame(), "none"


def get_metadata():
    try:
        db = get_db()
        docs = list(db.collection("metadata").stream())
        if docs:
            return {d.id: d.to_dict() for d in docs}
    except Exception:
        pass
    return {}


def set_metadata(doc_id, data):
    try:
        db = get_db()
        db.collection("metadata").document(doc_id).set(data)
    except Exception:
        pass

