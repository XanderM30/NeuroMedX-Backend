from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

from app.seguridad.limitador import limitador
from app.seguridad.confianza_proxy import obtener_ip_cliente
from app.seguridad.configuracion import (
    LIMITE_GENERAL_IP,
    VENTANA_SOLICITUDES,
)


async def proteger_solicitudes(request: Request, call_next):

    try:
        # Obtener la IP directa o validada por el proxy
        ip_cliente = obtener_ip_cliente(request)

        # Aplicar el limite antes de la autenticacion
        limitador.verificar(
            clave=f"general:{ip_cliente}",
            limite=LIMITE_GENERAL_IP,
            ventana=VENTANA_SOLICITUDES,
        )

    except HTTPException as error:
        return JSONResponse(
            status_code=error.status_code,
            content={
                "detail": error.detail
            },
            headers=error.headers,
        )

    return await call_next(request)
