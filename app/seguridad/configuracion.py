import os

from dotenv import load_dotenv

load_dotenv()


def obtener_booleano(
    nombre: str,
    predeterminado: bool = False
) -> bool:
    valor = os.getenv(nombre)

    if valor is None:
        return predeterminado

    return valor.strip().lower() == "true"


# Documentacion interactiva de FastAPI
DOCUMENTACION_HABILITADA = obtener_booleano(
    "DOCUMENTACION_HABILITADA",
    False
)


# Consulta interna del estado de PostgreSQL
SALUD_BASE_DATOS_HABILITADA = obtener_booleano(
    "SALUD_BASE_DATOS_HABILITADA",
    False
)


# Recepcion y consulta experimental de mediciones
PULSERA_MEDICIONES_HABILITADAS = obtener_booleano(
    "PULSERA_MEDICIONES_HABILITADAS",
    False
)
# Limites de solicitudes por minuto
VENTANA_SOLICITUDES = 60

LIMITE_GENERAL_IP = 120

LIMITE_MEDICAMENTOS_UID = 20

LIMITE_SINTOMAS_UID = 10

LIMITE_REGISTRO_UID = 5

LIMITE_PERFIL_UID = 60
# Tiempo maximo para recibir el cuerpo HTTP
TIEMPO_MAXIMO_RECEPCION_HTTP = 15
