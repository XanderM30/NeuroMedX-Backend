import re

from app.ia.iasintomas.procesamiento import normalizar_texto


ALARMAS_EMERGENCIA = {
    "respiratoria": (
        "dificultad para respirar",
        "no puedo respirar",
        "no puede respirar",
        "me falta el aire",
        "sensacion de asfixia",
    ),
    "toracica": (
        "dolor en el pecho",
        "dolor de pecho",
        "opresion en el pecho",
        "presion en el pecho",
    ),
    "convulsiones": (
        "convulsion",
        "convulsiones",
        "crisis convulsivas",
        "episodios de desconexion subita",
    ),
    "conciencia": (
        "perdida del conocimiento",
        "perdida de conciencia",
        "no responde",
        "esta inconsciente",
    ),
    "neurologica": (
        "debilidad repentina en un lado del cuerpo",
        "paralisis repentina",
        "dificultad repentina para hablar",
        "dolor de cabeza subito e intenso",
    ),
}


ALARMAS_URGENTES = {
    "confusion": (
        "confusion posterior al episodio",
    ),
    "deglucion": (
        "dificultad para tragar",
    ),
    "abdominal": (
        "dolor abdominal que inicia cerca del ombligo y migra hacia abajo a la derecha",
    ),
    "cefalea": (
        "dolor de cabeza intenso",
    ),
    "ocular": (
        "dolor ocular intenso",
    ),
    "vascular": (
        "hinchazon en una pierna",
    ),
}


def detectar_alarmas(texto: str) -> dict:

    if not isinstance(texto, str):
        raise TypeError("El texto debe ser una cadena.")

    normalizado = normalizar_texto(texto)

    coincidencias = []

    niveles = (
        ("posible_emergencia", ALARMAS_EMERGENCIA),
        ("valoracion_urgente", ALARMAS_URGENTES),
    )

    for nivel, grupos in niveles:

        for categoria, expresiones in grupos.items():

            for expresion in expresiones:

                patron = (
                    r"\b"
                    + r"\s+".join(
                        re.escape(palabra)
                        for palabra in expresion.split()
                    )
                    + r"\b"
                )

                if re.search(patron, normalizado):

                    coincidencias.append({
                        "nivel": nivel,
                        "categoria": categoria,
                        "expresion": expresion,
                    })

    if any(
        item["nivel"] == "posible_emergencia"
        for item in coincidencias
    ):
        nivel = "posible_emergencia"

    elif coincidencias:
        nivel = "valoracion_urgente"

    else:
        nivel = "sin_coincidencias"

    return {
        "alarma_detectada": bool(coincidencias),
        "nivel": nivel,
        "coincidencias": coincidencias,
        "validacion_clinica": False,
    }
