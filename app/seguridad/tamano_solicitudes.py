from time import monotonic

import anyio

from starlette.responses import JSONResponse
from app.seguridad.configuracion import (
    TIEMPO_MAXIMO_RECEPCION_HTTP,
)


# Limites expresados en bytes
LIMITES_POR_RUTA = {
    "/usuarios/registro-paciente": 4 * 1024,
    "/usuarios/registro-medico": 4 * 1024,
    "/ia/medicamentos/detectar": 128 * 1024,
    "/ia/sintomas/analizar": 32 * 1024,
    "/pulsera/mediciones": 16 * 1024,
}

LIMITE_PREDETERMINADO = 16 * 1024


class LimitarTamanoSolicitudes:

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        ruta = scope.get("path", "").rstrip("/")

        limite = LIMITES_POR_RUTA.get(
            ruta,
            LIMITE_PREDETERMINADO
        )

        async def rechazar_solicitud(codigo, detalle):
            respuesta = JSONResponse(
                status_code=codigo,
                content={"detail": detalle},
            )

            await respuesta(scope, receive, send)

        # Comprobar Content-Length
        longitudes = [
            valor
            for nombre, valor in scope.get("headers", [])
            if nombre.lower() == b"content-length"
        ]

        if longitudes:

            if len(longitudes) != 1:
                await rechazar_solicitud(
                    400,
                    "Cabecera Content-Length duplicada."
                )
                return

            valor = longitudes[0]

            if not valor.isdigit() or len(valor) > 20:
                await rechazar_solicitud(
                    400,
                    "Cabecera Content-Length no valida."
                )
                return

            longitud = int(valor)

            if longitud > limite:
                await rechazar_solicitud(
                    413,
                    "El cuerpo de la solicitud supera el limite permitido."
                )
                return

        # Control del tiempo total de recepcion
        inicio = monotonic()
        cuerpo = bytearray()

        while True:

            tiempo_restante = (
                TIEMPO_MAXIMO_RECEPCION_HTTP
                - (monotonic() - inicio)
            )

            if tiempo_restante <= 0:
                await rechazar_solicitud(
                    408,
                    "Tiempo maximo de recepcion agotado."
                )
                return

            try:
                with anyio.fail_after(tiempo_restante):
                    mensaje = await receive()

            except TimeoutError:
                await rechazar_solicitud(
                    408,
                    "Tiempo maximo de recepcion agotado."
                )
                return

            if mensaje["type"] == "http.disconnect":
                return

            if mensaje["type"] != "http.request":
                continue

            fragmento = mensaje.get("body", b"")

            if len(cuerpo) + len(fragmento) > limite:
                await rechazar_solicitud(
                    413,
                    "El cuerpo de la solicitud supera el limite permitido."
                )
                return

            cuerpo.extend(fragmento)

            if not mensaje.get("more_body", False):
                break

        # Entregar el cuerpo validado a FastAPI
        entregado = False

        async def recibir_cuerpo():

            nonlocal entregado

            if not entregado:
                entregado = True

                return {
                    "type": "http.request",
                    "body": bytes(cuerpo),
                    "more_body": False,
                }

            return await receive()

        await self.app(
            scope,
            recibir_cuerpo,
            send
        )