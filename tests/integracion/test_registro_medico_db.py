from contextlib import contextmanager
from uuid import uuid4

import pytest
from sqlalchemy import text

import app.database.usuarios as modulo_usuarios


pytestmark = [
    pytest.mark.integracion,
    pytest.mark.postgresql,
]


@pytest.fixture
def datos_medico():
    identificador = uuid4().hex

    return {
        "firebase_uid": f"prueba_{identificador}",
        "correo": f"prueba_{identificador}@example.invalid",
        "nombre": "Nombre",
        "apellido": "Apellido",
        "cedula_profesional": str(uuid4().int)[:30],
        "especialidad": "Medicina general",
        "institucion_formacion": "Universidad de prueba",
    }


@pytest.fixture
def registro_aislado(
    conexion_postgresql_pruebas,
    monkeypatch,
):
    conn = conexion_postgresql_pruebas

    class EnginePruebas:

        @contextmanager
        def begin(self):
            with conn.begin_nested():
                yield conn

    monkeypatch.setattr(
        modulo_usuarios,
        "engine",
        EnginePruebas(),
    )

    return conn


def contar_usuarios(conn, firebase_uid):
    return conn.execute(
        text("""
            SELECT COUNT(*)
            FROM public.usuarios
            WHERE firebase_uid = :uid
        """),
        {"uid": firebase_uid},
    ).scalar_one()


def contar_medicos(conn, cedula):
    return conn.execute(
        text("""
            SELECT COUNT(*)
            FROM public.medicos
            WHERE cedula_profesional = :cedula
        """),
        {"cedula": cedula},
    ).scalar_one()


def test_registro_medico_nuevo(
    registro_aislado,
    datos_medico,
):
    resultado = modulo_usuarios.crear_usuario_medico(
        **datos_medico
    )

    assert resultado["usuario_id"]
    assert resultado["medico_id"]
    assert resultado["rol"] == "medico"
    assert resultado["estado"] is True
    assert resultado["existente"] is False
    assert resultado["estado_verificacion"] == "pendiente"

    assert contar_usuarios(
        registro_aislado,
        datos_medico["firebase_uid"],
    ) == 1

    assert contar_medicos(
        registro_aislado,
        datos_medico["cedula_profesional"],
    ) == 1


def test_registro_idempotente(
    registro_aislado,
    datos_medico,
):
    primero = modulo_usuarios.crear_usuario_medico(
        **datos_medico
    )

    segundo = modulo_usuarios.crear_usuario_medico(
        **datos_medico
    )

    assert primero["existente"] is False
    assert segundo["existente"] is True

    assert primero["usuario_id"] == segundo["usuario_id"]
    assert primero["medico_id"] == segundo["medico_id"]

    assert contar_usuarios(
        registro_aislado,
        datos_medico["firebase_uid"],
    ) == 1

    assert contar_medicos(
        registro_aislado,
        datos_medico["cedula_profesional"],
    ) == 1


def test_normalizacion_datos(
    registro_aislado,
    datos_medico,
):
    datos_medico["correo"] = (
        " " + datos_medico["correo"].upper() + " "
    )

    datos_medico["nombre"] = "  Nombre  "
    datos_medico["apellido"] = "  Apellido  "

    datos_medico["especialidad"] = (
        "\ufeff\u00a0Medicina general\u2003"
    )

    datos_medico["institucion_formacion"] = (
        "\tUniversidad de prueba\ufeff"
    )

    resultado = modulo_usuarios.crear_usuario_medico(
        **datos_medico
    )

    assert resultado["correo"] == (
        datos_medico["correo"].strip().lower()
    )

    assert resultado["especialidad"] == "Medicina general"

    assert (
        resultado["institucion_formacion"]
        == "Universidad de prueba"
    )

    usuario = registro_aislado.execute(
        text("""
            SELECT nombre, apellido
            FROM public.usuarios
            WHERE firebase_uid = :uid
        """),
        {"uid": datos_medico["firebase_uid"]},
    ).mappings().one()

    assert usuario["nombre"] == "Nombre"
    assert usuario["apellido"] == "Apellido"


def test_rechazar_cedula_duplicada(
    registro_aislado,
    datos_medico,
):
    modulo_usuarios.crear_usuario_medico(
        **datos_medico
    )

    identificador = uuid4().hex

    segundo = {
        **datos_medico,
        "firebase_uid": f"prueba_{identificador}",
        "correo": f"prueba_{identificador}@example.invalid",
    }

    with pytest.raises(ValueError, match="cedula profesional"):
        modulo_usuarios.crear_usuario_medico(**segundo)

    assert contar_usuarios(
        registro_aislado,
        segundo["firebase_uid"],
    ) == 0

    assert contar_medicos(
        registro_aislado,
        datos_medico["cedula_profesional"],
    ) == 1


