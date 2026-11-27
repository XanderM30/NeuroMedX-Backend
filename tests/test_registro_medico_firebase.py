from unittest.mock import Mock

import pytest
from fastapi import HTTPException

import app.database.registro as modulo_registro

from app.database.excepciones import (
    RegistroTemporalmenteNoDisponible,
)


@pytest.fixture
def entorno_registro(monkeypatch):

    identidad = {
        "uid": "firebase_medico_prueba",
        "email": "medico@example.invalid",
        "email_verified": True,
    }

    datos = {
        "token": "token_ficticio",
        "nombre": "Medico",
        "apellido": "Prueba",
        "cedula_profesional": "12345678",
        "especialidad": "Medicina general",
        "institucion_formacion": "Universidad de prueba",
    }

    resultado = {
        "usuario_id": "usuario-prueba",
        "medico_id": "medico-prueba",
        "rol": "medico",
        "estado": True,
        "estado_verificacion": "pendiente",
        "existente": False,
    }

    firebase = Mock(return_value=identidad)
    limitador = Mock()
    registro = Mock(return_value=resultado)

    monkeypatch.setattr(
        modulo_registro,
        "verificar_token_firebase",
        firebase,
    )

    monkeypatch.setattr(
        modulo_registro,
        "limitar_registro",
        limitador,
    )

    monkeypatch.setattr(
        modulo_registro,
        "crear_usuario_medico",
        registro,
    )

    return {
        "identidad": identidad,
        "datos": datos,
        "resultado": resultado,
        "firebase": firebase,
        "limitador": limitador,
        "registro": registro,
    }


def ejecutar(entorno):

    return modulo_registro.registrar_medico_firebase(
        **entorno["datos"]
    )


def test_registro_medico_nuevo(entorno_registro):

    e = entorno_registro

    respuesta = ejecutar(e)

    assert respuesta["estado"] == "correcto"
    assert respuesta["estado_cuenta"] is True
    assert respuesta["existente"] is False
    assert respuesta["rol"] == "medico"
    assert respuesta["estado_verificacion"] == "pendiente"

    e["firebase"].assert_called_once_with(
        "token_ficticio"
    )

    e["limitador"].assert_called_once_with(
        "firebase_medico_prueba"
    )

    e["registro"].assert_called_once_with(
        firebase_uid="firebase_medico_prueba",
        correo="medico@example.invalid",
        nombre="Medico",
        apellido="Prueba",
        cedula_profesional="12345678",
        especialidad="Medicina general",
        institucion_formacion="Universidad de prueba",
    )


def test_medico_registrado_previamente(entorno_registro):

    e = entorno_registro

    e["resultado"]["existente"] = True
    e["resultado"]["estado_verificacion"] = "verificado"

    respuesta = ejecutar(e)

    assert respuesta["existente"] is True
    assert respuesta["estado_verificacion"] == "verificado"
    assert "ya estaba registrado" in respuesta["mensaje"]


@pytest.mark.parametrize(
    "detalle",
    [
        "Token invalido",
        "Token expirado",
        "Token revocado",
    ],
)
def test_rechazar_token(entorno_registro, detalle):

    e = entorno_registro

    e["firebase"].side_effect = HTTPException(
        status_code=401,
        detail=detalle,
    )

    with pytest.raises(HTTPException) as error:
        ejecutar(e)

    assert error.value.status_code == 401
    assert error.value.detail == detalle

    e["limitador"].assert_not_called()
    e["registro"].assert_not_called()


@pytest.mark.parametrize(
    "verificado",
    [False, None, "true", 1],
)
def test_correo_no_verificado(
    entorno_registro,
    verificado,
):

    e = entorno_registro

    e["identidad"]["email_verified"] = verificado

    with pytest.raises(HTTPException) as error:
        ejecutar(e)

    assert error.value.status_code == 403

    e["limitador"].assert_not_called()
    e["registro"].assert_not_called()


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("uid", None),
        ("uid", ""),
        ("uid", "   "),
        ("uid", 123),
        ("uid", "a" * 129),
        ("email", None),
        ("email", ""),
        ("email", "   "),
        ("email", 123),
        ("email", "correo-sin-arroba"),
        ("email", "a" * 256 + "@example.invalid"),
    ],
)
def test_identidad_invalida(
    entorno_registro,
    campo,
    valor,
):

    e = entorno_registro

    e["identidad"][campo] = valor

    with pytest.raises(HTTPException) as error:
        ejecutar(e)

    assert error.value.status_code == 401

    e["limitador"].assert_not_called()
    e["registro"].assert_not_called()


@pytest.mark.parametrize(
    "campo",
    ["uid", "email"],
)
def test_identidad_incompleta(entorno_registro, campo):

    e = entorno_registro

    del e["identidad"][campo]

    with pytest.raises(HTTPException) as error:
        ejecutar(e)

    assert error.value.status_code == 401

    e["limitador"].assert_not_called()
    e["registro"].assert_not_called()


def test_normalizacion_identidad(entorno_registro):

    e = entorno_registro

    e["identidad"]["email"] = "  MEDICO@EXAMPLE.INVALID  "

    ejecutar(e)

    argumentos = e["registro"].call_args.kwargs

    assert argumentos["correo"] == "medico@example.invalid"
    assert argumentos["firebase_uid"] == "firebase_medico_prueba"


def test_limite_registro(entorno_registro):

    e = entorno_registro

    e["limitador"].side_effect = HTTPException(
        status_code=429,
        detail="Limite de solicitudes alcanzado",
        headers={"Retry-After": "60"},
    )

    with pytest.raises(HTTPException) as error:
        ejecutar(e)

    assert error.value.status_code == 429
    assert error.value.headers["Retry-After"] == "60"

    e["registro"].assert_not_called()


@pytest.mark.parametrize(
    "detalle_interno",
    [
        "El correo pertenece a otro usuario",
        "La cedula profesional ya existe",
        "La cuenta pertenece a un paciente",
        "La cuenta esta desactivada",
        "Los datos profesionales no coinciden",
    ],
)
def test_conflicto_registro(
    entorno_registro,
    detalle_interno,
):

    e = entorno_registro

    e["registro"].side_effect = ValueError(
        detalle_interno
    )

    with pytest.raises(HTTPException) as error:
        ejecutar(e)

    assert error.value.status_code == 409

    assert error.value.detail == (
        "No fue posible completar el registro "
        "con los datos proporcionados"
    )

    assert detalle_interno not in error.value.detail


def test_bloqueo_temporal(entorno_registro):

    e = entorno_registro

    e["registro"].side_effect = (
        RegistroTemporalmenteNoDisponible(
            "Bloqueo interno de PostgreSQL"
        )
    )

    with pytest.raises(HTTPException) as error:
        ejecutar(e)

    assert error.value.status_code == 503
    assert error.value.headers["Retry-After"] == "5"

    assert "Bloqueo interno" not in error.value.detail


def test_error_inesperado_base_datos(entorno_registro):

    e = entorno_registro

    e["registro"].side_effect = RuntimeError(
        "Informacion interna de PostgreSQL"
    )

    with pytest.raises(HTTPException) as error:
        ejecutar(e)

    assert error.value.status_code == 503

    assert error.value.detail == (
        "No fue posible registrar el medico en PostgreSQL"
    )

    assert "Informacion interna" not in error.value.detail
