import pytest

import app.database.usuarios as modulo_usuarios


@pytest.fixture
def datos_validos():
    return {
        "firebase_uid": "uid_medico_prueba",
        "correo": "medico@example.invalid",
        "nombre": "Nombre",
        "apellido": "Apellido",
        "cedula_profesional": "12345678",
        "especialidad": "Medicina general",
        "institucion_formacion": "Universidad de prueba",
    }


@pytest.fixture
def bloquear_base_datos(monkeypatch):

    class EngineBloqueado:

        def begin(self):
            pytest.fail(
                "Una solicitud invalida intento acceder "
                "a PostgreSQL"
            )

        def connect(self):
            pytest.fail(
                "Se intento establecer una conexion "
                "no autorizada"
            )

    monkeypatch.setattr(
        modulo_usuarios,
        "engine",
        EngineBloqueado(),
    )


@pytest.mark.parametrize(
    "campo,valor,mensaje",
    [
        # UID de Firebase
        ("firebase_uid", "", "UID de Firebase invalido"),
        ("firebase_uid", "   ", "UID de Firebase invalido"),
        ("firebase_uid", "a" * 129, "UID de Firebase invalido"),

        # Correo
        ("correo", "", "Correo electronico invalido"),
        ("correo", "correo_invalido", "Correo electronico invalido"),
        ("correo", "a" * 250 + "@test.invalid", "Correo electronico invalido"),

        # Nombre
        ("nombre", "", "Nombre invalido"),
        ("nombre", "A", "Nombre invalido"),
        ("nombre", "   ", "Nombre invalido"),
        ("nombre", "a" * 101, "Nombre invalido"),

        # Apellido
        ("apellido", "", "Apellido invalido"),
        ("apellido", "A", "Apellido invalido"),
        ("apellido", "   ", "Apellido invalido"),
        ("apellido", "a" * 101, "Apellido invalido"),

        # Cedula profesional
        ("cedula_profesional", "", "Cedula profesional invalida"),
        ("cedula_profesional", "   ", "Cedula profesional invalida"),
        ("cedula_profesional", "ABC123", "Cedula profesional invalida"),
        ("cedula_profesional", "12 345", "Cedula profesional invalida"),
        ("cedula_profesional", "-12345", "Cedula profesional invalida"),
        ("cedula_profesional", "123.45", "Cedula profesional invalida"),
        ("cedula_profesional", "1" * 31, "Cedula profesional invalida"),
        ("cedula_profesional", "\u0661\u0662", "Cedula profesional invalida"),

        # Especialidad
        ("especialidad", "", "Especialidad invalida"),
        ("especialidad", "A", "Especialidad invalida"),
        ("especialidad", "   ", "Especialidad invalida"),
        ("especialidad", "\t\n", "Especialidad invalida"),
        ("especialidad", "\u00a0\u2003", "Especialidad invalida"),
        ("especialidad", "\ufeff\u00a0\ufeff", "Especialidad invalida"),
        ("especialidad", "\ufeff A \u2003", "Especialidad invalida"),
        ("especialidad", "a" * 151, "Especialidad invalida"),

        # Institucion
        ("institucion_formacion", "", "Institucion de formacion invalida"),
        ("institucion_formacion", "A", "Institucion de formacion invalida"),
        ("institucion_formacion", "   ", "Institucion de formacion invalida"),
        ("institucion_formacion", "\t\n", "Institucion de formacion invalida"),
        ("institucion_formacion", "\u00a0\u2003", "Institucion de formacion invalida"),
        ("institucion_formacion", "\ufeff\u00a0\ufeff", "Institucion de formacion invalida"),
        ("institucion_formacion", "\ufeff A \u2003", "Institucion de formacion invalida"),
        ("institucion_formacion", "a" * 201, "Institucion de formacion invalida"),
    ],
)
def test_registro_medico_datos_invalidos(
    datos_validos,
    bloquear_base_datos,
    campo,
    valor,
    mensaje,
):
    datos_validos[campo] = valor

    with pytest.raises(ValueError, match=mensaje):
        modulo_usuarios.crear_usuario_medico(
            **datos_validos
        )
