import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from pathlib import Path

_initialized = False
_db = None

KEY_PATH = Path(__file__).parent / "firebase-key.json"

def get_db():
    global _initialized, _db
    if _initialized:
        return _db
    cred = None
    if KEY_PATH.exists():
        cred = credentials.Certificate(str(KEY_PATH))
    else:
        raw = os.environ.get("FIREBASE_KEY_JSON")
        if raw:
            cred = credentials.Certificate(json.loads(raw))
    if cred is None:
        raise RuntimeError("No se encontro firebase-key.json ni FIREBASE_KEY_JSON")
    app = firebase_admin.initialize_app(cred)
    _db = firestore.client()
    _initialized = True
    return _db


def save_to_firestore(df, collection, batch_size=500):
    db = get_db()
    docs = df.to_dict(orient="records")
    total = len(docs)
    for i in range(0, total, batch_size):
        batch = db.batch()
        for doc in docs[i : i + batch_size]:
            batch.set(db.collection(collection).document(), doc)
        batch.commit()
    return total


def load_from_firestore(collection, filters=None):
    db = get_db()
    ref = db.collection(collection)
    if filters:
        for field, op_val in filters.items():
            op, val = op_val
            ref = ref.where(field, op, val)
    docs = list(ref.stream())
    records = [d.to_dict() for d in docs]
    import pandas as pd
    return pd.DataFrame(records) if records else pd.DataFrame()


def get_metadata():
    db = get_db()
    docs = list(db.collection("metadata").stream())
    return {d.id: d.to_dict() for d in docs}


def set_metadata(doc_id, data):
    db = get_db()
    db.collection("metadata").document(doc_id).set(data)
