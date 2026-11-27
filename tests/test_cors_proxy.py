import pytest
import httpx

from fastapi.testclient import TestClient

from app.seguridad.proxy import servidor, cors, politicas
from app.seguridad.limitador import LimitadorSolicitudes


CLAVE_PRUEBA = "a" * 64
ORIGEN = "https://medicos.neuromedx.site"
IP_CLIENTE = "203.0.113.25"

CABECERAS = {
    "host": "api.neuromedx.site",
    "cf-connecting-ip": IP_CLIENTE,
}

PREFLIGHT = {
    **CABECERAS,
    "origin": ORIGEN,
    "access-control-request-method": "GET",
    "access-control-request-headers": "authorization",
}


class FlujoSimulado(httpx.AsyncByteStream):

    def __init__(self, contenido):
        self.contenido = contenido

    async def __aiter__(self):
        yield self.contenido

    async def aclose(self):
        pass


@pytest.fixture
def entorno(monkeypatch):

    solicitudes = []

    configuracion = {
        "status": 200,
        "contenido": b'{"usuario":{"rol":"medico"}}',
        "headers": {
            "content-type": "application/json",
        },
    }

    monkeypatch.setattr(
        servidor,
        "CLAVE_INTERNA",
        CLAVE_PRUEBA,
    )

    monkeypatch.setattr(
        cors,
        "ORIGENES_CORS_PERMITIDOS",
        frozenset({ORIGEN}),
    )

    monkeypatch.setattr(
        politicas,
        "limitador_proxy",
        LimitadorSolicitudes(),
    )

    cliente_original = httpx.AsyncClient

    async def backend_simulado(request):

        solicitudes.append(request)

        return httpx.Response(
            status_code=configuracion["status"],
            stream=FlujoSimulado(
                configuracion["contenido"]
            ),
            headers=configuracion["headers"],
        )

    def crear_cliente(*args, **kwargs):

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


# ==========================================
# SOLICITUDES OPTIONS
# ==========================================

def test_preflight_autorizado(entorno):

    cliente, solicitudes, _ = entorno

    respuesta = cliente.options(
        "/usuarios/me",
        headers=PREFLIGHT,
    )

    assert respuesta.status_code == 204
    assert solicitudes == []


@pytest.mark.parametrize("origen", [
    "https://externo.com",
    "http://localhost:3000",
])
def test_preflight_origen_rechazado(entorno, origen):

    cliente, solicitudes, _ = entorno

    respuesta = cliente.options(
        "/usuarios/me",
        headers={
            **PREFLIGHT,
            "origin": origen,
        },
    )

    assert respuesta.status_code == 403
    assert solicitudes == []


def test_preflight_dominio_incorrecto(entorno):

    cliente, solicitudes, _ = entorno

    respuesta = cliente.options(
        "/usuarios/me",
        headers={
            **PREFLIGHT,
            "host": "externo.example",
        },
    )

    assert respuesta.status_code == 403
    assert solicitudes == []


def test_preflight_metodo_rechazado(entorno):

    cliente, solicitudes, _ = entorno

    respuesta = cliente.options(
        "/usuarios/me",
        headers={
            **PREFLIGHT,
            "access-control-request-method": "DELETE",
        },
    )

    assert respuesta.status_code == 403
    assert solicitudes == []


def test_preflight_ruta_privada(entorno):

    cliente, solicitudes, _ = entorno

    respuesta = cliente.options(
        "/docs",
        headers=PREFLIGHT,
    )

    assert respuesta.status_code == 403
    assert solicitudes == []


def test_preflight_cabecera_interna(entorno):

    cliente, solicitudes, _ = entorno

    respuesta = cliente.options(
        "/usuarios/me",
        headers={
            **PREFLIGHT,
            "access-control-request-headers":
                "x-neuromedx-proxy-key",
        },
    )

    assert respuesta.status_code == 403
    assert solicitudes == []


def test_preflight_ip_invalida(entorno):

    cliente, solicitudes, _ = entorno

    respuesta = cliente.options(
        "/usuarios/me",
        headers={
            **PREFLIGHT,
            "cf-connecting-ip": "ip-invalida",
        },
    )

    assert respuesta.status_code == 400
    assert solicitudes == []


def test_preflight_parametros_rechazados(entorno):

    cliente, solicitudes, _ = entorno

    respuesta = cliente.options(
        "/usuarios/me?prueba=1",
        headers=PREFLIGHT,
    )

    assert respuesta.status_code == 400
    assert solicitudes == []


def test_preflight_cabeceras_respuesta(entorno):

    cliente, _, _ = entorno

    respuesta = cliente.options(
        "/usuarios/me",
        headers=PREFLIGHT,
    )

    assert respuesta.status_code == 204

    assert respuesta.headers[
        "access-control-allow-origin"
    ] == ORIGEN

    assert "access-control-allow-credentials" not in (
        respuesta.headers
    )

    assert respuesta.headers["cache-control"] == "no-store"


