from firebase_admin import firestore

from app.auth.firebase import obtener_firebase_app


def cargar_enfermedades() -> list[dict]:
    """Carga y valida enfermedades y síntomas desde Firestore."""
    db = firestore.client(app=obtener_firebase_app())
    documentos = db.collection("enfermedades").stream()

    enfermedades = []

    for documento in documentos:
        datos = documento.to_dict() or {}
        nombre = datos.get("nombre")
        sintomas = datos.get("sintomas", [])

        if not isinstance(nombre, str) or not nombre.strip():
            continue

        if not isinstance(sintomas, list):
            continue

        sintomas_validos = [
            sintoma.strip()
            for sintoma in sintomas
            if isinstance(sintoma, str) and sintoma.strip()
        ]

        if sintomas_validos:
            enfermedades.append({
                "nombre": nombre.strip(),
                "sintomas": sintomas_validos,
            })

    if not enfermedades:
        raise RuntimeError(
            "Firestore no contiene enfermedades con síntomas válidos."
        )

    return enfermedades
