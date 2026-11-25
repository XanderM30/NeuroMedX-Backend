import json
import re
import unicodedata
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
ARCHIVO_ALIAS = CARPETA / "alias_medicamentos.json"
ARCHIVO_ETIQUETAS = (
    CARPETA.parents[1]
    / "modelos"
    / "BETO"
    / "configuracion"
    / "etiquetas.json"
)


def normalizar_texto(texto: str) -> str:
    """Normaliza mayusculas, acentos y separadores."""
    texto = unicodedata.normalize("NFKD", str(texto or "").upper())
    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )
    return re.sub(r"[^A-Z0-9]+", " ", texto).strip()


def cargar_catalogo():
    """Carga y valida el diccionario de alias."""
    if not ARCHIVO_ALIAS.exists():
        raise FileNotFoundError(
            f"No se encontro el catalogo: {ARCHIVO_ALIAS}"
        )

    with ARCHIVO_ALIAS.open("r", encoding="utf-8-sig") as archivo:
        datos = json.load(archivo)

    indice = datos.get("indice_alias")
    if not isinstance(indice, dict):
        raise ValueError("El catalogo no contiene un indice valido.")

    return datos


def buscar_nombre_canonico(clave: str):
    """Busca coincidencias exactas entre los 23 nombres canonicos."""
    if not ARCHIVO_ETIQUETAS.exists():
        raise FileNotFoundError(
            f"No se encontro el catalogo canonico: {ARCHIVO_ETIQUETAS}"
        )

    with ARCHIVO_ETIQUETAS.open(
        "r", encoding="utf-8-sig"
    ) as archivo:
        datos = json.load(archivo)

    for medicamento in datos.get("medicamentos", []):
        if normalizar_texto(medicamento["nombre"]) == clave:
            return {
                "encontrado": True,
                "medicamento_id": medicamento["id"],
                "medicamento": medicamento["nombre"],
                "nombre_comercial": None,
                "tipo_coincidencia": "nombre_canonico",
                "evidencia": {
                    "tipo": "nombre_canonico",
                    "fuente": "modelos/BETO/configuracion/etiquetas.json"
                }
            }

    return None


def buscar_medicamento(nombre: str):
    """
    Busca primero alias aprobados y despues nombres canonicos.
    Ambas busquedas son exactas despues de normalizar el texto.
    """
    if not isinstance(nombre, str) or not nombre.strip():
        return None

    datos = cargar_catalogo()
    clave = normalizar_texto(nombre)

    if not clave:
        return None

    medicamento_id = datos["indice_alias"].get(clave)

    if medicamento_id is not None:
        for alias in datos["aliases"]:
            if (
                alias["medicamento_id"] == medicamento_id
                and alias["alias_normalizado"] == clave
            ):
                return {
                    "encontrado": True,
                    "medicamento_id": medicamento_id,
                    "medicamento": alias["medicamento"],
                    "nombre_comercial": alias["nombre_comercial"],
                    "tipo_coincidencia": "alias_aprobado",
                    "evidencia": {
                        "clasificacion": alias["clasificacion_cofepris"],
                        "registros_cofepris": alias["numeros_de_registro"],
                        "denominaciones_genericas": alias["denominaciones_genericas"],
                        "sustancias_quimicas": alias["sustancias_quimicas"],
                        "presentaciones": alias["presentaciones"],
                    },
                }

        raise ValueError(
            f"El indice contiene {clave}, pero no existe su registro detallado."
        )

    return buscar_nombre_canonico(clave)


def normalizar_medicamento(nombre: str):
    """Devuelve el identificador y nombre canonico."""
    resultado = buscar_medicamento(nombre)

    if resultado is None:
        return None

    return {
        "medicamento_id": resultado["medicamento_id"],
        "medicamento": resultado["medicamento"],
    }


if __name__ == "__main__":
    pruebas = [
        "BIOROIC",
        "CLIRBEST",
        "ZYRTEC",
        "PARACETAMOL",
        "Losartan",
        "NOMBRE INEXISTENTE",
    ]

    print("========== PRUEBAS DEL NORMALIZADOR ==========")

    for nombre in pruebas:
        resultado = buscar_medicamento(nombre)
        print(f"{nombre} -> {resultado}")
