import os
import re
from hmac import compare_digest
from ipaddress import ip_address

from dotenv import load_dotenv
from fastapi import Request, HTTPException

load_dotenv()

CLAVE_INTERNA = os.getenv("PROXY_CLAVE_INTERNA", "")


def obtener_ip_cliente(request: Request) -> str:
    ip_directa = (
        request.client.host
        if request.client
        else "desconocida"
    )

    claves = request.headers.getlist(
        "x-neuromedx-proxy-key"
    )

    direcciones = request.headers.getlist(
        "x-neuromedx-client-ip"
    )

    # Solicitud directa sin cabeceras internas
    if not claves and not direcciones:
        return ip_directa

    # Rechazar cabeceras incompletas o duplicadas
    if len(claves) != 1 or len(direcciones) != 1:
        raise HTTPException(
            status_code=403,
            detail="Cabeceras internas invalidas."
        )

    # Restringir el origen del proxy autorizado
    if ip_directa != "10.242.46.163":
        raise HTTPException(
            status_code=403,
            detail="Origen del proxy no autorizado."
        )

    # Verificar la credencial interna
    if (
        not re.fullmatch(r"[0-9a-f]{64}", CLAVE_INTERNA)
        or not re.fullmatch(r"[0-9a-f]{64}", claves[0])
        or not compare_digest(CLAVE_INTERNA, claves[0])
    ):
        raise HTTPException(
            status_code=403,
            detail="Proxy no autorizado."
        )

    # Validar la direccion reenviada
    try:
        valor = direcciones[0].strip()

        if "," in valor or "%" in valor:
            raise ValueError()

        return str(ip_address(valor))

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Direccion IP reenviada invalida."
        ) from None
