from fastapi import Depends, HTTPException, status

from app.auth.dependencies import obtener_usuario_autenticado
from app.database.medicos import obtener_medico_por_usuario_id
from app.seguridad.politicas import limitar_perfil


def obtener_medico_autenticado(
    usuario: dict = Depends(obtener_usuario_autenticado),
) -> dict:
    """
    Autoriza la consulta del perfil medico propio.
    Permite consultar los tres estados de verificacion.
    """

    limitar_perfil(usuario["firebase_uid"])

    if usuario["rol"] != "medico":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere una cuenta de medico",
        )

    try:
        medico = obtener_medico_por_usuario_id(
            usuario["id"]
        )

    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No fue posible consultar el perfil medico",
        ) from error

    if medico is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No existe un perfil medico asociado a la cuenta",
        )

    return {
        "usuario": usuario,
        "medico": medico,
    }

def obtener_medico_verificado(
    perfil: dict = Depends(obtener_medico_autenticado),
) -> dict:
    """
    Exige que el medico tenga una cuenta activa
    y una verificacion profesional aprobada.
    """

    usuario = perfil["usuario"]
    medico = perfil["medico"]

    if usuario["estado"] is not True:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta de usuario se encuentra desactivada",
        )

    if medico["estado_verificacion"] != "verificado":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere una verificacion profesional aprobada",
        )

    return perfil
