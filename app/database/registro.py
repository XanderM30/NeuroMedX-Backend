
from fastapi import HTTPException, status

from app.auth.firebase import verificar_token_firebase
from app.database.usuarios import (
    crear_usuario_paciente,
    crear_usuario_medico,
)
from app.database.excepciones import RegistroTemporalmenteNoDisponible
from app.seguridad.politicas import limitar_registro


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

    # Exigir correo electrónico verificado
    if datos_firebase.get("email_verified") is not True:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes verificar tu correo electrónico antes de registrarte"
        )

    firebase_uid = datos_firebase.get("uid")
    correo = datos_firebase.get("email")

    if not firebase_uid or not correo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La identidad de Firebase no contiene UID o correo válido"
        )

    # Limitar solicitudes por UID verificado
    limitar_registro(firebase_uid)

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

def registrar_medico_firebase(
    token: str,
    nombre: str,
    apellido: str,
    cedula_profesional: str,
    especialidad: str,
    institucion_formacion: str,
) -> dict:
    """
    Verifica la identidad de Firebase y registra
    al medico de forma transaccional en PostgreSQL.
    """

    datos_firebase = verificar_token_firebase(token)

    if datos_firebase.get("email_verified") is not True:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes verificar tu correo antes de registrarte"
        )

    firebase_uid = datos_firebase.get("uid")
    correo = datos_firebase.get("email")

    if (
        not isinstance(firebase_uid, str)
        or not firebase_uid.strip()
        or len(firebase_uid) > 128
        or not isinstance(correo, str)
        or not correo.strip()
        or len(correo) > 255
        or "@" not in correo
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La identidad de Firebase no contiene UID o correo valido"
        )

    firebase_uid = firebase_uid.strip()
    correo = correo.strip().lower()

    limitar_registro(firebase_uid)

    try:
        resultado = crear_usuario_medico(
            firebase_uid=firebase_uid,
            correo=correo,
            nombre=nombre,
            apellido=apellido,
            cedula_profesional=cedula_profesional,
            especialidad=especialidad,
            institucion_formacion=institucion_formacion,
        )

        return {
            **resultado,
            "estado_cuenta": resultado["estado"],
            "estado": "correcto",
            "mensaje": (
                "El medico ya estaba registrado"
                if resultado["existente"]
                else "Medico registrado correctamente"
            ),
        }

    except RegistroTemporalmenteNoDisponible as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El registro esta ocupado temporalmente. Intenta nuevamente.",
            headers={"Retry-After": "5"},
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible completar el registro con los datos proporcionados"
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No fue posible registrar el medico en PostgreSQL"
        ) from error
