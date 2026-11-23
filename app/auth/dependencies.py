
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import text

from app.auth.firebase import verificar_token_firebase
from app.database.connection import engine

bearer_scheme = HTTPBearer(auto_error=False)


def obtener_usuario_autenticado(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> dict:

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere autenticación"
        )

    # Verificar identidad mediante Firebase
    datos_firebase = verificar_token_firebase(
        credentials.credentials
    )

    firebase_uid = datos_firebase.get("uid")

    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La identidad de Firebase no contiene un UID válido"
        )

    # Buscar el perfil correspondiente en PostgreSQL
    try:
        with engine.connect() as connection:
            resultado = connection.execute(
                text("""
                    SELECT
                        id,
                        firebase_uid,
                        correo,
                        nombre,
                        apellido,
                        rol,
                        estado
                    FROM usuarios
                    WHERE firebase_uid = :firebase_uid
                """),
                {"firebase_uid": firebase_uid}
            )

            usuario = resultado.mappings().one_or_none()

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No fue posible consultar el perfil del usuario"
        )

    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no tiene un perfil registrado en NeuroMedX Connect"
        )

    if not usuario["estado"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta de usuario se encuentra desactivada"
        )

    return dict(usuario)
