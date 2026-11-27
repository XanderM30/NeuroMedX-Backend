# Direccion interna de FastAPI
URL_BACKEND = "http://10.242.46.163:8001"

# Direccion de escucha del proxy
HOST_PROXY = "127.0.0.1"
PUERTO_PROXY = 8002

# Dominio publico autorizado
HOST_PUBLICO = "api.neuromedx.site"

# Rutas publicas y metodos permitidos
RUTAS_PERMITIDAS = frozenset({
    ("GET", "/salud"),
    ("GET", "/usuarios/me"),
    ("POST", "/usuarios/registro-paciente"),
    ("POST", "/ia/medicamentos/detectar"),
})

# Limites de cuerpo por ruta, expresados en bytes
LIMITES_CUERPO = {
    "/usuarios/registro-paciente": 4 * 1024,
    "/ia/medicamentos/detectar": 128 * 1024,
}

LIMITE_CUERPO_PREDETERMINADO = 0

# Tiempos maximos expresados en segundos
TIMEOUT_CONEXION = 5
TIMEOUT_LECTURA = 90
TIMEOUT_ESCRITURA = 15
TIMEOUT_POOL = 5
TIMEOUT_RECEPCION = 15
