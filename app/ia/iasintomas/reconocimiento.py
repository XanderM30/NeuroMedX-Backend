import re

from app.ia.iasintomas.procesamiento import (
    normalizar_texto,
    tokenizar,
)


EQUIVALENCIAS_SINTOMAS = {
    "me duele la cabeza": "dolor de cabeza",
    "tengo dolor de cabeza": "dolor de cabeza",
    "tengo fiebre": "fiebre",
    "presento fiebre": "fiebre",
    "estoy cansado": "cansancio",
    "estoy cansada": "cansancio",
    "me siento cansado": "cansancio",
    "me siento cansada": "cansancio",
    "tengo cansancio": "cansancio",
}

PATRON_NEGACION = re.compile(
    r"(?:\bno\b|\bsin\b|\bnunca\b|\bjamás\b|\bjamás\b)"
    r"(?:\s+\w+){0,2}\s*$"
)


def crear_patron(frase: str) -> re.Pattern:
    """Crea un patrón que reconoce frases completas."""
    partes = [re.escape(palabra) for palabra in frase.split()]
    contenido = r"\s+".join(partes)

    return re.compile(
        rf"(?<![a-z0-9]){contenido}(?![a-z0-9])"
    )


def construir_patrones(catalogo: dict) -> list[dict]:
    """Prepara frases canónicas y equivalencias reconocidas."""
    patrones = {}

    for manifestacion in catalogo["manifestaciones"]:
        canonico = manifestacion["canonico"]

        patrones[canonico] = {
            "canonico": canonico,
            "id": manifestacion["id"],
            "patron": crear_patron(canonico),
        }

    for variante, canonico in EQUIVALENCIAS_SINTOMAS.items():
        manifestacion = next(
            (
                item
                for item in catalogo["manifestaciones"]
                if item["canonico"] == canonico
            ),
            None,
        )

        if manifestacion is None:
            raise ValueError(
                f"La equivalencia '{variante}' apunta a "
                f"una manifestación inexistente: '{canonico}'."
            )

        patrones[variante] = {
            "canonico": canonico,
            "id": manifestacion["id"],
            "patron": crear_patron(variante),
        }

    return sorted(
        patrones.values(),
        key=lambda item: len(item["canonico"].split()),
        reverse=True,
    )


def tiene_negacion(texto: str, inicio: int) -> bool:
    """Detecta negaciones respetando conectores y excepciones."""

    contexto = texto[:inicio]

    # Una conjunción adversativa inicia un nuevo contexto.
    conectores = [
        "pero",
        "aunque",
        "sin embargo",
        "sino",
        "mas bien",
    ]

    ultimo_conector = -1

    for conector in conectores:
        posicion = contexto.rfind(conector)

        if posicion > ultimo_conector:
            ultimo_conector = posicion

    if ultimo_conector >= 0:
        contexto = contexto[ultimo_conector + len(
            next(
                conector
                for conector in conectores
                if contexto.rfind(conector) == ultimo_conector
            )
        ):]

    # Expresiones afirmativas que no representan negacion.
    contexto = re.sub(
        r"\bsin\s+(?:lugar\s+a\s+dudas|ninguna\s+duda|duda\s+alguna|duda)\b",
        " ",
        contexto,
    )

    contexto = contexto.strip()

    # "No solamente" y "no solo" no expresan negación del síntoma.
    if re.search(r"\bno\s+(?:solamente|solo)\b", contexto):
        return False

    # Una negación explícita puede extenderse hasta el siguiente síntoma.
    if re.search(r"\b(?:no|nunca|jamas|sin)\b(?:\s+\w+){0,3}\s*$", contexto):
        return True

    # "Ni" niega también el síntoma que aparece a continuación.
    if re.search(r"\bni\s*$", contexto):
        return True

    return False




def reconocer_sintomas(
    texto: str,
    catalogo: dict,
) -> dict:
    """
    Reconoce manifestaciones del catálogo en texto libre.

    Devuelve manifestaciones positivas, negadas y texto
    que no pudo reconocerse.
    """
    if not isinstance(texto, str):
        raise TypeError("El texto debe ser una cadena.")

    texto_normalizado = normalizar_texto(texto)
    patrones = construir_patrones(catalogo)

    coincidencias = []

    for item in patrones:
        for coincidencia in item["patron"].finditer(texto_normalizado):
            coincidencias.append({
                "inicio": coincidencia.start(),
                "fin": coincidencia.end(),
                "id": item["id"],
                "canonico": item["canonico"],
                "negado": tiene_negacion(
                    texto_normalizado,
                    coincidencia.start(),
                ),
            })

    coincidencias.sort(
        key=lambda item: (
            item["inicio"],
            -(item["fin"] - item["inicio"]),
        )
    )

    seleccionadas = []
    posiciones_ocupadas = []

    for item in coincidencias:
        se_superpone = any(
            item["inicio"] < fin and item["fin"] > inicio
            for inicio, fin in posiciones_ocupadas
        )

        if se_superpone:
            continue

        seleccionadas.append(item)
        posiciones_ocupadas.append(
            (item["inicio"], item["fin"])
        )

    positivas = {}
    negadas = {}

    for item in seleccionadas:
        destino = negadas if item["negado"] else positivas

        destino[item["id"]] = {
            "id": item["id"],
            "canonico": item["canonico"],
        }

    # Preparar el texto residual.
    texto_residual = list(texto_normalizado)

    for item in seleccionadas:
        for posicion in range(item["inicio"], item["fin"]):
            texto_residual[posicion] = " "

    texto_residual_normalizado = "".join(texto_residual)

    # Eliminar expresiones afirmativas completas del residual.
    texto_residual_normalizado = re.sub(
        r"\bsin\s+(?:lugar\s+a\s+dudas|ninguna\s+duda|duda\s+alguna|duda)\b",
        " ",
        texto_residual_normalizado,
    )

    tokens_residuales = texto_residual_normalizado.split()

    palabras_auxiliares = {
        "no", "ni", "nunca", "jamas",
        "he", "tenido", "tengo",
        "aunque", "pero",
        "solamente", "solo", "tambien",
        "si", "tampoco", "mas", "bien",
        "sin", "embargo",
        "y", "e",
    }

    tokens_residuales = [
        token
        for token in tokens_residuales
        if token not in palabras_auxiliares
    ]

    return {
        "texto_original": texto,
        "manifestaciones_positivas": list(positivas.values()),
        "manifestaciones_negadas": list(negadas.values()),
        "texto_no_reconocido": " ".join(tokens_residuales),
    }
