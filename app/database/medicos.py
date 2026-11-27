from sqlalchemy import text
from sqlalchemy.engine import Connection


def crear_perfil_medico(
    connection: Connection,
    usuario_id,
    cedula_profesional: str,
    especialidad: str,
    institucion_formacion: str,
) -> dict:
    """
    Crea el perfil medico dentro de una
    transaccion existente.

    El estado inicial siempre es pendiente.
    """

    medico = connection.execute(
        text("""
            INSERT INTO public.medicos (
                usuario_id,
                cedula_profesional,
                especialidad,
                institucion_formacion,
                estado_verificacion
            )
            VALUES (
                :usuario_id,
                :cedula_profesional,
                :especialidad,
                :institucion_formacion,
                'pendiente'
            )
            RETURNING
                id,
                usuario_id,
                cedula_profesional,
                especialidad,
                institucion_formacion,
                estado_verificacion,
                fecha_registro
        """),
        {
            "usuario_id": usuario_id,
            "cedula_profesional": cedula_profesional,
            "especialidad": especialidad,
            "institucion_formacion": institucion_formacion,
        }
    ).mappings().one()

    return {
        "medico_id": str(medico["id"]),
        "usuario_id": str(medico["usuario_id"]),
        "cedula_profesional": medico["cedula_profesional"],
        "especialidad": medico["especialidad"],
        "institucion_formacion": medico["institucion_formacion"],
        "estado_verificacion": medico["estado_verificacion"],
        "fecha_registro": medico["fecha_registro"],
    }


def obtener_medico_por_usuario_id(
    usuario_id,
) -> dict | None:
    """
    Consulta el perfil profesional relacionado
    con un usuario de NeuroMedX.
    """

    from app.database.connection import engine

    with engine.connect() as connection:
        medico = connection.execute(
            text("""
                SELECT
                    id,
                    usuario_id,
                    cedula_profesional,
                    especialidad,
                    institucion_formacion,
                    estado_verificacion,
                    fecha_registro
                FROM public.medicos
                WHERE usuario_id = :usuario_id
            """),
            {"usuario_id": usuario_id}
        ).mappings().one_or_none()

        return dict(medico) if medico else None
