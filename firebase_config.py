import os
import json
from datetime import date, datetime
from pathlib import Path
import pandas as pd

LOCAL_BASE = Path(__file__).parent / "base"
COUNTER_FILE = LOCAL_BASE / ".sync_counter.json"
CACHE_FILE = LOCAL_BASE / ".cache_meta.json"
CLEANUP_FILE = LOCAL_BASE / ".cleanup_log.json"
META_FILE = LOCAL_BASE / ".upload_meta.json"
SKIP_FIRESTORE_FILE = LOCAL_BASE / ".skip_firestore"

LOCAL_PARQUET = {
    "pedidos": LOCAL_BASE / "pedidos.parquet",
    "facturas": LOCAL_BASE / "facturas.parquet",
    "inventario": LOCAL_BASE / "inventario.parquet",
}
LAST_FILES_JSON = LOCAL_BASE / ".last_files.json"

MAX_SYNCS_PER_DAY = 3
MAX_DOCS_PER_TYPE = 3
CACHE_TTL_HOURS = 24


def _load_json(path, default=None):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default if default is not None else {}


def _save_json(path, data):
    LOCAL_BASE.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def save_last_file(tipo, filename):
    data = _load_json(LAST_FILES_JSON, {"pedidos": "", "facturas": "", "inventario": ""})
    data[tipo] = filename
    _save_json(LAST_FILES_JSON, data)


def get_last_files():
    return _load_json(LAST_FILES_JSON, {"pedidos": "", "facturas": "", "inventario": ""})


def _load_counter():
    if COUNTER_FILE.exists():
        with open(COUNTER_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"date": "", "count": 0}


