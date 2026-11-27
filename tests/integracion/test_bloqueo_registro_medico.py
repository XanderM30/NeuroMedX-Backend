from time import monotonic
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

import app.database.usuarios as modulo_usuarios

from app.database.excepciones import (
    RegistroTemporalmenteNoDisponible,
)


pytestmark = [
    pytest.mark.integracion,
    pytest.mark.postgresql,
]


def test_tiempo_espera_bloqueo(
    engine_postgresql_pruebas,
    monkeypatch,
):
    engine = engine_postgresql_pruebas

    identificador = uuid4().hex
    uid = f"prueba_{identificador}"

    datos = {
        "firebase_uid": uid,
        "correo": f"prueba_{identificador}@example.invalid",
        "nombre": "Nombre",
        "apellido": "Apellido",
        "cedula_profesional": str(uuid4().int)[:30],
        "especialidad": "Medicina general",
        "institucion_formacion": "Universidad de prueba",
    }

    clave = "neuromedx:registro:medico:" + uid

    monkeypatch.setattr(
        modulo_usuarios,
        "engine",
        engine,
    )

    with engine.connect() as conn:

        transaccion = conn.begin()

        try:
            conn.execute(
                text("""
                    SELECT pg_advisory_xact_lock(
                        hashtextextended(:clave, 0)
                    )
                """),
                {"clave": clave},
            )

            inicio = monotonic()

            with pytest.raises(
                RegistroTemporalmenteNoDisponible
            ) as captura:

                modulo_usuarios.crear_usuario_medico(
                    **datos
                )

            duracion = monotonic() - inicio

            causa = captura.value.__cause__

            assert isinstance(causa, OperationalError)
            assert causa.orig.sqlstate == "55P03"

            assert 4.5 <= duracion <= 15

            print(
                f"\nTiempo de espera: {duracion:.2f} segundos"
            )

        finally:
            transaccion.rollback()

    # Comprobar liberacion del bloqueo y ausencia de datos

    with engine.begin() as conn:

        bloqueo_disponible = conn.execute(
            text("""
                SELECT pg_try_advisory_xact_lock(
                    hashtextextended(:clave, 0)
                )
            """),
            {"clave": clave},
        ).scalar_one()

        assert bloqueo_disponible is True

        usuarios = conn.execute(
            text("""
                SELECT COUNT(*)
                FROM public.usuarios
                WHERE firebase_uid = :uid
            """),
            {"uid": uid},
        ).scalar_one()

        medicos = conn.execute(
            text("""
                SELECT COUNT(*)
                FROM public.medicos
                WHERE cedula_profesional = :cedula
            """),
            {"cedula": datos["cedula_profesional"]},
        ).scalar_one()

        assert usuarios == 0
        assert medicos == 0

        print("Bloqueo liberado correctamente")
        print("Usuarios residuales:", usuarios)
        print("Medicos residuales:", medicos)
