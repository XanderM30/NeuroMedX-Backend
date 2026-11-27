import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import dependencies
from app.database import registro


@pytest.mark.parametrize(
    "datos_firebase",
    [
        {"uid": "uid-no-verificado", "email_verified": False},
        {"uid": "uid-sin-verificacion"},
    ],
)
def test_usuario_no_verificado_recibe_403(
    monkeypatch,
    datos_firebase
):
    monkeypatch.setattr(
        dependencies,
        "verificar_token_firebase",
        lambda token: datos_firebase
    )

    cliente = TestClient(app)

    respuesta = cliente.get(
        "/usuarios/me",
        headers={"Authorization": "Bearer token-prueba"}
    )

    assert respuesta.status_code == 403
    assert "verificar tu correo" in respuesta.json()["detail"].lower()


def test_registro_no_verificado_recibe_403(
    monkeypatch
):
    llamadas = []

    monkeypatch.setattr(
        registro,
        "verificar_token_firebase",
        lambda token: {
            "uid": "uid-no-verificado",
            "email": "prueba@neuromedx.test",
            "email_verified": False,
        }
    )

    monkeypatch.setattr(
        registro,
        "crear_usuario_paciente",
        lambda **kwargs: llamadas.append(kwargs)
    )

    cliente = TestClient(app)

    respuesta = cliente.post(
        "/usuarios/registro-paciente",
        headers={"Authorization": "Bearer token-prueba"},
        json={
            "nombre": "Usuario",
            "apellido": "Prueba",
        }
    )

    assert respuesta.status_code == 403
    assert len(llamadas) == 0


def test_registro_sin_campo_email_verified_recibe_403(
    monkeypatch
):
    llamadas = []

    monkeypatch.setattr(
        registro,
        "verificar_token_firebase",
        lambda token: {
            "uid": "uid-sin-verificacion",
            "email": "prueba@neuromedx.test",
        }
    )

    monkeypatch.setattr(
        registro,
        "crear_usuario_paciente",
        lambda **kwargs: llamadas.append(kwargs)
    )

    cliente = TestClient(app)

    respuesta = cliente.post(
        "/usuarios/registro-paciente",
        headers={"Authorization": "Bearer token-prueba"},
        json={
            "nombre": "Usuario",
            "apellido": "Prueba",
        }
    )

    assert respuesta.status_code == 403
    assert len(llamadas) == 0
