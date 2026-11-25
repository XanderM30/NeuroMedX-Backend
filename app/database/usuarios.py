
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database.connection import engine
from app.database.pacientes import crear_perfil_paciente


def crear_usuario_paciente(
    firebase_uid: str,
    correo: str,
    nombre: str,
    apellido: str
) -> dict:
    """
    Crea un usuario paciente y su perfil en PostgreSQL.
    Ambas operaciones utilizan una sola transacción.
    """

    firebase_uid = firebase_uid.strip()
    correo = correo.strip().lower()
    nombre = nombre.strip()
    apellido = apellido.strip()

    if not all([firebase_uid, correo, nombre, apellido]):
        raise ValueError("Todos los datos del paciente son obligatorios")

    try:
        with engine.begin() as connection:

            # Buscar usuario existente
            usuario = connection.execute(
                text("""
                    SELECT id, firebase_uid, correo, nombre,
                           apellido, rol, estado
                    FROM usuarios
                    WHERE firebase_uid = :firebase_uid
                """),
                {"firebase_uid": firebase_uid}
            ).mappings().one_or_none()

            if usuario is not None:

                if usuario["rol"] != "paciente":
                    raise ValueError(
                         "La cuenta existente no corresponde a un paciente"
                   )

                if not usuario["estado"]:
                    raise ValueError(
                         "La cuenta de paciente se encuentra desactivada"
                   )


                paciente = connection.execute(
                    text("""
                        SELECT id
                        FROM pacientes
                        WHERE usuario_id = :usuario_id
                    """),
                    {"usuario_id": usuario["id"]}
                ).mappings().one_or_none()

                if paciente is None:
                    perfil = crear_perfil_paciente(
                        connection,
                        usuario["id"]
                    )
                    paciente_id = perfil["paciente_id"]
                else:
                    paciente_id = str(paciente["id"])

                return {
                    "usuario_id": str(usuario["id"]),
                    "paciente_id": paciente_id,
                    "correo": usuario["correo"],
                    "rol": usuario["rol"],
                    "estado": usuario["estado"],
                    "existente": True
                }

            # Evitar duplicar correos
            correo_existente = connection.execute(
                text("""
                    SELECT id
                    FROM usuarios
                    WHERE correo = :correo
                """),
                {"correo": correo}
            ).scalar_one_or_none()

            if correo_existente is not None:
                raise ValueError(
                    "El correo ya está asociado a otra cuenta"
                )

            # Crear usuario con rol fijo
            usuario_id = connection.execute(
                text("""
                    INSERT INTO usuarios (
                        firebase_uid,
                        correo,
                        nombre,
                        apellido,
                        rol,
                        estado
                    )
                    VALUES (
                        :firebase_uid,
                        :correo,
                        :nombre,
                        :apellido,
                        'paciente',
                        TRUE
                    )
                    RETURNING id
                """),
                {
                    "firebase_uid": firebase_uid,
                    "correo": correo,
                    "nombre": nombre,
                    "apellido": apellido
                }
            ).scalar_one()

            # Crear su perfil de paciente
            perfil = crear_perfil_paciente(
                connection,
                usuario_id
            )

            return {
                "usuario_id": str(usuario_id),
                "paciente_id": perfil["paciente_id"],
                "correo": correo,
                "rol": "paciente",
                "estado": True,
                "existente": False
            }

    except IntegrityError as error:
        raise ValueError(
            "El usuario o su correo ya se encuentran registrados"
        ) from error


def obtener_usuario_por_firebase_uid(firebase_uid: str):
    """Consulta un usuario mediante su UID de Firebase."""

    with engine.connect() as connection:
        usuario = connection.execute(
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
        ).mappings().one_or_none()

        return dict(usuario) if usuario else None
