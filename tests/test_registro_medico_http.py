from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app

import app.database.registro as modulo_registro
import app.seguridad.middleware as modulo_middleware
import app.seguridad.politicas as modulo_politicas

from app.database.excepciones import (
    RegistroTemporalmenteNoDisponible,
)

from app.seguridad.limitador import LimitadorSolicitudes
from app.seguridad.configuracion import LIMITE_REGISTRO_UID


RUTA = "/usuarios/registro-medico"

CABECERAS = {
    "Authorization": "Bearer token_ficticio"
}

USUARIO_ID = "12345678-1234-4234-8234-123456789012"
MEDICO_ID = "87654321-4321-4321-8321-210987654321"


@pytest.fixture
def entorno_http(monkeypatch):

    limitador = LimitadorSolicitudes()

    monkeypatch.setattr(
        modulo_middleware,
        "limitador",
        limitador,
    )

    monkeypatch.setattr(
        modulo_politicas,
        "limitador",
        limitador,
    )

    identidad = {
        "uid": "firebase_medico_prueba",
        "email": "medico@example.invalid",
        "email_verified": True,
    }

    datos = {
        "nombre": "Medico",
        "apellido": "Prueba",
        "cedula_profesional": "00123456",
        "especialidad": "Medicina general",
        "institucion_formacion": "Universidad de prueba",
    }

    resultado = {
        "usuario_id": USUARIO_ID,
        "medico_id": MEDICO_ID,
        "rol": "medico",
        "estado": True,
        "estado_verificacion": "pendiente",
        "existente": False,
        "firebase_uid": "identificador-interno",
        "correo": "medico@example.invalid",
        "dato_interno": "No debe exponerse",
    }

    firebase = Mock(return_value=identidad)
    registro = Mock(return_value=resultado)

    monkeypatch.setattr(
        modulo_registro,
        "verificar_token_firebase",
        firebase,
    )

    monkeypatch.setattr(
        modulo_registro,
        "crear_usuario_medico",
        registro,
    )

    with TestClient(app) as cliente:

        yield {
            "cliente": cliente,
            "identidad": identidad,
            "datos": datos,
            "resultado": resultado,
            "firebase": firebase,
            "registro": registro,
        }


def enviar(entorno, cabeceras=None):

    if cabeceras is None:
        cabeceras = CABECERAS

    return entorno["cliente"].post(
        RUTA,
        json=entorno["datos"],
        headers=cabeceras,
    )


def test_registro_nuevo_http(entorno_http):

    e = entorno_http
    respuesta = enviar(e)

    assert respuesta.status_code == 201

    cuerpo = respuesta.json()

    assert cuerpo["estado"] == "correcto"
    assert cuerpo["usuario_id"] == USUARIO_ID
    assert cuerpo["medico_id"] == MEDICO_ID
    assert cuerpo["rol"] == "medico"
    assert cuerpo["estado_cuenta"] is True
    assert cuerpo["estado_verificacion"] == "pendiente"
    assert cuerpo["existente"] is False

    e["firebase"].assert_called_once_with(
        "token_ficticio"
    )

    e["registro"].assert_called_once_with(
        firebase_uid="firebase_medico_prueba",
        correo="medico@example.invalid",
        **e["datos"],
    )


def test_registro_existente_http(entorno_http):

    e = entorno_http

    e["resultado"]["existente"] = True
    e["resultado"]["estado_verificacion"] = "verificado"

    respuesta = enviar(e)

    assert respuesta.status_code == 200
    assert respuesta.json()["existente"] is True

    assert (
        respuesta.json()["estado_verificacion"]
        == "verificado"
    )


def test_registro_sin_token(entorno_http):

    e = entorno_http

    respuesta = enviar(e, {})

    assert respuesta.status_code == 401

    assert (
        respuesta.headers["www-authenticate"]
        == "Bearer"
    )

    e["firebase"].assert_not_called()
    e["registro"].assert_not_called()


def test_esquema_autenticacion_incorrecto(entorno_http):

    e = entorno_http

    respuesta = enviar(
        e,
        {"Authorization": "Basic token_ficticio"},
    )

    assert respuesta.status_code == 401

    e["firebase"].assert_not_called()
    e["registro"].assert_not_called()


def test_token_invalido(entorno_http):

    e = entorno_http

    e["firebase"].side_effect = HTTPException(
        status_code=401,
        detail="Token invalido",
    )

    respuesta = enviar(e)

    assert respuesta.status_code == 401

    e["registro"].assert_not_called()


def test_correo_no_verificado(entorno_http):

    e = entorno_http

    e["identidad"]["email_verified"] = False

    respuesta = enviar(e)

    assert respuesta.status_code == 403

    e["registro"].assert_not_called()


def test_identidad_firebase_incompleta(entorno_http):

    e = entorno_http

    del e["identidad"]["uid"]

    respuesta = enviar(e)

    assert respuesta.status_code == 401

    e["registro"].assert_not_called()


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("nombre", ""),
        ("nombre", " "),
        ("nombre", "A"),
        ("nombre", "A" * 101),
        ("nombre", 123),

        ("apellido", ""),
        ("apellido", " "),
        ("apellido", "A"),
        ("apellido", "A" * 101),
        ("apellido", 123),

        ("cedula_profesional", ""),
        ("cedula_profesional", " "),
        ("cedula_profesional", "ABC123"),
        ("cedula_profesional", "123-456"),
        ("cedula_profesional", "1" * 31),
        ("cedula_profesional", 123456),
        ("cedula_profesional", "\u0661\u0662\u0663"),

        ("especialidad", ""),
        ("especialidad", " "),
        ("especialidad", "\u00A0\u2003\uFEFF"),
        ("especialidad", "A"),
        ("especialidad", "A" * 151),
        ("especialidad", 123),

        ("institucion_formacion", ""),
        ("institucion_formacion", " "),
        ("institucion_formacion", "\u00A0\u2003\uFEFF"),
        ("institucion_formacion", "A"),
        ("institucion_formacion", "A" * 201),
        ("institucion_formacion", 123),
    ],
)
def test_datos_invalidos(
    entorno_http,
    campo,
    valor,
):

    e = entorno_http

    e["datos"][campo] = valor

    respuesta = enviar(e)

    assert respuesta.status_code == 422

    e["firebase"].assert_not_called()
    e["registro"].assert_not_called()


