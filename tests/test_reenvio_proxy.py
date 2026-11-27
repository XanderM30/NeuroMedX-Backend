import pytest
import httpx

from fastapi.testclient import TestClient
from app.seguridad.proxy import servidor


CLAVE_PRUEBA = "a" * 64

CABECERAS = {
    "host": "api.neuromedx.site",
    "cf-connecting-ip": "203.0.113.25",
    "authorization": "Bearer token-ficticio",
    "content-type": "application/json",
}


@pytest.fixture
def entorno(monkeypatch):
    solicitudes = []
    configuracion = {
        "status": 200,
        "contenido": b'{"estado":"correcto"}',
        "headers": {
            "content-type": "application/json",
        },
    }

    monkeypatch.setattr(
        servidor,
        "CLAVE_INTERNA",
        CLAVE_PRUEBA,
    )

    cliente_original = httpx.AsyncClient

    async def backend_simulado(request):
        solicitudes.append(request)

        return httpx.Response(
            status_code=configuracion["status"],
            stream=httpx.ByteStream(configuracion["contenido"]),
            headers=configuracion["headers"],
        )

    def crear_cliente(*args, **kwargs):
        assert kwargs["trust_env"] is False
        assert kwargs["follow_redirects"] is False

        kwargs["transport"] = httpx.MockTransport(
            backend_simulado
        )

        return cliente_original(*args, **kwargs)

    monkeypatch.setattr(
        servidor.httpx,
        "AsyncClient",
        crear_cliente,
    )

    with TestClient(
        servidor.app,
        client=("127.0.0.1", 12345),
    ) as cliente:
        yield cliente, solicitudes, configuracion


@pytest.mark.parametrize("metodo,ruta", [
    ("GET", "/salud"),
    ("GET", "/usuarios/me"),
    ("POST", "/usuarios/registro-paciente"),
    ("POST", "/ia/medicamentos/detectar"),
])
def test_reenviar_rutas_autorizadas(entorno, metodo, ruta):
    cliente, solicitudes, _ = entorno

    cuerpo = b"{}" if metodo == "POST" else b""

    respuesta = cliente.request(
        metodo,
        ruta,
        headers=CABECERAS,
        content=cuerpo,
    )

    assert respuesta.status_code == 200
    assert len(solicitudes) == 1

    solicitud = solicitudes[0]

    assert solicitud.method == metodo
    assert str(solicitud.url) == (
        servidor.URL_BACKEND + ruta
    )
    assert solicitud.content == cuerpo


def test_conservar_autorizacion(entorno):
    cliente, solicitudes, _ = entorno

    respuesta = cliente.get(
        "/usuarios/me",
        headers=CABECERAS,
    )

    assert respuesta.status_code == 200
    assert solicitudes[0].headers["authorization"] == (
        "Bearer token-ficticio"
    )


def test_agregar_identidad_interna(entorno):
    cliente, solicitudes, _ = entorno

    respuesta = cliente.get(
        "/salud",
        headers=CABECERAS,
    )

    assert respuesta.status_code == 200

    cabeceras = solicitudes[0].headers

    assert cabeceras["x-neuromedx-client-ip"] == (
        "203.0.113.25"
    )

    assert cabeceras["x-neuromedx-proxy-key"] == (
        CLAVE_PRUEBA
    )


def test_sustituir_cabeceras_falsificadas(entorno):
    cliente, solicitudes, _ = entorno

    respuesta = cliente.get(
        "/salud",
        headers={
            **CABECERAS,
            "x-neuromedx-client-ip": "203.0.113.99",
            "x-neuromedx-proxy-key": "clave-falsa",
            "x-forwarded-for": "203.0.113.99",
            "x-real-ip": "203.0.113.99",
            "cookie": "sesion=ficticia",
        },
    )

    assert respuesta.status_code == 200

    cabeceras = solicitudes[0].headers

    assert cabeceras["x-neuromedx-client-ip"] == (
        "203.0.113.25"
    )

    assert cabeceras["x-neuromedx-proxy-key"] == (
        CLAVE_PRUEBA
    )

    assert "x-forwarded-for" not in cabeceras
    assert "x-real-ip" not in cabeceras
    assert "cf-connecting-ip" not in cabeceras
    assert "cookie" not in cabeceras


@pytest.mark.parametrize("codigo", [
    200, 201, 400, 401, 403,
    409, 422, 429, 500, 503,
])
def test_conservar_codigo_http(entorno, codigo):
    cliente, _, configuracion = entorno

    configuracion["status"] = codigo

    respuesta = cliente.get(
        "/usuarios/me",
        headers=CABECERAS,
    )

    assert respuesta.status_code == codigo


