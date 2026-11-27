from datetime import datetime
from unittest.mock import Mock, MagicMock
from uuid import UUID

import pytest

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app

import app.auth.dependencies as modulo_auth
import app.auth.medicos as modulo_medicos
import app.seguridad.middleware as modulo_middleware
import app.seguridad.politicas as modulo_politicas

from app.seguridad.limitador import LimitadorSolicitudes
from app.seguridad.configuracion import LIMITE_PERFIL_UID


RUTA = "/medicos/me"

CABECERAS = {
    "Authorization": "Bearer token_ficticio",
}

USUARIO_ID = UUID(
    "12345678-1234-4234-8234-123456789012"
)

MEDICO_ID = UUID(
    "87654321-4321-4321-8321-210987654321"
)


@pytest.fixture
def entorno_perfil(monkeypatch):

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

    usuario = {
        "id": USUARIO_ID,
        "firebase_uid": "firebase_medico_prueba",
        "correo": "medico@example.invalid",
        "nombre": "Medico",
        "apellido": "Prueba",
        "rol": "medico",
        "estado": True,
    }

    medico = {
        "id": MEDICO_ID,
        "usuario_id": USUARIO_ID,
        "cedula_profesional": "00123456",
        "especialidad": "Medicina general",
        "institucion_formacion": "Universidad de prueba",
        "estado_verificacion": "pendiente",
        "fecha_registro": datetime(2026, 11, 27, 12, 0),
    }

    firebase = Mock(return_value=identidad)

    engine = MagicMock()

    conexion = (
        engine.connect.return_value
        .__enter__.return_value
    )

    consulta = (
        conexion.execute.return_value
        .mappings.return_value
        .one_or_none
    )

    consulta.return_value = usuario

    consulta_medico = Mock(return_value=medico)

    monkeypatch.setattr(
        modulo_auth,
        "verificar_token_firebase",
        firebase,
    )

    monkeypatch.setattr(
        modulo_auth,
        "engine",
        engine,
    )

    monkeypatch.setattr(
        modulo_medicos,
        "obtener_medico_por_usuario_id",
        consulta_medico,
    )

    with TestClient(app) as cliente:

        yield {
            "cliente": cliente,
            "identidad": identidad,
            "usuario": usuario,
            "medico": medico,
            "firebase": firebase,
            "engine": engine,
            "conexion": conexion,
            "consulta": consulta,
            "consulta_medico": consulta_medico,
        }


def consultar(entorno, cabeceras=None):

    if cabeceras is None:
        cabeceras = CABECERAS

    return entorno["cliente"].get(
        RUTA,
        headers=cabeceras,
    )


@pytest.mark.parametrize(
    "estado",
    ["pendiente", "verificado", "rechazado"],
)
def test_perfil_medico_por_estado(
    entorno_perfil,
    estado,
):

    e = entorno_perfil
    e["medico"]["estado_verificacion"] = estado

    respuesta = consultar(e)

    assert respuesta.status_code == 200

    cuerpo = respuesta.json()

    assert cuerpo["usuario"]["id"] == str(USUARIO_ID)
    assert cuerpo["usuario"]["rol"] == "medico"
    assert cuerpo["usuario"]["estado_cuenta"] is True

    assert cuerpo["medico"]["id"] == str(MEDICO_ID)

    assert (
        cuerpo["medico"]["estado_verificacion"]
        == estado
    )

    e["consulta_medico"].assert_called_once_with(
        USUARIO_ID
    )


def test_perfil_sin_token(entorno_perfil):

    e = entorno_perfil

    respuesta = consultar(e, {})

    assert respuesta.status_code == 401

    e["firebase"].assert_not_called()
    e["engine"].connect.assert_not_called()
    e["consulta_medico"].assert_not_called()


def test_autenticacion_incorrecta(entorno_perfil):

    e = entorno_perfil

    respuesta = consultar(
        e,
        {"Authorization": "Basic token_ficticio"},
    )

    assert respuesta.status_code == 401

    e["firebase"].assert_not_called()


@pytest.mark.parametrize(
    "detalle",
    [
        "Token invalido",
        "Token expirado",
        "Token revocado",
    ],
)
def test_token_rechazado(entorno_perfil, detalle):

    e = entorno_perfil

    e["firebase"].side_effect = HTTPException(
        status_code=401,
        detail=detalle,
    )

    respuesta = consultar(e)

    assert respuesta.status_code == 401

    e["engine"].connect.assert_not_called()
    e["consulta_medico"].assert_not_called()


def test_correo_no_verificado(entorno_perfil):

    e = entorno_perfil

    e["identidad"]["email_verified"] = False

    respuesta = consultar(e)

    assert respuesta.status_code == 403

    e["engine"].connect.assert_not_called()
    e["consulta_medico"].assert_not_called()