def test_preflight_mantenimiento(
    entorno, indicador_proxy_pruebas
):

    cliente, solicitudes, _ = entorno

    indicador_proxy_pruebas.unlink()

    respuesta = cliente.options(
        "/usuarios/me",
        headers=PREFLIGHT,
    )

    assert respuesta.status_code == 503
    assert respuesta.headers["retry-after"] == "60"
    assert solicitudes == []


def test_preflight_cliente_no_local(entorno):

    _, solicitudes, _ = entorno

    with TestClient(
        servidor.app,
        client=("203.0.113.99", 12345),
    ) as externo:

        respuesta = externo.options(
            "/usuarios/me",
            headers=PREFLIGHT,
        )

    assert respuesta.status_code == 403
    assert solicitudes == []


# ==========================================
# SOLICITUDES GET Y POST
# ==========================================

def test_get_portal_autorizado(entorno):

    cliente, solicitudes, _ = entorno

    respuesta = cliente.get(
        "/usuarios/me",
        headers={
            **CABECERAS,
            "origin": ORIGEN,
            "authorization": "Bearer token-ficticio",
        },
    )

    assert respuesta.status_code == 200

    assert respuesta.headers[
        "access-control-allow-origin"
    ] == ORIGEN

    assert respuesta.json()["usuario"]["rol"] == "medico"
    assert len(solicitudes) == 1


def test_get_error_autenticacion_con_cors(entorno):

    cliente, _, configuracion = entorno

    configuracion["status"] = 401

    respuesta = cliente.get(
        "/usuarios/me",
        headers={
            **CABECERAS,
            "origin": ORIGEN,
        },
    )

    assert respuesta.status_code == 401

    assert respuesta.headers[
        "access-control-allow-origin"
    ] == ORIGEN


def test_conservar_www_authenticate(entorno):

    cliente, _, configuracion = entorno

    configuracion["status"] = 401

    configuracion["headers"][
        "www-authenticate"
    ] = "Bearer"

    respuesta = cliente.get(
        "/usuarios/me",
        headers={
            **CABECERAS,
            "origin": ORIGEN,
        },
    )

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


def test_get_sin_origen(entorno):

    cliente, solicitudes, _ = entorno

    respuesta = cliente.get(
        "/usuarios/me",
        headers=CABECERAS,
    )

    assert respuesta.status_code == 200

    assert "access-control-allow-origin" not in (
        respuesta.headers
    )

    assert len(solicitudes) == 1


def test_post_sin_origen(entorno):

    cliente, solicitudes, configuracion = entorno

    configuracion["status"] = 201

    respuesta = cliente.post(
        "/usuarios/registro-paciente",
        headers={
            **CABECERAS,
            "authorization": "Bearer token-ficticio",
        },
        json={
            "nombre": "Usuario",
            "apellido": "Prueba",
        },
    )

    assert respuesta.status_code == 201

    assert "access-control-allow-origin" not in (
        respuesta.headers
    )

    assert len(solicitudes) == 1


def test_get_origen_externo(entorno):

    cliente, solicitudes, _ = entorno

    respuesta = cliente.get(
        "/usuarios/me",
        headers={
            **CABECERAS,
            "origin": "https://externo.com",
        },
    )

    assert respuesta.status_code == 403
    assert solicitudes == []

    assert "access-control-allow-origin" not in (
        respuesta.headers
    )


def test_get_mantenimiento_con_cors(
    entorno, indicador_proxy_pruebas
):

    cliente, solicitudes, _ = entorno

    indicador_proxy_pruebas.unlink()

    respuesta = cliente.get(
        "/usuarios/me",
        headers={
            **CABECERAS,
            "origin": ORIGEN,
        },
    )

    assert respuesta.status_code == 503
    assert respuesta.headers["retry-after"] == "60"

    assert respuesta.headers[
        "access-control-allow-origin"
    ] == ORIGEN

    assert solicitudes == []


def test_conservar_clave_interna(entorno):

    cliente, solicitudes, _ = entorno

    respuesta = cliente.get(
        "/usuarios/me",
        headers={
            **CABECERAS,
            "origin": ORIGEN,
        },
    )

    assert respuesta.status_code == 200

    assert solicitudes[0].headers[
        "x-neuromedx-proxy-key"
    ] == CLAVE_PRUEBA


def test_conservar_ip_cliente(entorno):

    cliente, solicitudes, _ = entorno

    respuesta = cliente.get(
        "/usuarios/me",
        headers={
            **CABECERAS,
            "origin": ORIGEN,
        },
    )

    assert respuesta.status_code == 200

    assert solicitudes[0].headers[
        "x-neuromedx-client-ip"
    ] == IP_CLIENTE

@pytest.mark.parametrize("metodo,ruta", [
    ("POST", "/usuarios/registro-medico"),
    ("GET", "/medicos/me"),
])
def test_preflight_medico_autorizado(
    entorno,
    metodo,
    ruta,
):

    cliente, solicitudes, _ = entorno

    respuesta = cliente.options(
        ruta,
        headers={
            **PREFLIGHT,
            "access-control-request-method": metodo,
            "access-control-request-headers": (
                "authorization, content-type"
            ),
        },
    )

    assert respuesta.status_code == 204

    assert respuesta.headers[
        "access-control-allow-origin"
    ] == ORIGEN

    assert metodo in respuesta.headers[
        "access-control-allow-methods"
    ]

    assert "authorization" in respuesta.headers[
        "access-control-allow-headers"
    ].lower()

    assert "access-control-allow-credentials" not in (
        respuesta.headers
    )

    assert respuesta.headers["cache-control"] == "no-store"

    assert solicitudes == []


