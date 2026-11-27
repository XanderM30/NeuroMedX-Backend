from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


pytestmark = [
    pytest.mark.integracion,
    pytest.mark.postgresql,
]


def generar_cedula():
    return str(uuid4().int)[:30]


def crear_usuario(conn):
    identificador = uuid4().hex

    return conn.execute(text("""
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
    """), {
        "uid": f"prueba_{identificador}",
        "correo": f"prueba_{identificador}@example.invalid",
    }).scalar_one()


def insertar_medico(conn, usuario_id, cambios=None):
    datos = {
        "usuario_id": usuario_id,
        "cedula": generar_cedula(),
        "especialidad": "Medicina general",
        "institucion": "Universidad de prueba",
        "estado": "pendiente",
    }

    datos.update(cambios or {})

    return conn.execute(text("""
        INSERT INTO public.medicos (
            usuario_id,
            cedula_profesional,
            especialidad,
            institucion_formacion,
            estado_verificacion
        )
        VALUES (
            :usuario_id,
            :cedula,
            :especialidad,
            :institucion,
            :estado
        )
        RETURNING id, estado_verificacion
    """), datos).mappings().one()


def comprobar_error(conn, operacion, codigo, restriccion=None):
    with pytest.raises(IntegrityError) as captura:
        with conn.begin_nested():
            operacion()

    error = captura.value.orig

    assert error.sqlstate == codigo

    if restriccion is not None:
        assert error.diag.constraint_name == restriccion


def test_medico_valido(conexion_postgresql_pruebas):
    conn = conexion_postgresql_pruebas
    usuario = crear_usuario(conn)
    resultado = insertar_medico(conn, usuario)

    assert resultado["id"] is not None
    assert resultado["estado_verificacion"] == "pendiente"


def test_estado_predeterminado(conexion_postgresql_pruebas):
    conn = conexion_postgresql_pruebas
    usuario = crear_usuario(conn)

    estado = conn.execute(text("""
        INSERT INTO public.medicos (
            usuario_id,
            cedula_profesional,
            especialidad,
            institucion_formacion
        )
        VALUES (
            :usuario,
            :cedula,
            'Medicina general',
            'Universidad de prueba'
        )
        RETURNING estado_verificacion
    """), {
        "usuario": usuario,
        "cedula": generar_cedula(),
    }).scalar_one()

    assert estado == "pendiente"


@pytest.mark.parametrize(
    "campo,columna",
    [
        ("cedula", "cedula_profesional"),
        ("especialidad", "especialidad"),
        ("institucion", "institucion_formacion"),
    ],
)
def test_campos_obligatorios(
    conexion_postgresql_pruebas,
    campo,
    columna,
):
    conn = conexion_postgresql_pruebas
    usuario = crear_usuario(conn)

    with pytest.raises(IntegrityError) as captura:
        with conn.begin_nested():
            insertar_medico(conn, usuario, {campo: None})

    assert captura.value.orig.sqlstate == "23502"
    assert captura.value.orig.diag.column_name == columna


def test_cedula_duplicada(conexion_postgresql_pruebas):
    conn = conexion_postgresql_pruebas
    cedula = generar_cedula()

    usuario1 = crear_usuario(conn)
    usuario2 = crear_usuario(conn)

    insertar_medico(conn, usuario1, {"cedula": cedula})

    comprobar_error(
        conn,
        lambda: insertar_medico(
            conn, usuario2, {"cedula": cedula}
        ),
        "23505",
        "medicos_cedula_profesional_key",
    )


def test_perfil_medico_duplicado(
    conexion_postgresql_pruebas,
):
    conn = conexion_postgresql_pruebas
    usuario = crear_usuario(conn)

    insertar_medico(conn, usuario)

    comprobar_error(
        conn,
        lambda: insertar_medico(conn, usuario),
        "23505",
        "medicos_usuario_id_key",
    )


@pytest.mark.parametrize("cedula", ["ABC123", ""])
def test_cedula_invalida(
    conexion_postgresql_pruebas,
    cedula,
):
    conn = conexion_postgresql_pruebas
    usuario = crear_usuario(conn)

    comprobar_error(
        conn,
        lambda: insertar_medico(
            conn, usuario, {"cedula": cedula}
        ),
        "23514",
        "medicos_cedula_formato_check",
    )


VALORES_INVALIDOS = [
    "",
    "A",
    "   ",
    "\t\t",
    "\n\n",
    "\r\r",
    " \t\n ",
    "\u00a0\u00a0",
    "\u2003\u2003",
    "A\t",
    "A\u00a0",
    "\u3000\u3000",
    "\ufeff\ufeff",
]


@pytest.mark.parametrize(
    "campo,restriccion",
    [
        (
            "especialidad",
            "medicos_especialidad_valida_check",
        ),
        (
            "institucion",
            "medicos_institucion_valida_check",
        ),
    ],
)
@pytest.mark.parametrize("valor", VALORES_INVALIDOS)
def test_datos_profesionales_invalidos(
    conexion_postgresql_pruebas,
    campo,
    restriccion,
    valor,
):
    conn = conexion_postgresql_pruebas
    usuario = crear_usuario(conn)

    comprobar_error(
        conn,
        lambda: insertar_medico(
            conn, usuario, {campo: valor}
        ),
        "23514",
        restriccion,
    )


def test_estado_invalido(conexion_postgresql_pruebas):
    conn = conexion_postgresql_pruebas
    usuario = crear_usuario(conn)

    comprobar_error(
        conn,
        lambda: insertar_medico(
            conn, usuario, {"estado": "invalido"}
        ),
        "23514",
        "medicos_estado_verificacion_check",
    )


@pytest.mark.parametrize(
    "cambios",
    [
        {
            "especialidad":
                "\u00a0Medicina general\u2003"
        },
        {
            "institucion":
                "\u00a0Universidad de prueba\u2003"
        },
        {
            "especialidad": "AB",
            "institucion": "CD",
        },
    ],
)
def test_datos_profesionales_validos(
    conexion_postgresql_pruebas,
    cambios,
):
    conn = conexion_postgresql_pruebas
    usuario = crear_usuario(conn)

    resultado = insertar_medico(
        conn, usuario, cambios
    )

    assert resultado["id"] is not None
