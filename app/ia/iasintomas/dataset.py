from itertools import combinations

from app.ia.iasintomas.catalogo import construir_catalogo


def construir_dataset(
    catalogo: dict | None = None,
    max_sintomas: int = 3,
) -> dict:
    """
    Construye muestras sintéticas a partir de las asociaciones
    entre manifestaciones y enfermedades.

    Las combinaciones compartidas se agrupan en una sola muestra
    con todas sus enfermedades asociadas.
    """
    if max_sintomas < 1:
        raise ValueError("max_sintomas debe ser al menos 1.")

    if catalogo is None:
        catalogo = construir_catalogo()

    manifestaciones = catalogo["manifestaciones"]

    ids_manifestaciones = [
        item["id"]
        for item in manifestaciones
    ]

    nombres_enfermedades = sorted({
        nombre
        for item in manifestaciones
        for nombre in item["enfermedades"]
    })

    indice_manifestaciones = {
        identificador: indice
        for indice, identificador in enumerate(ids_manifestaciones)
    }

    # Obtener las manifestaciones de cada enfermedad.
    sintomas_por_enfermedad = {
        enfermedad: []
        for enfermedad in nombres_enfermedades
    }

    for item in manifestaciones:
        for enfermedad in item["enfermedades"]:
            sintomas_por_enfermedad[enfermedad].append(item["id"])

    # Agrupar combinaciones repetidas.
    combinaciones = {}

    for enfermedad, sintomas in sintomas_por_enfermedad.items():
        sintomas = sorted(set(sintomas))

        for cantidad in range(
            1,
            min(max_sintomas, len(sintomas)) + 1,
        ):
            for grupo in combinations(sintomas, cantidad):
                clave = tuple(sorted(grupo))

                if clave not in combinaciones:
                    combinaciones[clave] = set()

                combinaciones[clave].add(enfermedad)

    muestras = []

    for grupo, enfermedades in sorted(combinaciones.items()):
        entrada = [0] * len(ids_manifestaciones)

        for identificador in grupo:
            indice = indice_manifestaciones[identificador]
            entrada[indice] = 1

        etiquetas = [
            int(enfermedad in enfermedades)
            for enfermedad in nombres_enfermedades
        ]

        muestras.append({
            "sintomas_ids": list(grupo),
            "entrada": entrada,
            "etiquetas": etiquetas,
            "enfermedades_coincidentes": sorted(enfermedades),
        })

    return {
        "version": 1,
        "tipo": "sintetico_catalogo",
        "max_sintomas": max_sintomas,
        "manifestaciones": ids_manifestaciones,
        "enfermedades": nombres_enfermedades,
        "total_manifestaciones": len(ids_manifestaciones),
        "total_enfermedades": len(nombres_enfermedades),
        "total_muestras": len(muestras),
        "muestras": muestras,
    }
