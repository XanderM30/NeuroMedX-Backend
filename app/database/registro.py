
from fastapi import HTTPException, status

from app.auth.firebase import verificar_token_firebase
from app.database.usuarios import crear_usuario_paciente


def registrar_paciente_firebase(
    token: str,
    nombre: str,
    apellido: str
) -> dict:
    """
    Verifica la identidad de Firebase y registra
    al paciente en PostgreSQL.
    """

    # Verificar el token de Firebase
    datos_firebase = verificar_token_firebase(token)

    firebase_uid = datos_firebase.get("uid")
    correo = datos_firebase.get("email")

    if not firebase_uid or not correo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La identidad de Firebase no contiene UID o correo válido"
        )

    # Registrar usuario y perfil de paciente
    try:
        resultado = crear_usuario_paciente(
            firebase_uid=firebase_uid,
            correo=correo,
            nombre=nombre,
            apellido=apellido
        )

        return {
            "estado": "correcto",
            "mensaje": (
                "El paciente ya estaba registrado"
                if resultado["existente"]
                else "Paciente registrado correctamente"
            ),
            **resultado
        }

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error)
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No fue posible registrar el paciente en PostgreSQL"
        ) from error
