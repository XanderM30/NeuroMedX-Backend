import pytest
import httpx

from fastapi.testclient import TestClient
from app.seguridad.proxy import servidor

CABECERAS = {
    "host": "api.neuromedx.site",
    "cf-connecting-ip": "203.0.113.25",
    "content-type": "application/json",
}

@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setattr(
        servidor,
        "CLAVE_INTERNA",
        "a" * 64,
    )

    def bloquear_backend(*args, **kwargs):
        pytest.fail(
            "Una solicitud invalida alcanzo el backend."
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        bloquear_backend,
    )

    with TestClient(
        servidor.app,
        client=("127.0.0.1", 12345),
    ) as cliente:
        yield cliente

@pytest.mark.parametrize("ruta,limite", [
    ("/usuarios/registro-paciente", 4 * 1024),
    ("/ia/medicamentos/detectar", 128 * 1024),
])
def test_cuerpo_demasiado_grande(cliente, ruta, limite):
    respuesta = cliente.post(
        ruta,
        headers=CABECERAS,
        content=b"x" * (limite + 1),
    )

    assert respuesta.status_code == 413

@pytest.mark.parametrize("ruta", [
    "/salud",
    "/usuarios/me",
])
def test_get_con_cuerpo(cliente, ruta):
    respuesta = cliente.request(
        "GET",
        ruta,
        headers=CABECERAS,
        content=b"contenido",
    )

    assert respuesta.status_code == 413

@pytest.mark.parametrize("tipo", [
    "text/plain",
    "text/html",
    "application/xml",
    "application/octet-stream",
    "multipart/form-data",
])
def test_tipo_contenido_invalido(cliente, tipo):
    respuesta = cliente.post(
        "/usuarios/registro-paciente",
        headers={
            **CABECERAS,
            "content-type": tipo,
        },
        content=b"contenido",
    )

    assert respuesta.status_code == 415

def test_tipo_contenido_ausente(cliente):
    respuesta = cliente.post(
        "/usuarios/registro-paciente",
        headers={
            "host": "api.neuromedx.site",
            "cf-connecting-ip": "203.0.113.25",
        },
        content=b"{}",
    )

    assert respuesta.status_code == 415

@pytest.mark.parametrize("codificacion", [
    "gzip",
    "br",
    "deflate",
])
def test_codificacion_no_permitida(cliente, codificacion):
    respuesta = cliente.post(
        "/usuarios/registro-paciente",
        headers={
            **CABECERAS,
            "content-encoding": codificacion,
        },
        content=b"{}",
    )

    assert respuesta.status_code == 415

@pytest.mark.parametrize("longitud", [
    "-1",
    "abc",
    "1.5",
    "2, 3",
    "9999999999999",
])
def test_longitud_invalida(cliente, longitud):
    respuesta = cliente.post(
        "/usuarios/registro-paciente",
        headers={
            **CABECERAS,
            "content-length": longitud,
        },
        content=b"{}",
    )

    assert respuesta.status_code == 400

def test_longitud_duplicada(cliente):
    cabeceras = list(CABECERAS.items()) + [
        ("content-length", "2"),
        ("content-length", "3"),
    ]

    respuesta = cliente.post(
        "/usuarios/registro-paciente",
        headers=cabeceras,
        content=b"{}",
    )

    assert respuesta.status_code == 400

def test_longitud_incorrecta(cliente):
    respuesta = cliente.post(
        "/usuarios/registro-paciente",
        headers={
            **CABECERAS,
            "content-length": "1",
        },
        content=b"{}",
    )

    assert respuesta.status_code == 400

def test_longitud_y_transferencia_incompatibles(cliente):
    respuesta = cliente.post(
        "/usuarios/registro-paciente",
        headers={
            **CABECERAS,
            "content-length": "2",
            "transfer-encoding": "chunked",
        },
        content=b"{}",
    )

    assert respuesta.status_code == 400

def test_cuerpo_excede_limite_real(cliente):
    respuesta = cliente.post(
        "/usuarios/registro-paciente",
        headers={
            **CABECERAS,
            "content-length": "2",
        },
        content=b"x" * 4097,
    )

    assert respuesta.status_code == 413
