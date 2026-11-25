
from sqlalchemy import text
from sqlalchemy.engine import Connection


def crear_perfil_paciente(
    connection: Connection,
    usuario_id
) -> dict:
    """
    Crea el perfil de paciente dentro de una
    transacción existente.
    """

    paciente_id = connection.execute(
        text("""
            INSERT INTO pacientes (usuario_id)
            VALUES (:usuario_id)
            RETURNING id
        """),
        {"usuario_id": usuario_id}
    ).scalar_one()

    return {
        "paciente_id": str(paciente_id),
        "usuario_id": str(usuario_id)
    }


def obtener_paciente_por_usuario_id(
    usuario_id
) -> dict | None:
    """
    Consulta el perfil de paciente relacionado
    con un usuario de NeuroMedX.
    """

    from app.database.connection import engine

    with engine.connect() as connection:
        paciente = connection.execute(
            text("""
                SELECT
                    id,
                    usuario_id,
                    fecha_nacimiento,
                    telefono,
                    contacto_emergencia,
                    telefono_emergencia,
                    fecha_registro
                FROM pacientes
                WHERE usuario_id = :usuario_id
            """),
            {"usuario_id": usuario_id}
        ).mappings().one_or_none()

        return dict(paciente) if paciente else None
