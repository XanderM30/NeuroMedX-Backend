import pytest
import httpx

from fastapi.testclient import TestClient
from app.seguridad.proxy import servidor


CLAVE_PRUEBA = "a" * 64

CABECERAS = {
    "host": "api.neuromedx.site",
    "cf-connecting-ip": "203.0.113.25",
}


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setattr(
        servidor,
        "CLAVE_INTERNA",
        CLAVE_PRUEBA,
    )

    def bloquear_backend(*args, **kwargs):
        pytest.fail(
            "Una solicitud rechazada intento acceder al backend."
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


@pytest.mark.parametrize("ruta", [
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/salud/base-datos",
    "/pulsera/health",
    "/pulsera/mediciones",
    "/pulsera/mediciones/ultima",
    "/ia/sintomas/health",
    "/ia/sintomas/catalogo",
    "/ia/sintomas/analizar",
    "/usuarios",
    "/administracion",
    "/.env",
])
def test_rutas_privadas(cliente, ruta):
    respuesta = cliente.get(
        ruta,
        headers=CABECERAS,
    )

    assert respuesta.status_code == 404


@pytest.mark.parametrize("metodo,ruta", [
    ("POST", "/salud"),
    ("POST", "/usuarios/me"),
    ("GET", "/usuarios/registro-paciente"),
    ("GET", "/ia/medicamentos/detectar"),
    ("DELETE", "/usuarios/me"),
    ("PUT", "/usuarios/registro-paciente"),
    ("PATCH", "/usuarios/me"),
    ("OPTIONS", "/salud"),
    ("HEAD", "/salud"),
])
def test_metodos_no_autorizados(cliente, metodo, ruta):
    respuesta = cliente.request(
        metodo,
        ruta,
        headers=CABECERAS,
    )

    assert respuesta.status_code == 404


def test_dominio_incorrecto(cliente):
    respuesta = cliente.get(
        "/salud",
        headers={
            **CABECERAS,
            "host": "dominio-invalido.example",
        },
    )

    assert respuesta.status_code == 403


def test_origen_no_local(cliente):
    with TestClient(
        servidor.app,
        client=("10.242.197.59", 12345),
    ) as externo:

        respuesta = externo.get(
            "/salud",
            headers=CABECERAS,
        )

        assert respuesta.status_code == 403


def test_ip_cloudflare_ausente(cliente):
    respuesta = cliente.get(
        "/salud",
        headers={
            "host": "api.neuromedx.site",
        },
    )

    assert respuesta.status_code == 400


def test_ip_cloudflare_invalida(cliente):
    respuesta = cliente.get(
        "/salud",
        headers={
            **CABECERAS,
            "cf-connecting-ip": "ip-invalida",
        },
    )

    assert respuesta.status_code == 400


def test_parametros_no_permitidos(cliente):
    respuesta = cliente.get(
        "/salud?prueba=1",
        headers=CABECERAS,
    )

    assert respuesta.status_code == 400


def test_ruta_codificada(cliente):
    respuesta = cliente.get(
        "/%73alud",
        headers=CABECERAS,
    )

    assert respuesta.status_code == 400


def test_clave_ausente(cliente, monkeypatch):
    monkeypatch.setattr(
        servidor,
        "CLAVE_INTERNA",
        "",
    )

    respuesta = cliente.get(
        "/salud",
        headers=CABECERAS,
    )

    assert respuesta.status_code == 503


def test_barra_final_no_autorizada(cliente):
    respuesta = cliente.get(
        "/salud/",
        headers=CABECERAS,
        follow_redirects=False,
    )

    assert respuesta.status_code == 404
