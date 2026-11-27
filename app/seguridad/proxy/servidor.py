import os
import re
import asyncio
from pathlib import Path

import anyio
import httpx

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, Response

from app.seguridad.proxy.configuracion import (
    URL_BACKEND,
    HOST_PUBLICO,
    RUTAS_PERMITIDAS,
    LIMITES_CUERPO,
    LIMITE_CUERPO_PREDETERMINADO,
    TIMEOUT_CONEXION,
    TIMEOUT_LECTURA,
    TIMEOUT_ESCRITURA,
    TIMEOUT_POOL,
    TIMEOUT_RECEPCION,
)

from app.seguridad.proxy.cabeceras import (
    obtener_ip_cloudflare,
    preparar_cabeceras,
)

from app.seguridad.proxy.mantenimiento import (
    servicio_habilitado,
)
from app.seguridad.proxy.politicas import limitar_preflight

from app.seguridad.proxy.cors import (
    obtener_origen_cors,
    generar_cabeceras_cors,
    es_preflight,
    procesar_preflight,
    error_cors,
)

load_dotenv()

INDICADOR_PROXY = Path(
    r"C:\NeuroMedX-AutoUpdate\proxy-habilitado.flag"
)

CLAVE_INTERNA = os.getenv("PROXY_CLAVE_INTERNA", "")

MAXIMO_CONEXIONES = 16
MAXIMO_RESPUESTA = 2 * 1024 * 1024

conexiones = asyncio.Semaphore(MAXIMO_CONEXIONES)

app = FastAPI(
    title="NeuroMedX Proxy",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    redirect_slashes=False,
)
# ==========================================
# CABECERAS CORS EN RESPUESTAS HTTP
# ==========================================

@app.middleware("http")
async def agregar_cors_respuesta(
    request: Request,
    call_next,
):
    respuesta = await call_next(request)

    origen = obtener_origen_cors(request)

    if origen is not None and request.method != "OPTIONS":

        cabeceras = generar_cabeceras_cors(origen)

        for nombre, valor in cabeceras.items():
            if nombre.lower() != "vary":
                respuesta.headers[nombre] = valor

    respuesta.headers.add_vary_header("Origin")

    return respuesta

def error(codigo: int, mensaje: str):
    return JSONResponse(
        status_code=codigo,
        content={"detail": mensaje},
        headers={"Cache-Control": "no-store"},
    )

