import os

from fastapi import Depends, HTTPException

from app.auth.dependencies import obtener_usuario_autenticado


def verificar_acceso_experimental(
    usuario: dict = Depends(obtener_usuario_autenticado),
) -> dict:

    habilitada = (
        os.getenv("IA_SINTOMAS_HABILITADA", "false")
        .strip()
        .lower() == "true"
    )

    if not habilitada:
        raise HTTPException(
            status_code=503,
            detail="La IA de sintomas experimental no esta habilitada.",
        )

    autorizados = {
        uid.strip()
        for uid in os.getenv(
            "IA_SINTOMAS_USUARIOS_AUTORIZADOS", ""
        ).split(",")
        if uid.strip()
    }

    firebase_uid = usuario.get("firebase_uid")

    if not firebase_uid or firebase_uid not in autorizados:
        raise HTTPException(
            status_code=403,
            detail="Usuario no autorizado para las pruebas experimentales.",
        )

    return usuario
