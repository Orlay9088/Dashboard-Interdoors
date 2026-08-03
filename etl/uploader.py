from firebase_config import save_to_firestore, set_metadata
from datetime import datetime


def subir_a_firestore(df, tipo, filename=""):
    count = save_to_firestore(df, tipo, filename)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_metadata("ultima_actualizacion", {
        "fecha": now,
        "tipo": tipo,
        "registros": count,
        "archivo": filename,
    })
    return count
