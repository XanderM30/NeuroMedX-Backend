import os
from dotenv import load_dotenv

load_dotenv()


# ==========================================
# CONFIGURACION GENERAL DEL PROXY
# ==========================================

# Direccion interna de FastAPI
URL_BACKEND = "http://10.242.46.163:8001"

# Direccion de escucha del proxy
HOST_PROXY = "127.0.0.1"
PUERTO_PROXY = 8002

# Dominio publico autorizado
HOST_PUBLICO = "api.neuromedx.site"


# ==========================================
# RUTAS PUBLICAS Y METODOS PERMITIDOS
# ==========================================

RUTAS_PERMITIDAS = frozenset({
    ("GET", "/salud"),
    ("GET", "/usuarios/me"),
    ("POST", "/usuarios/registro-paciente"),
    ("POST", "/usuarios/registro-medico"),
    ("GET", "/medicos/me"),
    ("POST", "/ia/medicamentos/detectar"),
})


# ==========================================
# LIMITES DEL CUERPO HTTP
# ==========================================

LIMITES_CUERPO = {
    "/usuarios/registro-paciente": 4 * 1024,
    "/usuarios/registro-medico": 4 * 1024,
    "/ia/medicamentos/detectar": 128 * 1024,
}

LIMITE_CUERPO_PREDETERMINADO = 0


# ==========================================
# TIEMPOS MAXIMOS EN SEGUNDOS
# ==========================================

TIMEOUT_CONEXION = 5
TIMEOUT_LECTURA = 90
TIMEOUT_ESCRITURA = 15
TIMEOUT_POOL = 5
TIMEOUT_RECEPCION = 15


# ==========================================
# CONFIGURACION CORS DEL PORTAL MEDICO
# ==========================================

ORIGENES_CORS_PRODUCCION = frozenset({
    "https://medicos.neuromedx.site",
})

ORIGENES_CORS_DESARROLLO = frozenset({
    "http://localhost:3000",
    "http://192.168.0.162:3000",
})

CORS_DESARROLLO_HABILITADO = (
    os.getenv("CORS_DESARROLLO_HABILITADO", "false")
    .strip()
    .lower() == "true"
)

ORIGENES_CORS_PERMITIDOS = (
    ORIGENES_CORS_PRODUCCION | ORIGENES_CORS_DESARROLLO
    if CORS_DESARROLLO_HABILITADO
    else ORIGENES_CORS_PRODUCCION
)

CABECERAS_CORS_PERMITIDAS = frozenset({
    "authorization",
    "content-type",
    "accept",
})

CORS_MAX_AGE = 600
# ==========================================
# LIMITACION DE SOLICITUDES PREFLIGHT
# ==========================================

LIMITE_PREFLIGHT_IP = 60
VENTANA_PREFLIGHT = 60
