import hashlib

from app.ia.iasintomas.datos import cargar_enfermedades
from app.ia.iasintomas.procesamiento import (
    preparar_vocabulario,
    normalizar_texto,
)


def generar_id_manifestacion(frase_normalizada: str) -> str:
    """Genera un identificador estable a partir de la frase canónica."""
    digest = hashlib.sha256(
        frase_normalizada.encode("utf-8")
    ).hexdigest()[:12].upper()

    return f"SINT_{digest}"


def construir_catalogo(
    enfermedades: list[dict] | None = None,
) -> dict:
    """
    Construye un catálogo de manifestaciones únicas.

    Las manifestaciones compartidas por varias enfermedades
    se almacenan una sola vez.
    """
    if enfermedades is None:
        enfermedades = cargar_enfermedades()

    procesados = preparar_vocabulario(enfermedades)

    manifestaciones = {}

    for nombre_enfermedad, frases in procesados["frases"].items():
        for frase in frases:
            canonico = normalizar_texto(frase["original"])

            if not canonico:
                continue

            if canonico not in manifestaciones:
                manifestaciones[canonico] = {
                    "id": generar_id_manifestacion(canonico),
                    "canonico": canonico,
                    "frases_originales": set(),
                    "tokens": sorted(set(frase["tokens"])),
                    "enfermedades": set(),
                }

            registro = manifestaciones[canonico]

            registro["frases_originales"].add(frase["original"])
            registro["enfermedades"].add(nombre_enfermedad)

    resultado = []

    for canonico in sorted(manifestaciones):
        registro = manifestaciones[canonico]

        resultado.append({
            "id": registro["id"],
            "canonico": registro["canonico"],
            "frases_originales": sorted(
                registro["frases_originales"],
                key=str.casefold,
            ),
            "tokens": registro["tokens"],
            "enfermedades": sorted(
                registro["enfermedades"],
                key=str.casefold,
            ),
        })

    identificadores = [
        manifestacion["id"]
        for manifestacion in resultado
    ]

    if len(identificadores) != len(set(identificadores)):
        raise RuntimeError(
            "Se detectaron identificadores duplicados en el catálogo."
        )

    return {
        "version": 1,
        "total_manifestaciones": len(resultado),
        "manifestaciones": resultado,
    }


def buscar_manifestacion(
    catalogo: dict,
    identificador: str,
) -> dict | None:
    """Busca una manifestación mediante su identificador."""
    for manifestacion in catalogo["manifestaciones"]:
        if manifestacion["id"] == identificador:
            return manifestacion

    return None


def buscar_por_frase(
    catalogo: dict,
    frase: str,
) -> dict | None:
    """Busca una coincidencia exacta de frase normalizada."""
    canonico = normalizar_texto(frase)

    for manifestacion in catalogo["manifestaciones"]:
        if manifestacion["canonico"] == canonico:
            return manifestacion

    return None


def obtener_manifestaciones_enfermedad(
    catalogo: dict,
    nombre_enfermedad: str,
) -> list[dict]:
    """Obtiene las manifestaciones asociadas a una enfermedad."""
    nombre_normalizado = normalizar_texto(nombre_enfermedad)

    return [
        manifestacion
        for manifestacion in catalogo["manifestaciones"]
        if any(
            normalizar_texto(nombre) == nombre_normalizado
            for nombre in manifestacion["enfermedades"]
        )
    ]
