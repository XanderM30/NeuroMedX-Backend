import re
import unicodedata


PALABRAS_VACIAS = {
    "a", "al", "algo", "como", "con", "contra", "cual",
    "cuando", "de", "del", "desde", "donde", "el", "ella",
    "ellas", "ellos", "e", "en", "entre", "era", "es", "esa",
    "ese", "eso", "esta", "este", "esto", "fue", "ha",
    "hacia", "hasta", "hay", "la", "las", "le", "les",
    "lo", "los", "mas", "me", "mi", "mis", "muy",
    "o", "para", "pero", "por", "porque", "que", "se",
    "sin", "sobre", "su", "sus", "tambien", "te", "tengo",
    "tu", "tus", "u", "un", "una", "uno", "unos", "unas",
    "y", "ya",
}

FRASES_NO_SINTOMATICAS = {
    "higado graso no alcoholico": {
        "suele ser asintomatico al inicio",
    },
    "osteoporosis": {
        "suele no dar sintomas hasta que ocurre una fractura",
    },
}

ALIAS_ENFERMEDADES = {
    "gripe": "Influenza (gripe)",
    "influenza": "Influenza (gripe)",
}


def normalizar_texto(texto: str) -> str:
    """Normaliza texto en español sin eliminar información léxica."""
    if not isinstance(texto, str):
        raise TypeError("El texto debe ser una cadena.")

    texto = unicodedata.normalize("NFD", texto.casefold())
    texto = "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)

    return " ".join(texto.split())


def normalizar_nombre_enfermedad(nombre: str) -> str:
    """Devuelve el nombre canónico de una enfermedad."""
    nombre_normalizado = normalizar_texto(nombre)

    return ALIAS_ENFERMEDADES.get(
        nombre_normalizado,
        nombre.strip(),
    )

def tokenizar(texto: str) -> list[str]:
    """Divide un texto normalizado y elimina palabras vacías."""
    return [
        palabra
        for palabra in normalizar_texto(texto).split()
        if palabra not in PALABRAS_VACIAS
    ]


def preparar_vocabulario(enfermedades: list[dict]) -> dict:
    """Construye vocabulario y agrupa enfermedades equivalentes."""
    vocabulario = set()
    frases = {}
    caracteristicas_frase = set()

    for enfermedad in enfermedades:
        nombre_original = enfermedad["nombre"]
        nombre_canonico = normalizar_nombre_enfermedad(
            nombre_original
        )
        nombre_normalizado = normalizar_texto(nombre_original)

        # No sobrescribir síntomas si dos nombres se unifican.
        frases.setdefault(nombre_canonico, [])

        frases_excluidas = FRASES_NO_SINTOMATICAS.get(
            nombre_normalizado,
            set(),
        )

        for sintoma in enfermedad["sintomas"]:
            frase_normalizada = normalizar_texto(sintoma)

            if frase_normalizada in frases_excluidas:
                continue

            tokens = tokenizar(sintoma)

            if not tokens:
                continue

            frases[nombre_canonico].append({
                "original": sintoma,
                "normalizado": frase_normalizada,
                "tokens": tokens,
            })

            vocabulario.update(tokens)
            caracteristicas_frase.add(frase_normalizada)

    return {
        "vocabulario": sorted(vocabulario),
        "frases_vocabulario": sorted(caracteristicas_frase),
        "enfermedades": [
            nombre
            for nombre, manifestaciones in frases.items()
            if manifestaciones
        ],
        "frases": frases,
    }


def construir_entrada_sintomas(
    sintomas_usuario: list[str],
) -> dict:
    """
    Normaliza síntomas introducidos mediante texto libre
    o selección del catálogo.
    """
    if not isinstance(sintomas_usuario, list):
        raise TypeError("Los síntomas deben enviarse como una lista.")

    originales = []
    frases_normalizadas = []
    palabras = set()

    for sintoma in sintomas_usuario:
        if not isinstance(sintoma, str):
            continue

        original = sintoma.strip()

        if not original:
            continue

        normalizado = normalizar_texto(original)

        if not normalizado:
            continue

        originales.append(original)
        frases_normalizadas.append(normalizado)
        palabras.update(tokenizar(original))

    return {
        "originales": originales,
        "frases": sorted(set(frases_normalizadas)),
        "palabras": sorted(palabras),
    }


def vectorizar_sintomas(
    sintomas_usuario: list[str],
    vocabulario: list[str],
) -> list[int]:
    """Genera el vector binario de palabras."""
    entrada = construir_entrada_sintomas(sintomas_usuario)
    palabras_usuario = set(entrada["palabras"])

    return [
        int(caracteristica in palabras_usuario)
        for caracteristica in vocabulario
    ]


def vectorizar_frases(
    sintomas_usuario: list[str],
    frases_vocabulario: list[str],
) -> list[int]:
    """Genera el vector binario de manifestaciones completas."""
    entrada = construir_entrada_sintomas(sintomas_usuario)
    frases_usuario = set(entrada["frases"])

    return [
        int(frase in frases_usuario)
        for frase in frases_vocabulario
    ]


def construir_etiquetas(
    nombres_enfermedades: list[str],
    enfermedades_coincidentes: set[str],
) -> list[int]:
    """Construye una salida multietiqueta."""
    return [
        int(nombre in enfermedades_coincidentes)
        for nombre in nombres_enfermedades
    ]
