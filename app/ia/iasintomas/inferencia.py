import json
import hashlib
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.ia.iasintomas.alarmas import detectar_alarmas
from app.ia.iasintomas.dataset import construir_dataset
from app.ia.iasintomas.reconocimiento import reconocer_sintomas


RUTA_MODELO = (
    Path(__file__).resolve().parents[3]
    / "modelos"
    / "sintomas"
)


@lru_cache(maxsize=1)
def cargar_recursos():
    import tensorflow as tf

    with (RUTA_MODELO / "configuracion.json").open(
        encoding="utf-8"
    ) as archivo:
        configuracion = json.load(archivo)

    # Cargar y verificar el catalogo congelado.
    metadata_catalogo = configuracion["catalogo_congelado"]

    if metadata_catalogo["version"] != 1:
        raise ValueError("Version de catalogo incompatible.")

    if metadata_catalogo["archivo"] != "catalogo.json":
        raise ValueError("Archivo de catalogo incompatible.")

    ruta_catalogo = RUTA_MODELO / "catalogo.json"

    contenido_catalogo = ruta_catalogo.read_bytes()

    huella_actual = hashlib.sha256(
        contenido_catalogo
    ).hexdigest()

    if huella_actual != metadata_catalogo["sha256"]:
        raise ValueError("Integridad del catalogo comprometida.")

    catalogo = json.loads(
        contenido_catalogo.decode("utf-8")
    )

    ids = [
        item["id"]
        for item in catalogo["manifestaciones"]
    ]

    enfermedades = sorted({
        enfermedad
        for item in catalogo["manifestaciones"]
        for enfermedad in item["enfermedades"]
    })

    if ids != configuracion["manifestaciones"]:
        raise ValueError(
            "Catalogo de manifestaciones incompatible."
        )

    if enfermedades != configuracion["enfermedades"]:
        raise ValueError(
            "Catalogo de enfermedades incompatible."
        )

    modelo = tf.keras.models.load_model(
        RUTA_MODELO / "modelo_sintomas.keras",
        compile=False,
    )

    if modelo.input_shape[-1] != len(ids):
        raise ValueError("Entrada del modelo incompatible.")

    if modelo.output_shape[-1] != len(enfermedades):
        raise ValueError("Salida del modelo incompatible.")

    dataset = construir_dataset(
        catalogo=catalogo,
        max_sintomas=3,
    )

    if (
        dataset["total_manifestaciones"]
        != metadata_catalogo["total_manifestaciones"]
        or dataset["total_enfermedades"]
        != metadata_catalogo["total_enfermedades"]
        or dataset["total_muestras"]
        != metadata_catalogo["total_combinaciones"]
    ):
        raise ValueError("Dimensiones del catalogo incompatibles.")

    combinaciones_conocidas = frozenset(
        frozenset(muestra["sintomas_ids"])
        for muestra in dataset["muestras"]
    )

    return {
        "combinaciones_conocidas": combinaciones_conocidas,
        "modelo": modelo,
        "catalogo": catalogo,
        "configuracion": configuracion,
        "indice_manifestaciones": {
            identificador: indice
            for indice, identificador in enumerate(ids)
        },
    }


def analizar_sintomas(texto: str) -> dict:

    if not isinstance(texto, str):
        raise TypeError("El texto debe ser una cadena.")

    if not texto.strip():
        raise ValueError("El texto no puede estar vacio.")

    # Las posibles alarmas tienen prioridad sobre el modelo.
    alarmas = detectar_alarmas(texto)

    if alarmas["alarma_detectada"]:

        if alarmas["nivel"] == "posible_emergencia":
            mensaje = (
                "Se identifico una expresion de posible emergencia. "
                "Si la manifestacion esta ocurriendo, "
                "busque atencion medica de emergencia inmediatamente "
                "o llame al 911. No espere una evaluacion de la IA."
            )
        else:
            mensaje = (
                "Se identifico una expresion que puede requerir "
                "valoracion medica urgente. "
                "Busque atencion medica sin demora. "
                "Si los sintomas son graves o repentinos, "
                "solicite atencion de emergencia."
            )

        return {
            "reconocimiento": None,
            "resultados": [],
            "estado": alarmas["nivel"],
            "alarmas": alarmas,
            "umbral": None,
            "validacion_clinica": False,
            "advertencia": mensaje,
        }

    recursos = cargar_recursos()
    configuracion = recursos["configuracion"]

    reconocimiento = reconocer_sintomas(
        texto,
        recursos["catalogo"],
    )

    positivas = reconocimiento["manifestaciones_positivas"]
    negadas = reconocimiento["manifestaciones_negadas"]

    ids_positivos = {
        item["id"] for item in positivas
    }

    ids_negados = {
        item["id"] for item in negadas
    }

    respuesta = {
        "reconocimiento": reconocimiento,
        "alarmas": alarmas,
        "resultados": [],
        "estado": "pendiente",
        "umbral": configuracion["umbral_clasificacion"],
        "validacion_clinica": False,
        "advertencia": (
            "Modelo experimental. Los resultados no "
            "constituyen un diagnostico medico ni "
            "descartan enfermedades."
        ),
    }

    if ids_positivos.intersection(ids_negados):
        respuesta["estado"] = "manifestaciones_contradictorias"
        return respuesta

    if not positivas:
        respuesta["estado"] = "sin_manifestaciones_positivas"
        return respuesta

    if len(ids_positivos) > 3:
        respuesta["estado"] = "fuera_del_rango_evaluado"
        return respuesta

    # Evitar inferencias con informacion no interpretada.
    residual = reconocimiento["texto_no_reconocido"].strip()

    if residual:
        respuesta["estado"] = "requiere_aclaracion"
        respuesta["aclaracion"] = {
            "motivo": "texto_parcialmente_reconocido",
            "texto_pendiente": residual,
            "mensaje": (
                "No se pudo interpretar toda la informacion. "
                "Es necesario aclarar los datos antes de continuar."
            ),
        }
        return respuesta

    # Bloquear combinaciones ausentes del dataset.
    combinacion = frozenset(ids_positivos)

    if combinacion not in recursos["combinaciones_conocidas"]:
        respuesta["estado"] = "combinacion_desconocida"
        respuesta["aclaracion"] = {
            "motivo": "combinacion_fuera_del_dataset",
            "mensaje": (
                "Esta combinacion no esta representada "
                "en el dataset experimental. "
                "No es posible generar resultados fiables. "
                "Esto no descarta ninguna enfermedad."
            ),
        }
        return respuesta

    entrada = np.zeros(
        (1, len(configuracion["manifestaciones"])),
        dtype=np.float32,
    )

    for identificador in ids_positivos:
        indice = recursos["indice_manifestaciones"][identificador]
        entrada[0, indice] = 1.0

    puntuaciones = recursos["modelo"](
        entrada,
        training=False,
    ).numpy()[0]

    if not np.all(np.isfinite(puntuaciones)):
        raise ValueError("Puntuaciones invalidas del modelo.")

    umbral = configuracion["umbral_clasificacion"]

    resultados = [
        {
            "enfermedad": enfermedad,
            "puntuacion_modelo": round(float(puntuacion), 6),
        }
        for enfermedad, puntuacion in zip(
            configuracion["enfermedades"],
            puntuaciones,
        )
        if puntuacion >= umbral
    ]

    resultados.sort(
        key=lambda item: item["puntuacion_modelo"],
        reverse=True,
    )

    respuesta["resultados"] = resultados

    respuesta["estado"] = (
        "resultados_orientativos"
        if resultados
        else "sin_resultados_sobre_umbral"
    )

    return respuesta