def _save_counter(data):
    LOCAL_BASE.mkdir(parents=True, exist_ok=True)
    with open(COUNTER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _use_firestore_sync():
    try:
        c = _load_counter()
        today = str(date.today())
        if c.get("date") != today:
            c = {"date": today, "count": 0}
        if c["count"] < MAX_SYNCS_PER_DAY:
            c["count"] += 1
            _save_counter(c)
            return True
        return False
    except Exception:
        return False


_firestore_app = None
_firestore_db = None
_firestore_failed = False


def _firestore_client():
    global _firestore_app, _firestore_db, _firestore_failed
    if _firestore_failed:
        return None, None
    if _firestore_app and _firestore_db:
        return _firestore_app, _firestore_db
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        if firebase_admin._apps:
            _firestore_app = list(firebase_admin._apps.values())[0]
            _firestore_db = firestore.client()
            return _firestore_app, _firestore_db
        key = os.environ.get("FIREBASE_KEY_JSON")
        if key:
            cred = credentials.Certificate(json.loads(key))
        else:
            local = Path(__file__).parent / "firebase-key.json"
            render = Path("/etc/secrets/firebase-key.json")
            for p in [render, local]:
                if p.exists():
                    cred = credentials.Certificate(str(p))
                    break
            else:
                _firestore_failed = True
                return None, None
        _firestore_app = firebase_admin.initialize_app(cred)
        _firestore_db = firestore.client()
        return _firestore_app, _firestore_db
    except Exception:
        _firestore_failed = True
        return None, None


def save_local(df, tipo):
    LOCAL_BASE.mkdir(parents=True, exist_ok=True)
    path = LOCAL_PARQUET.get(tipo)
    if path:
        df.to_parquet(path, index=False)
        try:
            pd.read_parquet(path)
        except Exception:
            pass
    return path


def load_local(tipo, retries=3):
    import time
    path = LOCAL_PARQUET.get(tipo)
    for _ in range(retries):
        if path and path.exists():
            try:
                df = pd.read_parquet(path)
                if not df.empty:
                    return df
            except Exception:
                pass
        time.sleep(0.1)
    return pd.DataFrame()


def try_save(df, tipo, filename=""):
    n = len(df)
    save_local(df, tipo)
    save_upload_meta(tipo, filename, n)
    if SKIP_FIRESTORE_FILE.exists():
        SKIP_FIRESTORE_FILE.unlink()
    if _use_firestore_sync():
        try:
            save_to_firestore(df, tipo, filename)
            daily_cleanup(tipo)
        except Exception:
            pass
    if filename:
        save_last_file(tipo, filename)
    return n


def _firestore_available():
    if os.environ.get("FIREBASE_KEY_JSON"):
        return True
    if (Path(__file__).parent / "firebase-key.json").exists():
        return True
    if Path("/etc/secrets/firebase-key.json").exists():
        return True
    return False


def try_load(tipo):
    df = load_local(tipo)
    if not df.empty:
        return df, "local"
    if SKIP_FIRESTORE_FILE.exists():
        return pd.DataFrame(), "local"
    if not _firestore_available():
        return pd.DataFrame(), "local"
    df = load_from_firestore(tipo)
    if not df.empty:
        return df, "firestore"
    return pd.DataFrame(), "local"


def save_to_firestore(df, tipo, filename=""):
    """Guarda un DataFrame completo en un solo documento de Firestore."""
    app, db = _firestore_client()
    if not db:
        return 0

    n = len(df)
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    doc_id = f"upload_{now_str}"

    data_json = json.loads(df.to_json(orient="records", date_format="iso", force_ascii=False))
    meta = {
        "tipo": tipo,
        "filename": filename,
        "fecha": datetime.now().isoformat(),
        "registros": n,
        "columnas": list(df.columns),
        "data": data_json,
    }
    db.collection(tipo).document(doc_id).set(meta)
    return n


def load_from_firestore(tipo):
    """Carga el ultimo documento desde Firestore. 1 sola lectura."""
    app, db = _firestore_client()
    if not db:
        return pd.DataFrame()

    docs = (db.collection(tipo)
            .order_by("fecha", direction="DESCENDING")
            .limit(1)
            .stream())

    for doc in docs:
        meta = doc.to_dict()
        data = meta.get("data", [])
        columnas = meta.get("columnas", [])
        registros = meta.get("registros", 0)
        if not data and registros > 0:
            # Fallback: formato antiguo con subcolecciones
            return _load_from_firestore_legacy(db, tipo, doc.id, columnas)
        if data and columnas:
            df = pd.DataFrame(data, columns=columnas)
            if "_fecha" in df.columns:
                df["_fecha"] = pd.to_datetime(df["_fecha"], errors="coerce")
            return df
    return pd.DataFrame()


def _load_from_firestore_legacy(db, tipo, doc_id, columnas):
    """Fallback para documentos antiguos con subcoleccion records/."""
    try:
        records_list = (
            db.collection(tipo).document(doc_id)
            .collection("records")
            .order_by("__name__")
            .stream()
        )
        all_data = []
        for rec_doc in records_list:
            batch = rec_doc.to_dict().get("data", [])
            all_data.extend(batch)
        if all_data and columnas:
            df = pd.DataFrame(all_data, columns=columnas)
            if "_fecha" in df.columns:
                df["_fecha"] = pd.to_datetime(df["_fecha"], errors="coerce")
            return df
    except Exception:
        pass
    return pd.DataFrame()


def should_cleanup_now():
    """Verifica si pasaron 10 minutos desde la ultima limpieza."""
    log = _load_json(CLEANUP_FILE)
    last = log.get("last_cleanup", "")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
        return (datetime.now() - last_dt).total_seconds() > 600
    except Exception:
        return True


def daily_cleanup(tipo):
    """Elimina todos los documentos del tipo excepto los ultimos MAX_DOCS_PER_TYPE.
       Ejecuta la limpieza cada 10 minutos maximo."""
    if not should_cleanup_now():
        return 0

    app, db = _firestore_client()
    if not db:
        return 0

    docs = (db.collection(tipo)
            .order_by("fecha", direction="DESCENDING")
            .stream())

    all_docs = list(docs)
    if len(all_docs) <= MAX_DOCS_PER_TYPE:
        return 0

    deleted = 0
    for doc in all_docs[MAX_DOCS_PER_TYPE:]:
        _delete_doc_with_subcollections(db, tipo, doc.id)
        deleted += 1

    _save_json(CLEANUP_FILE, {"last_cleanup": datetime.now().isoformat()})
    return deleted


def _delete_doc_with_subcollections(db, collection, doc_id):
    """Elimina un documento y todas sus subcolecciones recursivamente."""
    doc_ref = db.collection(collection).document(doc_id)

    for sub in doc_ref.collections():
        for sub_doc in sub.stream():
            _delete_doc_with_subcollections(db, f"{collection}/{doc_id}/{sub.id}", sub_doc.id)

    doc_ref.delete()


def set_metadata(doc_id, data):
    """Guarda metadata en la coleccion _metadata de Firestore."""
    app, db = _firestore_client()
    if db:
        db.collection("_metadata").document(doc_id).set(data)


def is_cache_stale():
    if not CACHE_FILE.exists():
        return True
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            meta = json.load(f)
        ts = datetime.fromisoformat(meta["created"])
        return (datetime.now() - ts).total_seconds() > CACHE_TTL_HOURS * 3600
    except Exception:
        return True


def mark_cache_fresh():
    LOCAL_BASE.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({"created": datetime.now().isoformat()}, f)


def clear_local_cache():
    for path in LOCAL_PARQUET.values():
        if path.exists():
            path.unlink()
    for f in [COUNTER_FILE, CACHE_FILE, CLEANUP_FILE, META_FILE]:
        if f.exists():
            f.unlink()
    SKIP_FIRESTORE_FILE.touch()


def save_upload_meta(tipo, filename, records):
    """Guarda metadatos de cada upload para saber antiguedad de los datos."""
    meta = _load_json(META_FILE, {})
    meta[tipo] = {
        "fecha": datetime.now().isoformat(),
        "archivo": filename,
        "registros": records,
    }
    _save_json(META_FILE, meta)


def get_upload_age_hours(tipo):
    """Devuelve cuantas horas pasaron desde el ultimo upload del tipo."""
    meta = _load_json(META_FILE, {})
    info = meta.get(tipo, {})
    fecha_str = info.get("fecha", "")
    if not fecha_str:
        return None
    try:
        last_dt = datetime.fromisoformat(fecha_str)
        return (datetime.now() - last_dt).total_seconds() / 3600
    except Exception:
        return None


def get_metadata():
    info = {}
    for tipo in LOCAL_PARQUET:
        df = load_local(tipo)
        if not df.empty:
            info[tipo] = len(df)
    counter = _load_counter()
    remaining = MAX_SYNCS_PER_DAY - counter.get("count", 0)
    info["syncs_remaining"] = max(0, remaining)
    return info
