from fastapi import Request
from fastapi.responses import JSONResponse, Response

from app.seguridad.proxy.configuracion import (
    ORIGENES_CORS_PERMITIDOS,
    CABECERAS_CORS_PERMITIDAS,
    CORS_MAX_AGE,
    RUTAS_PERMITIDAS,
)


# ==========================================
# VALIDAR ORIGEN
# ==========================================

def obtener_origen_cors(request: Request) -> str | None:
    origenes = request.headers.getlist("origin")

    if len(origenes) != 1:
        return None

    origen = origenes[0]

    if origen not in ORIGENES_CORS_PERMITIDOS:
        return None

    return origen


# ==========================================
# GENERAR CABECERAS CORS
# ==========================================

def generar_cabeceras_cors(origen: str) -> dict[str, str]:

    if origen not in ORIGENES_CORS_PERMITIDOS:
        raise ValueError("Origen CORS no autorizado.")

    return {
        "Access-Control-Allow-Origin": origen,
        "Access-Control-Expose-Headers": (
            "Retry-After, WWW-Authenticate, X-NeuroMedX-Error"
        ),
        "Vary": "Origin",
    }


# ==========================================
# IDENTIFICAR SOLICITUD PREFLIGHT
# ==========================================

def es_preflight(request: Request) -> bool:
    return (
        request.method == "OPTIONS"
        and "origin" in request.headers
        and "access-control-request-method" in request.headers
    )


# ==========================================
# RESPUESTA DE ERROR CORS
# ==========================================

def error_cors(mensaje: str) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"detail": mensaje},
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Vary": (
                "Origin, Access-Control-Request-Method, "
                "Access-Control-Request-Headers"
            ),
        },
    )


# ==========================================
# PROCESAR SOLICITUD PREFLIGHT
# ==========================================

def procesar_preflight(request: Request) -> Response:

    # 1. Validar origen
    origen = obtener_origen_cors(request)

    if origen is None:
        return error_cors("Origen CORS no autorizado.")

    # 2. Validar metodo solicitado
    metodos = request.headers.getlist(
        "access-control-request-method"
    )

    if len(metodos) != 1:
        return error_cors("Metodo CORS invalido.")

    metodo = metodos[0]
    path = request.scope["path"]

    if (metodo, path) not in RUTAS_PERMITIDAS:
        return error_cors("Metodo o ruta no autorizados.")

    # 3. Validar cabeceras solicitadas
    valores = request.headers.getlist(
        "access-control-request-headers"
    )

    if len(valores) > 1:
        return error_cors("Cabeceras CORS duplicadas.")

    cabeceras_solicitadas = set()

    if valores:
        cabeceras_solicitadas = {
            nombre.strip().lower()
            for nombre in valores[0].split(",")
        }

    if not cabeceras_solicitadas.issubset(
        CABECERAS_CORS_PERMITIDAS
    ):
        return error_cors("Cabeceras CORS no autorizadas.")

    # 4. Construir respuesta autorizada
    cabeceras = generar_cabeceras_cors(origen)

    cabeceras.update({
        "Access-Control-Allow-Methods": metodo,
        "Access-Control-Allow-Headers": ", ".join(
            sorted(CABECERAS_CORS_PERMITIDAS)
        ),
        "Access-Control-Max-Age": str(CORS_MAX_AGE),
        "Vary": (
            "Origin, Access-Control-Request-Method, "
            "Access-Control-Request-Headers"
        ),
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    })

    return Response(
        status_code=204,
        headers=cabeceras,
    )