@app.api_route(
    "/{ruta:path}",
    methods=[
        "GET", "POST", "PUT", "PATCH",
        "DELETE", "OPTIONS", "HEAD",
    ],
)
async def reenviar(request: Request, ruta: str):

    # 1. Verificar origen local
    if not request.client:
        return error(403, "Origen no autorizado.")

    if request.client.host != "127.0.0.1":
        return error(403, "Origen no autorizado.")

    # 2. Verificar dominio publico
    hosts = request.headers.getlist("host")

    if len(hosts) != 1 or hosts[0].lower() != HOST_PUBLICO:
        return error(403, "Dominio no autorizado.")

    # 3. Verificar ruta y metodo
    metodo = request.method
    path = request.scope["path"]

    preflight = es_preflight(request)

    if not preflight:
        if (metodo, path) not in RUTAS_PERMITIDAS:
            return error(404, "Ruta no disponible.")

    try:
        ruta_ascii = path.encode("ascii")
    except UnicodeEncodeError:
        return error(400, "Ruta invalida.")

    if request.scope.get("raw_path") != ruta_ascii:
        return error(400, "Ruta invalida.")

    if request.scope.get("query_string"):
        return error(400, "Parametros no permitidos.")

    if request.headers.getlist("origin"):
        if obtener_origen_cors(request) is None:
            return error_cors("Origen CORS no autorizado.")


    # Verificar autorizacion de funcionamiento
    if not servicio_habilitado(INDICADOR_PROXY):
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Servicio temporalmente no disponible."
            },
            headers={
                "Cache-Control": "no-store",
                "Retry-After": "60",
                "X-Content-Type-Options": "nosniff",
            },
        )

    # 4. Verificar configuracion interna
    if not re.fullmatch(r"[0-9a-f]{64}", CLAVE_INTERNA):
        return error(503, "Servicio no disponible.")

    # 5. Validar cabeceras
    try:
        ip_cliente = obtener_ip_cloudflare(request.headers)
        cabeceras = preparar_cabeceras(request.headers)
    except ValueError:
        return error(400, "Cabeceras invalidas.")


    # Limitar solicitudes preliminares por IP
    if preflight:
        try:
            limitar_preflight(ip_cliente)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers={
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                    **(exc.headers or {}),
                },
            )

    if request.headers.getlist("content-encoding"):
        return error(415, "Codificacion no permitida.")

    if metodo == "POST":
        tipo = cabeceras.get("content-type", "")
        tipo = tipo.split(";", 1)[0].strip().lower()

        if tipo != "application/json":
            return error(415, "Se requiere application/json.")

    # 6. Validar longitud declarada
    limite = LIMITES_CUERPO.get(
        path,
        LIMITE_CUERPO_PREDETERMINADO,
    )

    longitudes = request.headers.getlist("content-length")
    longitud_declarada = None

    if len(longitudes) > 1:
        return error(400, "Longitud invalida.")

    if longitudes:
        valor = longitudes[0]

        if not re.fullmatch(r"[0-9]{1,12}", valor):
            return error(400, "Longitud invalida.")

        longitud_declarada = int(valor)

        if longitud_declarada > limite:
            return error(413, "Solicitud demasiado grande.")

    if longitudes and request.headers.getlist("transfer-encoding"):
        return error(400, "Cabeceras de longitud incompatibles.")

    # 7. Limitar solicitudes simultaneas
    try:
        await asyncio.wait_for(
            conexiones.acquire(),
            timeout=TIMEOUT_POOL,
        )
    except TimeoutError:
        return error(503, "Servicio temporalmente ocupado.")

    try:
        # Procesar solicitudes preliminares CORS
        if preflight:

            if longitudes not in ([], ["0"]):
                return error(
                    400,
                    "Preflight con cuerpo no permitido.",
                )

            if request.headers.getlist("transfer-encoding"):
                return error(
                    400,
                    "Transferencia no permitida.",
                )

            try:
                with anyio.fail_after(TIMEOUT_RECEPCION):
                    async for fragmento in request.stream():
                        if fragmento:
                            return error(
                                400,
                                "Preflight con cuerpo no permitido.",
                            )

            except TimeoutError:
                return error(
                    408,
                    "Tiempo de recepcion agotado.",
                )

            except Exception:
                return error(400, "Solicitud incompleta.")

            return procesar_preflight(request)

        # 8. Recibir cuerpo con limite real y temporal
        cuerpo = bytearray()

        try:
            with anyio.fail_after(TIMEOUT_RECEPCION):
                async for fragmento in request.stream():

                    if len(cuerpo) + len(fragmento) > limite:
                        return error(
                            413,
                            "Solicitud demasiado grande.",
                        )

                    cuerpo.extend(fragmento)

        except TimeoutError:
            return error(408, "Tiempo de recepcion agotado.")
        except Exception:
            return error(400, "Solicitud incompleta.")

        if (
            longitud_declarada is not None
            and longitud_declarada != len(cuerpo)
        ):
            return error(400, "Longitud incorrecta.")

        # 9. Agregar cabeceras internas confiables
        cabeceras["x-neuromedx-client-ip"] = ip_cliente
        cabeceras["x-neuromedx-proxy-key"] = CLAVE_INTERNA
        cabeceras["accept-encoding"] = "identity"

        timeout = httpx.Timeout(
            connect=TIMEOUT_CONEXION,
            read=TIMEOUT_LECTURA,
            write=TIMEOUT_ESCRITURA,
            pool=TIMEOUT_POOL,
        )

        # 10. Reenviar exclusivamente al backend configurado
        try:
            with anyio.fail_after(
                TIMEOUT_CONEXION
                + TIMEOUT_ESCRITURA
                + TIMEOUT_LECTURA
                + TIMEOUT_POOL
            ):
                async with httpx.AsyncClient(
                    timeout=timeout,
                    follow_redirects=False,
                    trust_env=False,
                ) as cliente:

                    async with cliente.stream(
                        method=metodo,
                        url=f"{URL_BACKEND}{path}",
                        headers=cabeceras,
                        content=bytes(cuerpo),
                    ) as respuesta:

                        # Proteger detalles internos del backend
                        if 500 <= respuesta.status_code <= 599:
                            headers_error = {
                                "Cache-Control": "no-store",
                                "X-Content-Type-Options": "nosniff",
                            }

                            if "retry-after" in respuesta.headers:
                                headers_error["retry-after"] = (
                                    respuesta.headers["retry-after"]
                                )

                            return JSONResponse(
                                status_code=respuesta.status_code,
                                content={
                                    "detail": "Servicio temporalmente no disponible."
                                },
                                headers=headers_error,
                            )

                        codificaciones = respuesta.headers.get_list(
                            "content-encoding"
                        )

                        if codificaciones and (
                            len(codificaciones) != 1
                            or codificaciones[0].strip().lower() != "identity"
                        ):
                            return error(
                                502,
                                "Codificacion de respuesta no permitida.",
                            )

                        contenido = bytearray()

                        async for fragmento in respuesta.aiter_raw():
                            if (
                                len(contenido) + len(fragmento)
                                > MAXIMO_RESPUESTA
                            ):
                                return error(
                                    502,
                                    "Respuesta demasiado grande.",
                                )

                            contenido.extend(fragmento)

                        cabeceras_respuesta = {
                            "Cache-Control": "no-store",
                            "X-Content-Type-Options": "nosniff",
                        }

                        for nombre in (
                            "content-type",
                            "retry-after",
                            "www-authenticate",
                        ):
                            if nombre in respuesta.headers:
                                cabeceras_respuesta[nombre] = (
                                    respuesta.headers[nombre]
                                )

                        return Response(
                            content=bytes(contenido),
                            status_code=respuesta.status_code,
                            headers=cabeceras_respuesta,
                        )

        except (httpx.TimeoutException, TimeoutError):
            return error(504, "Tiempo de respuesta agotado.")

        except httpx.RequestError:
            return error(502, "Backend no disponible.")

    finally:
        conexiones.release()
