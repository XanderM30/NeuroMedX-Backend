from app.seguridad.limitador import limitador

from app.seguridad.configuracion import (
    VENTANA_SOLICITUDES,
    LIMITE_MEDICAMENTOS_UID,
    LIMITE_SINTOMAS_UID,
    LIMITE_REGISTRO_UID,
    LIMITE_PERFIL_UID,
)


def limitar_medicamentos(firebase_uid: str) -> None:
    limitador.verificar(
        clave=f"medicamentos:{firebase_uid}",
        limite=LIMITE_MEDICAMENTOS_UID,
        ventana=VENTANA_SOLICITUDES
    )


def limitar_sintomas(firebase_uid: str) -> None:
    limitador.verificar(
        clave=f"sintomas:{firebase_uid}",
        limite=LIMITE_SINTOMAS_UID,
        ventana=VENTANA_SOLICITUDES
    )


def limitar_registro(firebase_uid: str) -> None:
    limitador.verificar(
        clave=f"registro:{firebase_uid}",
        limite=LIMITE_REGISTRO_UID,
        ventana=VENTANA_SOLICITUDES
    )


def limitar_perfil(firebase_uid: str) -> None:
    limitador.verificar(
        clave=f"perfil:{firebase_uid}",
        limite=LIMITE_PERFIL_UID,
        ventana=VENTANA_SOLICITUDES
    )