from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database.medicos import (
    crear_perfil_medico,
    obtener_medico_por_usuario_id,
)


pytestmark = [
    pytest.mark.integracion,
    pytest.mark.postgresql,
]


def crear_usuario(conn):
    identificador = uuid4().hex

    return conn.execute(
        text("""
            INSERT INTO public.usuarios (
                firebase_uid,
                correo,
                nombre,
                apellido,
                rol
            )
            VALUES (
                :uid,
                :correo,
                'Prueba',
                'Temporal',
                'medico'
            )
            RETURNING id
        """),
        {
            "uid": f"prueba_{identificador}",
            "correo": f"prueba_{identificador}@example.invalid",
        },
    ).scalar_one()


def generar_cedula():
    return str(uuid4().int)[:30]


def crear_medico(conn, usuario_id, cedula=None):
    return crear_perfil_medico(
        connection=conn,
        usuario_id=usuario_id,
        cedula_profesional=(
            generar_cedula() if cedula is None else cedula
        ),
        especialidad="Medicina general",
        institucion_formacion="Universidad de prueba",
    )


def test_crear_perfil_medico(
    conexion_postgresql_pruebas,
):
    conn = conexion_postgresql_pruebas
    usuario_id = crear_usuario(conn)

    resultado = crear_medico(conn, usuario_id)

    assert resultado["medico_id"]
    assert resultado["usuario_id"] == str(usuario_id)


def test_datos_profesionales(
    conexion_postgresql_pruebas,
):
    conn = conexion_postgresql_pruebas
    usuario_id = crear_usuario(conn)
    cedula = generar_cedula()

    resultado = crear_medico(conn, usuario_id, cedula)

    assert resultado["cedula_profesional"] == cedula
    assert resultado["especialidad"] == "Medicina general"
    assert (
        resultado["institucion_formacion"]
        == "Universidad de prueba"
    )


def test_estado_inicial_pendiente(
    conexion_postgresql_pruebas,
):
    conn = conexion_postgresql_pruebas
    usuario_id = crear_usuario(conn)

    resultado = crear_medico(conn, usuario_id)

    assert resultado["estado_verificacion"] == "pendiente"


def test_fecha_registro(
    conexion_postgresql_pruebas,
):
    conn = conexion_postgresql_pruebas
    usuario_id = crear_usuario(conn)

    resultado = crear_medico(conn, usuario_id)

    assert isinstance(
        resultado["fecha_registro"],
        datetime,
    )


def test_cedula_duplicada(
    conexion_postgresql_pruebas,
):
    conn = conexion_postgresql_pruebas
    usuario1 = crear_usuario(conn)
    usuario2 = crear_usuario(conn)
    cedula = generar_cedula()

    crear_medico(conn, usuario1, cedula)

    with pytest.raises(IntegrityError) as captura:
        with conn.begin_nested():
            crear_medico(conn, usuario2, cedula)

    assert captura.value.orig.sqlstate == "23505"
    assert (
        captura.value.orig.diag.constraint_name
        == "medicos_cedula_profesional_key"
    )


def test_perfil_duplicado(
    conexion_postgresql_pruebas,
):
    conn = conexion_postgresql_pruebas
    usuario_id = crear_usuario(conn)

    crear_medico(conn, usuario_id)

    with pytest.raises(IntegrityError) as captura:
        with conn.begin_nested():
            crear_medico(conn, usuario_id)

    assert captura.value.orig.sqlstate == "23505"
    assert (
        captura.value.orig.diag.constraint_name
        == "medicos_usuario_id_key"
    )


def test_obtener_perfil_existente(
    conexion_postgresql_pruebas,
    monkeypatch,
):
    conn = conexion_postgresql_pruebas
    usuario_id = crear_usuario(conn)
    creado = crear_medico(conn, usuario_id)

    from contextlib import nullcontext
    import app.database.connection as modulo_conexion

    class EnginePruebas:
        def connect(self):
            return nullcontext(conn)

    monkeypatch.setattr(
        modulo_conexion,
        "engine",
        EnginePruebas(),
    )

    resultado = obtener_medico_por_usuario_id(usuario_id)

    assert resultado is not None
    assert str(resultado["id"]) == creado["medico_id"]
    assert resultado["usuario_id"] == usuario_id
    assert resultado["estado_verificacion"] == "pendiente"
    assert (
        resultado["cedula_profesional"]
        == creado["cedula_profesional"]
    )


def test_obtener_perfil_inexistente(
    conexion_postgresql_pruebas,
    monkeypatch,
):
    conn = conexion_postgresql_pruebas

    from contextlib import nullcontext
    import app.database.connection as modulo_conexion

    class EnginePruebas:
        def connect(self):
            return nullcontext(conn)

    monkeypatch.setattr(
        modulo_conexion,
        "engine",
        EnginePruebas(),
    )

    resultado = obtener_medico_por_usuario_id(uuid4())

    assert resultado is None
