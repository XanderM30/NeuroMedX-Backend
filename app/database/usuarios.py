
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.database.connection import engine
from app.database.pacientes import crear_perfil_paciente
from app.database.medicos import crear_perfil_medico
from app.database.excepciones import RegistroTemporalmenteNoDisponible


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


def crear_usuario_medico(
    firebase_uid: str,
    correo: str,
    nombre: str,
    apellido: str,
    cedula_profesional: str,
    especialidad: str,
    institucion_formacion: str,
) -> dict:
    """
    Crea un usuario medico y su perfil profesional
    dentro de una sola transaccion.
    """

    firebase_uid = firebase_uid.strip()
    correo = correo.strip().lower()
    nombre = nombre.strip()
    apellido = apellido.strip()
    cedula_profesional = cedula_profesional.strip()
    espacios_profesionales = (
        "\u0009\u000a\u000b\u000c\u000d\u0020"
        "\u0085\u00a0\u1680"
        "\u2000\u2001\u2002\u2003\u2004\u2005"
        "\u2006\u2007\u2008\u2009\u200a"
        "\u2028\u2029\u202f\u205f\u3000\ufeff"
    )

    especialidad = especialidad.strip(
        espacios_profesionales
    )

    institucion_formacion = institucion_formacion.strip(
        espacios_profesionales
    )

    # Validar datos personales

    if not firebase_uid or len(firebase_uid) > 128:
        raise ValueError("UID de Firebase invalido")

    if (
        not correo
        or len(correo) > 255
        or "@" not in correo
    ):
        raise ValueError("Correo electronico invalido")

    if not 2 <= len(nombre) <= 100:
        raise ValueError("Nombre invalido")

    if not 2 <= len(apellido) <= 100:
        raise ValueError("Apellido invalido")

    # Validar datos profesionales

    if (
        not 1 <= len(cedula_profesional) <= 30
        or not cedula_profesional.isascii()
        or not cedula_profesional.isdigit()
    ):
        raise ValueError("Cedula profesional invalida")

    if not 2 <= len(especialidad) <= 150:
        raise ValueError("Especialidad invalida")

    if not 2 <= len(institucion_formacion) <= 200:
        raise ValueError("Institucion de formacion invalida")

    try:
        with engine.begin() as connection:

            # Limitar el tiempo de espera de bloqueos
            connection.execute(
                text("SET LOCAL lock_timeout = '5s'")
            )

            # Serializar registros del mismo UID
            connection.execute(
                text("""
                    SELECT pg_advisory_xact_lock(
                        hashtextextended(:clave, 0)
                    )
                """),
                {
                    "clave": (
                        "neuromedx:registro:medico:"
                        + firebase_uid
                    )
                },
            )

            # Buscar una cuenta existente

            usuario = connection.execute(
                text("""
                    SELECT
                        id,
                        correo,
                        rol,
                        estado
                    FROM public.usuarios
                    WHERE firebase_uid = :firebase_uid
                """),
                {"firebase_uid": firebase_uid},
            ).mappings().one_or_none()

            if usuario is not None:

                if usuario["rol"] != "medico":
                    raise ValueError(
                        "La cuenta existente no corresponde a un medico"
                    )

                if not usuario["estado"]:
                    raise ValueError(
                        "La cuenta se encuentra desactivada"
                    )

                if usuario["correo"] != correo:
                    raise ValueError(
                        "El correo no coincide con la cuenta registrada"
                    )

                medico = connection.execute(
                    text("""
                        SELECT
                            id,
                            cedula_profesional,
                            especialidad,
                            institucion_formacion,
                            estado_verificacion,
                            fecha_registro
                        FROM public.medicos
                        WHERE usuario_id = :usuario_id
                    """),
                    {"usuario_id": usuario["id"]},
                ).mappings().one_or_none()

                if medico is None:
                    raise ValueError(
                        "La cuenta medica tiene un perfil incompleto"
                    )

                if (
                    medico["cedula_profesional"] != cedula_profesional
                    or medico["especialidad"] != especialidad
                    or medico["institucion_formacion"]
                    != institucion_formacion
                ):
                    raise ValueError(
                        "Los datos profesionales no coinciden "
                        "con el perfil registrado"
                    )

                return {
                    "usuario_id": str(usuario["id"]),
                    "medico_id": str(medico["id"]),
                    "correo": usuario["correo"],
                    "rol": usuario["rol"],
                    "estado": usuario["estado"],
                    "cedula_profesional": medico["cedula_profesional"],
                    "especialidad": medico["especialidad"],
                    "institucion_formacion": medico["institucion_formacion"],
                    "estado_verificacion": medico["estado_verificacion"],
                    "fecha_registro": medico["fecha_registro"],
                    "existente": True,
                }

            # Comprobar correo duplicado

            correo_existente = connection.execute(
                text("""
                    SELECT id
                    FROM public.usuarios
                    WHERE correo = :correo
                """),
                {"correo": correo},
            ).scalar_one_or_none()

            if correo_existente is not None:
                raise ValueError(
                    "El correo ya esta asociado a otra cuenta"
                )

            # Comprobar cedula duplicada

            cedula_existente = connection.execute(
                text("""
                    SELECT id
                    FROM public.medicos
                    WHERE cedula_profesional = :cedula
                """),
                {"cedula": cedula_profesional},
            ).scalar_one_or_none()

            if cedula_existente is not None:
                raise ValueError(
                    "La cedula profesional ya se encuentra registrada"
                )

            # Crear usuario con rol fijo

            usuario_id = connection.execute(
                text("""
                    INSERT INTO public.usuarios (
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
                        'medico',
                        TRUE
                    )
                    RETURNING id
                """),
                {
                    "firebase_uid": firebase_uid,
                    "correo": correo,
                    "nombre": nombre,
                    "apellido": apellido,
                },
            ).scalar_one()

            # Crear perfil profesional

            perfil = crear_perfil_medico(
                connection=connection,
                usuario_id=usuario_id,
                cedula_profesional=cedula_profesional,
                especialidad=especialidad,
                institucion_formacion=institucion_formacion,
            )

            return {
                **perfil,
                "correo": correo,
                "rol": "medico",
                "estado": True,
                "existente": False,
            }

    except OperationalError as error:

        codigo = getattr(error.orig, "sqlstate", None)

        if codigo == "55P03":
            raise RegistroTemporalmenteNoDisponible(
                "El registro esta ocupado temporalmente. "
                "Intenta nuevamente."
            ) from error

        raise

    except IntegrityError as error:

        restriccion = getattr(
            getattr(error.orig, "diag", None),
            "constraint_name",
            None,
        )

        if restriccion == "medicos_cedula_profesional_key":
            raise ValueError(
                "La cedula profesional ya se encuentra registrada"
            ) from error

        if restriccion == "usuarios_correo_key":
            raise ValueError(
                "El correo ya esta asociado a otra cuenta"
            ) from error

        if restriccion == "usuarios_firebase_uid_key":
            raise ValueError(
                "La cuenta ya se encuentra registrada"
            ) from error

        if restriccion == "medicos_usuario_id_key":
            raise ValueError(
                "El perfil medico ya se encuentra registrado"
            ) from error

        raise