def test_conservar_cuerpo_json(entorno):
    cliente, _, configuracion = entorno

    configuracion["contenido"] = (
        b'{"estado":"correcto","total":2}'
    )

    respuesta = cliente.get(
        "/salud",
        headers=CABECERAS,
    )

    assert respuesta.json() == {
        "estado": "correcto",
        "total": 2,
    }


def test_conservar_retry_after(entorno):
    cliente, _, configuracion = entorno

    configuracion["status"] = 429
    configuracion["headers"]["retry-after"] = "60"

    respuesta = cliente.get(
        "/usuarios/me",
        headers=CABECERAS,
    )

    assert respuesta.status_code == 429
    assert respuesta.headers["retry-after"] == "60"


def test_filtrar_cabeceras_respuesta(entorno):
    cliente, _, configuracion = entorno

    configuracion["headers"].update({
        "set-cookie": "sesion=ficticia",
        "x-neuromedx-proxy-key": CLAVE_PRUEBA,
        "x-internal-server": "servidor-privado",
        "cache-control": "public",
    })

    respuesta = cliente.get(
        "/salud",
        headers=CABECERAS,
    )

    assert "set-cookie" not in respuesta.headers
    assert "x-neuromedx-proxy-key" not in respuesta.headers
    assert "x-internal-server" not in respuesta.headers

    assert respuesta.headers["cache-control"] == "no-store"

    assert respuesta.headers[
        "x-content-type-options"
    ] == "nosniff"


def test_respuesta_demasiado_grande(entorno):
    cliente, _, configuracion = entorno

    configuracion["contenido"] = (
        b"x" * (servidor.MAXIMO_RESPUESTA + 1)
    )

    respuesta = cliente.get(
        "/salud",
        headers=CABECERAS,
    )

    assert respuesta.status_code == 502


def test_solicitar_respuesta_sin_compresion(entorno):
    cliente, solicitudes, _ = entorno

    respuesta = cliente.get(
        "/salud",
        headers={
            **CABECERAS,
            "accept-encoding": "gzip, br",
        },
    )

    assert respuesta.status_code == 200
    assert solicitudes[0].headers["accept-encoding"] == "identity"


@pytest.mark.parametrize("codificacion", [
    "gzip",
    "deflate",
    "br",
    "zstd",
    "gzip, br",
])
def test_rechazar_respuesta_comprimida(entorno, codificacion):
    cliente, _, configuracion = entorno

    configuracion["headers"]["content-encoding"] = codificacion

    respuesta = cliente.get(
        "/salud",
        headers=CABECERAS,
    )

    assert respuesta.status_code == 502

    assert respuesta.json()["detail"] == (
        "Codificacion de respuesta no permitida."
    )


def test_permitir_codificacion_identity(entorno):
    cliente, _, configuracion = entorno

    configuracion["headers"]["content-encoding"] = "identity"

    respuesta = cliente.get(
        "/salud",
        headers=CABECERAS,
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "correcto"}
    assert "content-encoding" not in respuesta.headers


@pytest.mark.parametrize("codigo", [
    500,
    502,
    503,
    504,
    599,
])
def test_ocultar_detalles_internos(entorno, codigo):
    cliente, _, configuracion = entorno

    configuracion["status"] = codigo

    configuracion["contenido"] = (
        b'{"detail":"Error interno: credencial-ficticia"}'
    )

    respuesta = cliente.get(
        "/salud",
        headers=CABECERAS,
    )

    assert respuesta.status_code == codigo

    assert respuesta.json() == {
        "detail": "Servicio temporalmente no disponible."
    }

    assert "credencial-ficticia" not in respuesta.text
    assert respuesta.headers["cache-control"] == "no-store"
    assert respuesta.headers["x-content-type-options"] == "nosniff"


def test_conservar_retry_after_error_503(entorno):
    cliente, _, configuracion = entorno

    configuracion["status"] = 503
    configuracion["headers"]["retry-after"] = "5"

    configuracion["contenido"] = (
        b'{"detail":"Informacion interna ficticia"}'
    )

    respuesta = cliente.get(
        "/salud",
        headers=CABECERAS,
    )

    assert respuesta.status_code == 503
    assert respuesta.headers["retry-after"] == "5"

    assert respuesta.json() == {
        "detail": "Servicio temporalmente no disponible."
    }

    assert "Informacion interna ficticia" not in respuesta.text
