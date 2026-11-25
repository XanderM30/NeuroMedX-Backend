from pathlib import Path
import sys

import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification


# ============================================================
# RUTAS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

RUTA_MODELO = ROOT / "modelos" / "BETO" / "modelo_final"
RUTA_TOKENIZADOR = ROOT / "modelos" / "BETO" / "tokenizador"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datos.medicamentos.normalizador import buscar_medicamento


# ============================================================
# CARGA DEL MODELO
# ============================================================

_MODELO = None
_TOKENIZADOR = None
_DISPOSITIVO = None


def cargar_modelo():
    global _MODELO, _TOKENIZADOR, _DISPOSITIVO

    if _MODELO is not None and _TOKENIZADOR is not None:
        return _MODELO, _TOKENIZADOR

    if not RUTA_MODELO.is_dir():
        raise FileNotFoundError(f"No existe el modelo: {RUTA_MODELO}")

    if not RUTA_TOKENIZADOR.is_dir():
        raise FileNotFoundError(
            f"No existe el tokenizador: {RUTA_TOKENIZADOR}"
        )

    _DISPOSITIVO = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    _TOKENIZADOR = AutoTokenizer.from_pretrained(
        str(RUTA_TOKENIZADOR),
        local_files_only=True,
        use_fast=True
    )

    if not _TOKENIZADOR.is_fast:
        raise RuntimeError(
            "Se necesita un tokenizador Fast para obtener posiciones."
        )

    _MODELO = AutoModelForTokenClassification.from_pretrained(
        str(RUTA_MODELO),
        local_files_only=True,
        use_safetensors=True
    )

    _MODELO.to(_DISPOSITIVO)
    _MODELO.eval()

    return _MODELO, _TOKENIZADOR


# ============================================================
# DETECCION Y EXTRACCION DE ENTIDADES BIO
# ============================================================

def detectar_medicamentos(texto: str, umbral_confianza: float = 0.50):
    if not isinstance(texto, str):
        raise TypeError("El texto debe ser una cadena.")

    if not 0.0 <= umbral_confianza <= 1.0:
        raise ValueError("El umbral debe estar entre 0 y 1.")

    if not texto.strip():
        return {
            "texto": texto,
            "menciones": [],
            "total_menciones": 0
        }

    modelo, tokenizador = cargar_modelo()

    entradas = tokenizador(
        texto,
        return_tensors="pt",
        return_offsets_mapping=True,
        truncation=True,
        max_length=128
    )

    offsets = entradas.pop("offset_mapping")[0].tolist()

    entradas_modelo = {
        nombre: tensor.to(_DISPOSITIVO)
        for nombre, tensor in entradas.items()
    }

    with torch.no_grad():
        salida = modelo(**entradas_modelo)
        probabilidades = torch.softmax(salida.logits, dim=-1)[0]

    predicciones = probabilidades.argmax(dim=-1).tolist()
    id2label = modelo.config.id2label

    entidades = []
    actual = None

    def finalizar_entidad():
        nonlocal actual

        if actual is None:
            return

        inicio = actual["inicio"]
        fin = actual["fin"]
        confianza = sum(actual["confianzas"]) / len(
            actual["confianzas"]
        )

        mencion = texto[inicio:fin]
        normalizacion = None

        if confianza >= umbral_confianza:
            normalizacion = buscar_medicamento(mencion)

        entidades.append({
            "texto": mencion,
            "inicio": inicio,
            "fin": fin,
            "confianza": round(confianza, 6),
            "coincide_catalogo": normalizacion is not None,
            "medicamento_id": (
                normalizacion["medicamento_id"]
                if normalizacion else None
            ),
            "medicamento": (
                normalizacion["medicamento"]
                if normalizacion else None
            ),
            "evidencia": (
                normalizacion["evidencia"]
                if normalizacion else None
            ),
            "tipo_coincidencia": (
                normalizacion.get("tipo_coincidencia")
                if normalizacion else None
            ),
            "estado_catalogo": (
                normalizacion["tipo_coincidencia"]
                if normalizacion
                else (
                    "sin_alias_aprobado"
                    if confianza >= umbral_confianza
                    else "confianza_baja"
                )
            )
        })

        actual = None

    for indice, (id_etiqueta, offset) in enumerate(
        zip(predicciones, offsets)
    ):
        inicio, fin = offset

        # Ignorar tokens especiales.
        if inicio == fin:
            continue

        etiqueta = id2label.get(
            id_etiqueta,
            id2label.get(str(id_etiqueta), "O")
        )

        confianza = float(
            probabilidades[indice, id_etiqueta].item()
        )

        if etiqueta == "O":
            finalizar_entidad()
            continue

        if etiqueta == "B-MED":
            finalizar_entidad()

            actual = {
                "inicio": inicio,
                "fin": fin,
                "confianzas": [confianza]
            }

        elif etiqueta == "I-MED":
            if actual is None:
                actual = {
                    "inicio": inicio,
                    "fin": fin,
                    "confianzas": [confianza]
                }
            else:
                actual["fin"] = fin
                actual["confianzas"].append(confianza)

        else:
            finalizar_entidad()

    finalizar_entidad()

    return {
        "texto": texto,
        "menciones": entidades,
        "total_menciones": len(entidades),
        "umbral_confianza": umbral_confianza,
        "dispositivo": str(_DISPOSITIVO)
    }