@pytest.mark.parametrize(
    "campo",
    [
        "nombre",
        "apellido",
        "cedula_profesional",
        "especialidad",
        "institucion_formacion",
    ],
)
def test_campos_obligatorios(entorno_http, campo):

    e = entorno_http

    del e["datos"][campo]

    respuesta = enviar(e)

    assert respuesta.status_code == 422

    e["registro"].assert_not_called()


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("rol", "administrador"),
        ("rol", "paciente"),
        ("firebase_uid", "uid-ajeno"),
        ("correo", "otro@example.invalid"),
        ("estado", True),
        ("estado_cuenta", True),
        ("estado_verificacion", "verificado"),
        ("usuario_id", USUARIO_ID),
        ("medico_id", MEDICO_ID),
        ("existente", True),
        ("password", "clave-ficticia"),
    ],
)
def test_rechazar_campos_no_autorizados(
    entorno_http,
    campo,
    valor,
):

    e = entorno_http

    e["datos"][campo] = valor

    respuesta = enviar(e)

    assert respuesta.status_code == 422

    e["firebase"].assert_not_called()
    e["registro"].assert_not_called()


def test_normalizacion_http(entorno_http):

    e = entorno_http

    e["datos"]["nombre"] = "  Medico  "
    e["datos"]["apellido"] = "  Prueba  "

    e["datos"]["cedula_profesional"] = " 00123456 "

    e["datos"]["especialidad"] = (
        "\u00A0Medicina general\uFEFF"
    )

    e["datos"]["institucion_formacion"] = (
        "\u2003Universidad de prueba\u00A0"
    )

    respuesta = enviar(e)

    assert respuesta.status_code == 201

    argumentos = e["registro"].call_args.kwargs

    assert argumentos["nombre"] == "Medico"
    assert argumentos["apellido"] == "Prueba"
    assert argumentos["cedula_profesional"] == "00123456"
    assert argumentos["especialidad"] == "Medicina general"

    assert (
        argumentos["institucion_formacion"]
        == "Universidad de prueba"
    )


def test_conflicto_registro_http(entorno_http):

    e = entorno_http

    e["registro"].side_effect = ValueError(
        "La cedula pertenece a otro usuario"
    )

    respuesta = enviar(e)

    assert respuesta.status_code == 409

    assert respuesta.json()["detail"] == (
        "No fue posible completar el registro "
        "con los datos proporcionados"
    )


def test_solicitud_demasiado_grande(entorno_http):

    e = entorno_http

    e["datos"]["nombre"] = "A" * 5000

    respuesta = enviar(e)

    assert respuesta.status_code == 413

    e["firebase"].assert_not_called()
    e["registro"].assert_not_called()


def test_limite_registro_real(entorno_http):

    e = entorno_http

    for _ in range(LIMITE_REGISTRO_UID):

        respuesta = enviar(e)

        assert respuesta.status_code == 201

    respuesta = enviar(e)

    assert respuesta.status_code == 429

    assert int(respuesta.headers["retry-after"]) > 0

    assert (
        e["registro"].call_count
        == LIMITE_REGISTRO_UID
    )


def test_bloqueo_temporal_http(entorno_http):

    e = entorno_http

    e["registro"].side_effect = (
        RegistroTemporalmenteNoDisponible(
            "Detalle interno de bloqueo"
        )
    )

    respuesta = enviar(e)

    assert respuesta.status_code == 503

    assert respuesta.headers["retry-after"] == "5"

    assert "Detalle interno" not in respuesta.text


def test_error_postgresql_http(entorno_http):

    e = entorno_http

    e["registro"].side_effect = RuntimeError(
        "Informacion interna de PostgreSQL"
    )

    respuesta = enviar(e)

    assert respuesta.status_code == 503

    assert "Informacion interna" not in respuesta.text


def test_filtrado_respuesta_http(entorno_http):

    respuesta = enviar(entorno_http)

    assert respuesta.status_code == 201

    campos_permitidos = {
        "estado",
        "mensaje",
        "usuario_id",
        "medico_id",
        "rol",
        "estado_cuenta",
        "estado_verificacion",
        "existente",
    }

    assert set(respuesta.json()) == campos_permitidos


@pytest.mark.parametrize(
    "existente",
    [False, True],
)
def test_cache_control(entorno_http, existente):

    e = entorno_http

    e["resultado"]["existente"] = existente

    respuesta = enviar(e)

    assert respuesta.status_code == (
        200 if existente else 201
    )

    assert respuesta.headers["cache-control"] == "no-store"


def test_json_invalido(entorno_http):

    e = entorno_http

    respuesta = e["cliente"].post(
        RUTA,
        content='{"nombre":',
        headers={
            **CABECERAS,
            "Content-Type": "application/json",
        },
    )

    assert respuesta.status_code == 422

    e["registro"].assert_not_called()