def test_rechazar_correo_duplicado(
    registro_aislado,
    datos_medico,
):
    modulo_usuarios.crear_usuario_medico(
        **datos_medico
    )

    segundo = {
        **datos_medico,
        "firebase_uid": f"prueba_{uuid4().hex}",
        "cedula_profesional": str(uuid4().int)[:30],
    }

    with pytest.raises(ValueError, match="correo"):
        modulo_usuarios.crear_usuario_medico(**segundo)

    assert contar_usuarios(
        registro_aislado,
        segundo["firebase_uid"],
    ) == 0


def test_rechazar_cambio_datos_profesionales(
    registro_aislado,
    datos_medico,
):
    primero = modulo_usuarios.crear_usuario_medico(
        **datos_medico
    )

    modificados = {
        **datos_medico,
        "especialidad": "Cardiologia",
    }

    with pytest.raises(
        ValueError,
        match="datos profesionales",
    ):
        modulo_usuarios.crear_usuario_medico(
            **modificados
        )

    original = modulo_usuarios.crear_usuario_medico(
        **datos_medico
    )

    assert original["medico_id"] == primero["medico_id"]
    assert original["especialidad"] == "Medicina general"


def test_rechazar_usuario_paciente(
    registro_aislado,
    datos_medico,
):
    registro_aislado.execute(
        text("""
            INSERT INTO public.usuarios (
                firebase_uid,
                correo,
                nombre,
                apellido,
                rol
            )
            VALUES (
                :firebase_uid,
                :correo,
                :nombre,
                :apellido,
                'paciente'
            )
        """),
        datos_medico,
    )

    with pytest.raises(
        ValueError,
        match="no corresponde a un medico",
    ):
        modulo_usuarios.crear_usuario_medico(
            **datos_medico
        )

    rol = registro_aislado.execute(
        text("""
            SELECT rol
            FROM public.usuarios
            WHERE firebase_uid = :uid
        """),
        {"uid": datos_medico["firebase_uid"]},
    ).scalar_one()

    assert rol == "paciente"


def test_rechazar_cuenta_desactivada(
    registro_aislado,
    datos_medico,
):
    registro_aislado.execute(
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
                FALSE
            )
        """),
        datos_medico,
    )

    with pytest.raises(ValueError, match="desactivada"):
        modulo_usuarios.crear_usuario_medico(
            **datos_medico
        )


def test_rechazar_perfil_incompleto(
    registro_aislado,
    datos_medico,
):
    registro_aislado.execute(
        text("""
            INSERT INTO public.usuarios (
                firebase_uid,
                correo,
                nombre,
                apellido,
                rol
            )
            VALUES (
                :firebase_uid,
                :correo,
                :nombre,
                :apellido,
                'medico'
            )
        """),
        datos_medico,
    )

    with pytest.raises(
        ValueError,
        match="perfil incompleto",
    ):
        modulo_usuarios.crear_usuario_medico(
            **datos_medico
        )

    assert contar_medicos(
        registro_aislado,
        datos_medico["cedula_profesional"],
    ) == 0


def test_rechazar_correo_diferente_mismo_uid(
    registro_aislado,
    datos_medico,
):
    modulo_usuarios.crear_usuario_medico(
        **datos_medico
    )

    modificados = {
        **datos_medico,
        "correo": "diferente@example.invalid",
    }

    with pytest.raises(
        ValueError,
        match="correo no coincide",
    ):
        modulo_usuarios.crear_usuario_medico(
            **modificados
        )


def test_rollback_si_falla_perfil(
    registro_aislado,
    datos_medico,
    monkeypatch,
):
    def provocar_error(**kwargs):

        conn = kwargs["connection"]

        assert contar_usuarios(
            conn,
            datos_medico["firebase_uid"],
        ) == 1

        raise RuntimeError(
            "Fallo simulado al crear perfil medico"
        )

    monkeypatch.setattr(
        modulo_usuarios,
        "crear_perfil_medico",
        provocar_error,
    )

    with pytest.raises(
        RuntimeError,
        match="Fallo simulado",
    ):
        modulo_usuarios.crear_usuario_medico(
            **datos_medico
        )

    assert contar_usuarios(
        registro_aislado,
        datos_medico["firebase_uid"],
    ) == 0

    assert contar_medicos(
        registro_aislado,
        datos_medico["cedula_profesional"],
    ) == 0