@pytest.mark.parametrize("metodo,ruta", [
    ("POST", "/usuarios/registro-medico"),
    ("GET", "/medicos/me"),
])
@pytest.mark.parametrize("origen", [
    "https://externo.example",
    "http://medicos.neuromedx.site",
    "https://medicos.neuromedx.site.externo.example",
    "http://localhost:3000",
    "null",
])
def test_preflight_medico_origen_rechazado(
    entorno,
    metodo,
    ruta,
    origen,
):

    cliente, solicitudes, _ = entorno

    respuesta = cliente.options(
        ruta,
        headers={
            **PREFLIGHT,
            "origin": origen,
            "access-control-request-method": metodo,
        },
    )

    assert respuesta.status_code == 403
    assert solicitudes == []

    assert "access-control-allow-origin" not in (
        respuesta.headers
    )


@pytest.mark.parametrize("metodo,ruta", [
    ("GET", "/usuarios/registro-medico"),
    ("DELETE", "/usuarios/registro-medico"),
    ("POST", "/medicos/me"),
    ("PUT", "/medicos/me"),
])
def test_preflight_medico_metodo_rechazado(
    entorno,
    metodo,
    ruta,
):

    cliente, solicitudes, _ = entorno

    respuesta = cliente.options(
        ruta,
        headers={
            **PREFLIGHT,
            "access-control-request-method": metodo,
        },
    )

    assert respuesta.status_code == 403
    assert solicitudes == []


@pytest.mark.parametrize("metodo,ruta", [
    ("POST", "/usuarios/registro-medico"),
    ("GET", "/medicos/me"),
])
def test_preflight_medico_cabecera_interna(
    entorno,
    metodo,
    ruta,
):

    cliente, solicitudes, _ = entorno

    respuesta = cliente.options(
        ruta,
        headers={
            **PREFLIGHT,
            "access-control-request-method": metodo,
            "access-control-request-headers": (
                "authorization, x-neuromedx-proxy-key"
            ),
        },
    )

    assert respuesta.status_code == 403
    assert solicitudes == []


def test_post_registro_medico_con_cors(entorno):

    cliente, solicitudes, configuracion = entorno

    configuracion["status"] = 201

    datos = {
        "nombre": "Medico",
        "apellido": "Prueba",
        "cedula_profesional": "00123456",
        "especialidad": "Medicina general",
        "institucion_formacion": "Universidad de prueba",
    }

    respuesta = cliente.post(
        "/usuarios/registro-medico",
        headers={
            **CABECERAS,
            "origin": ORIGEN,
            "authorization": "Bearer token-ficticio",
        },
        json=datos,
    )

    assert respuesta.status_code == 201

    assert respuesta.headers[
        "access-control-allow-origin"
    ] == ORIGEN

    assert len(solicitudes) == 1

    assert solicitudes[0].headers[
        "authorization"
    ] == "Bearer token-ficticio"

    assert respuesta.headers["cache-control"] == "no-store"


def test_get_perfil_medico_con_cors(entorno):

    cliente, solicitudes, _ = entorno

    respuesta = cliente.get(
        "/medicos/me",
        headers={
            **CABECERAS,
            "origin": ORIGEN,
            "authorization": "Bearer token-ficticio",
        },
    )

    assert respuesta.status_code == 200

    assert respuesta.headers[
        "access-control-allow-origin"
    ] == ORIGEN

    assert len(solicitudes) == 1

    assert solicitudes[0].headers[
        "authorization"
    ] == "Bearer token-ficticio"

    assert respuesta.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("metodo,ruta", [
    ("POST", "/usuarios/registro-medico"),
    ("GET", "/medicos/me"),
])
def test_solicitud_medica_origen_externo(
    entorno,
    metodo,
    ruta,
):

    cliente, solicitudes, _ = entorno

    respuesta = cliente.request(
        metodo,
        ruta,
        headers={
            **CABECERAS,
            "origin": "https://externo.example",
            "authorization": "Bearer token-ficticio",
        },
    )

    assert respuesta.status_code == 403

    assert solicitudes == []

    assert "access-control-allow-origin" not in (
        respuesta.headers
    )


@pytest.mark.parametrize("codigo", [
    401, 403, 409, 422, 429, 503,
])
def test_error_registro_medico_con_cors(
    entorno,
    codigo,
):

    cliente, solicitudes, configuracion = entorno

    configuracion["status"] = codigo

    respuesta = cliente.post(
        "/usuarios/registro-medico",
        headers={
            **CABECERAS,
            "origin": ORIGEN,
            "authorization": "Bearer token-ficticio",
        },
        json={},
    )

    assert respuesta.status_code == codigo

    assert respuesta.headers[
        "access-control-allow-origin"
    ] == ORIGEN

    assert len(solicitudes) == 1
