import os
import json
import base64
import io
import threading
from datetime import date, datetime
from pathlib import Path
import pandas as pd

LOCAL_BASE = Path(__file__).parent / "base"
COUNTER_FILE = LOCAL_BASE / ".sync_counter.json"
CACHE_FILE = LOCAL_BASE / ".cache_meta.json"
META_FILE = LOCAL_BASE / ".upload_meta.json"
SKIP_FIRESTORE_FILE = LOCAL_BASE / ".skip_firestore"

LOCAL_PARQUET = {
    "pedidos": LOCAL_BASE / "pedidos.parquet",
    "facturas": LOCAL_BASE / "facturas.parquet",
    "inventario": LOCAL_BASE / "inventario.parquet",
}
LAST_FILES_JSON = LOCAL_BASE / ".last_files.json"

MAX_SYNCS_PER_DAY = 3
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


MAX_FIRESTORE_CHUNK = 850_000
STALE_HOURS = 144
STALE_LUNES = True
UPDATE_HOUR = 8


def save_all_to_firestore():
    results = {}
    attempted = 0
    successful = 0
    for tipo in LOCAL_PARQUET:
        df = load_local(tipo)
        if df.empty:
            results[tipo] = (0, "sin datos")
            continue
        attempted += 1
        try:
            if not _firestore_available() or not _firestore_client()[1]:
                raise RuntimeError("Firebase no disponible: falta FIREBASE_KEY_JSON o el secreto de Render")
            saved = _save_firestore_chunked(df, tipo, get_last_files().get(tipo, ""))
            if saved != len(df):
                raise RuntimeError("Firebase no confirmo la escritura")
            successful += 1
            results[tipo] = (saved, "ok")
        except Exception as e:
            results[tipo] = (0, str(e)[:60])
    if attempted > 0 and successful == attempted and SKIP_FIRESTORE_FILE.exists():
        SKIP_FIRESTORE_FILE.unlink(missing_ok=True)
    return results


def load_all_from_firestore():
    results = {}
    successful = 0
    for tipo in LOCAL_PARQUET:
        df = _load_from_firestore_chunked(tipo)
        if df.empty:
            results[tipo] = (0, "sin datos en la nube")
            continue
        try:
            save_local(df, tipo)
            save_upload_meta(tipo, get_last_files().get(tipo, ""), len(df))
            successful += 1
            results[tipo] = (len(df), "ok")
        except Exception as e:
            results[tipo] = (0, str(e)[:60])
    if successful > 0 and SKIP_FIRESTORE_FILE.exists():
        SKIP_FIRESTORE_FILE.unlink(missing_ok=True)
    return results


def is_data_stale(tipo):
    age = get_upload_age_hours(tipo)
    if age is None:
        return False
    if age > STALE_HOURS:
        return True
    now = datetime.now()
    if STALE_LUNES and now.weekday() == 0 and now.hour >= UPDATE_HOUR:
        meta = _load_json(META_FILE, {})
        last_str = meta.get(tipo, {}).get("fecha", "")
        if last_str:
            try:
                last_dt = datetime.fromisoformat(last_str)
                if last_dt.date() < date.today():
                    return True
            except Exception:
                pass
    return False


def try_save(df, tipo, filename=""):
    n = len(df)
    save_local(df, tipo)
    save_upload_meta(tipo, filename, n)
    if filename:
        save_last_file(tipo, filename)
    return n


def _delete_firestore_chunks(tipo):
    _, db = _firestore_client()
    if not db:
        return
    try:
        docs = db.collection(f"{tipo}_chunks").stream(timeout=10)
        for doc in docs:
            doc.reference.delete()
    except Exception:
        pass


def _save_firestore_chunked(df, tipo, filename):
    _, db = _firestore_client()
    if not db:
        raise RuntimeError("Firebase no disponible: no hay cliente Firestore")
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    raw = base64.b64encode(buf.getvalue()).decode("ascii")
    chunks = [raw[i:i + MAX_FIRESTORE_CHUNK] for i in range(0, len(raw), MAX_FIRESTORE_CHUNK)]
    col_ref = db.collection(f"{tipo}_chunks")
    for idx, chunk in enumerate(chunks):
        col_ref.document(f"chunk_{idx}").set({"data": chunk}, timeout=10)
    col_ref.document("meta").set({"count": len(chunks), "filename": filename,
                                   "fecha": datetime.now().isoformat(),
                                   "registros": len(df), "columnas": list(df.columns)}, timeout=10)
    return len(df)


def try_load(tipo):
    df = load_local(tipo)
    if not df.empty:
        return df, "local"
    if SKIP_FIRESTORE_FILE.exists():
        return pd.DataFrame(), "local"
    if not _firestore_available():
        return pd.DataFrame(), "local"
    df = _load_from_firestore_chunked(tipo)
    if not df.empty:
        save_local(df, tipo)
        return df, "firestore"
    return pd.DataFrame(), "local"


def _load_from_firestore_chunked(tipo):
    _, db = _firestore_client()
    if not db:
        return pd.DataFrame()
    try:
        meta_doc = db.collection(f"{tipo}_chunks").document("meta").get(timeout=5)
        if not meta_doc.exists:
            return pd.DataFrame()
        count = meta_doc.to_dict().get("count", 0)
        if count <= 0:
            return pd.DataFrame()
        parts = []
        for idx in range(count):
            doc = db.collection(f"{tipo}_chunks").document(f"chunk_{idx}").get(timeout=5)
            if doc.exists:
                parts.append(doc.to_dict().get("data", ""))
        if not parts:
            return pd.DataFrame()
        raw = "".join(parts)
        buf = io.BytesIO(base64.b64decode(raw))
        df = pd.read_parquet(buf)
        if "_fecha" in df.columns:
            df["_fecha"] = pd.to_datetime(df["_fecha"], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


def _firestore_available():
    if os.environ.get("FIREBASE_KEY_JSON"):
        return True
    if (Path(__file__).parent / "firebase-key.json").exists():
        return True
    if Path("/etc/secrets/firebase-key.json").exists():
        return True
    return False


def save_to_firestore(df, tipo, filename=""):
    return _save_firestore_chunked(df, tipo, filename)


def load_from_firestore(tipo):
    return _load_from_firestore_chunked(tipo)


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
    clear_firestore_data()
    for path in LOCAL_PARQUET.values():
        if path.exists():
            path.unlink()
    for f in [COUNTER_FILE, CACHE_FILE, META_FILE, LAST_FILES_JSON]:
        if f.exists():
            f.unlink()
    SKIP_FIRESTORE_FILE.touch()


def clear_firestore_data():
    """Delete the current persisted dataset for every module."""
    _, db = _firestore_client()
    if not db:
        return
    for collection_name in [*LOCAL_PARQUET, *[f"{tipo}_chunks" for tipo in LOCAL_PARQUET], "metadata", "_metadata"]:
        try:
            for doc in db.collection(collection_name).stream(timeout=10):
                doc.reference.delete(timeout=10)
        except Exception:
            pass


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
    meta = _load_json(META_FILE, {})
    for tipo in LOCAL_PARQUET:
        info[tipo] = meta.get(tipo, {}).get("registros", 0)
    counter = _load_counter()
    remaining = MAX_SYNCS_PER_DAY - counter.get("count", 0)
    info["syncs_remaining"] = max(0, remaining)
    return info
