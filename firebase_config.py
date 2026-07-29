import os
import json
from datetime import date
from pathlib import Path
import pandas as pd

LOCAL_BASE = Path(__file__).parent / "base"
COUNTER_FILE = LOCAL_BASE / ".sync_counter.json"
CACHE_FILE = LOCAL_BASE / ".cache_meta.json"

LOCAL_PARQUET = {
    "pedidos": LOCAL_BASE / "pedidos.parquet",
    "facturas": LOCAL_BASE / "facturas.parquet",
    "inventario": LOCAL_BASE / "inventario.parquet",
}

MAX_SYNCS_PER_DAY = 3
CACHE_TTL_HOURS = 24


def _load_counter():
    if COUNTER_FILE.exists():
        with open(COUNTER_FILE) as f:
            return json.load(f)
    return {"date": "", "count": 0}


def _save_counter(data):
    LOCAL_BASE.mkdir(parents=True, exist_ok=True)
    with open(COUNTER_FILE, "w") as f:
        json.dump(data, f)


def _firestore_ok():
    today = str(date.today())
    c = _load_counter()
    if c.get("date") != today:
        c = {"date": today, "count": 0}
        _save_counter(c)
    return c["count"] < MAX_SYNCS_PER_DAY


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
    return path


def load_local(tipo):
    path = LOCAL_PARQUET.get(tipo)
    if path and path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


def try_save(df, tipo, filename=""):
    n = len(df)
    save_local(df, tipo)
    _use_firestore_sync()
    return n


def try_load(tipo):
    return load_local(tipo), "local"


def is_cache_stale():
    if not CACHE_FILE.exists():
        return True
    try:
        with open(CACHE_FILE) as f:
            meta = json.load(f)
        from datetime import datetime
        ts = datetime.fromisoformat(meta["created"])
        return (datetime.now() - ts).total_seconds() > CACHE_TTL_HOURS * 3600
    except Exception:
        return True


def mark_cache_fresh():
    LOCAL_BASE.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    with open(CACHE_FILE, "w") as f:
        json.dump({"created": datetime.now().isoformat()}, f)


def clear_local_cache():
    for path in LOCAL_PARQUET.values():
        if path.exists():
            path.unlink()
    if COUNTER_FILE.exists():
        COUNTER_FILE.unlink()
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()


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


def set_metadata(doc_id, data):
    pass