def test_identidad_sin_uid(entorno_perfil):

    e = entorno_perfil

    del e["identidad"]["uid"]

    respuesta = consultar(e)

    assert respuesta.status_code == 401

    e["engine"].connect.assert_not_called()


def test_usuario_no_registrado(entorno_perfil):

    e = entorno_perfil

    e["consulta"].return_value = None

    respuesta = consultar(e)

    assert respuesta.status_code == 403

    e["consulta_medico"].assert_not_called()


def test_usuario_desactivado(entorno_perfil):

    e = entorno_perfil

    e["usuario"]["estado"] = False

    respuesta = consultar(e)

    assert respuesta.status_code == 403

    e["consulta_medico"].assert_not_called()


def test_paciente_no_autorizado(entorno_perfil):

    e = entorno_perfil

    e["usuario"]["rol"] = "paciente"

    respuesta = consultar(e)

    assert respuesta.status_code == 403

    e["consulta_medico"].assert_not_called()


def test_perfil_medico_inexistente(entorno_perfil):

    e = entorno_perfil

    e["consulta_medico"].return_value = None

    respuesta = consultar(e)

    assert respuesta.status_code == 403


def test_error_consulta_usuario(entorno_perfil):

    e = entorno_perfil

    e["engine"].connect.side_effect = RuntimeError(
        "Informacion interna PostgreSQL"
    )

    respuesta = consultar(e)

    assert respuesta.status_code == 503

    assert "Informacion interna" not in respuesta.text

    e["consulta_medico"].assert_not_called()


def test_error_consulta_medico(entorno_perfil):

    e = entorno_perfil

    e["consulta_medico"].side_effect = RuntimeError(
        "Informacion interna PostgreSQL"
    )

    respuesta = consultar(e)

    assert respuesta.status_code == 503

    assert "Informacion interna" not in respuesta.text


def test_filtrado_informacion(entorno_perfil):

    respuesta = consultar(entorno_perfil)

    assert respuesta.status_code == 200

    cuerpo = respuesta.json()

    assert set(cuerpo) == {
        "usuario",
        "medico",
    }

    assert set(cuerpo["usuario"]) == {
        "id",
        "nombre",
        "apellido",
        "correo",
        "rol",
        "estado_cuenta",
    }

    assert set(cuerpo["medico"]) == {
        "id",
        "cedula_profesional",
        "especialidad",
        "institucion_formacion",
        "estado_verificacion",
        "fecha_registro",
    }

    assert "firebase_uid" not in respuesta.text


def test_cache_control(entorno_perfil):

    respuesta = consultar(entorno_perfil)

    assert respuesta.status_code == 200

    assert respuesta.headers["cache-control"] == "no-store"


def test_consulta_identidad_propia(entorno_perfil):

    e = entorno_perfil

    respuesta = e["cliente"].get(
        RUTA,
        params={
            "usuario_id": "usuario-ajeno",
            "medico_id": "medico-ajeno",
        },
        headers=CABECERAS,
    )

    assert respuesta.status_code == 200

    e["consulta_medico"].assert_called_once_with(
        USUARIO_ID
    )

    argumentos = e["conexion"].execute.call_args.args

    assert argumentos[1] == {
        "firebase_uid": "firebase_medico_prueba"
    }


def test_limite_consultas_perfil(entorno_perfil):

    e = entorno_perfil

    for _ in range(LIMITE_PERFIL_UID):

        respuesta = consultar(e)

        assert respuesta.status_code == 200

    respuesta = consultar(e)

    assert respuesta.status_code == 429

    assert int(respuesta.headers["retry-after"]) > 0

    assert (
        e["consulta_medico"].call_count
        == LIMITE_PERFIL_UID
    )


@pytest.mark.parametrize(
    "estado_verificacion,estado_cuenta,permitido",
    [
        ("pendiente", True, False),
        ("verificado", True, True),
        ("rechazado", True, False),
        ("desconocido", True, False),
        ("verificado", False, False),
    ],
)
def test_autorizacion_profesional(
    estado_verificacion,
    estado_cuenta,
    permitido,
):

    perfil = {
        "usuario": {
            "rol": "medico",
            "estado": estado_cuenta,
        },
        "medico": {
            "estado_verificacion": estado_verificacion,
        },
    }

    if permitido:

        resultado = (
            modulo_medicos.obtener_medico_verificado(
                perfil
            )
        )

        assert resultado is perfil

    else:

        with pytest.raises(HTTPException) as error:

            modulo_medicos.obtener_medico_verificado(
                perfil
            )

        assert error.value.status_code == 403
