import pytest
import httpx

from fastapi.testclient import TestClient

from app.seguridad.proxy import servidor, cors, politicas
from app.seguridad import limitador
from app.seguridad.limitador import LimitadorSolicitudes


ORIGEN = "https://medicos.neuromedx.site"

IP_A = "203.0.113.10"
IP_B = "203.0.113.20"

CABECERAS = {
    "host": "api.neuromedx.site",
    "cf-connecting-ip": IP_A,
    "origin": ORIGEN,
    "access-control-request-method": "GET",
    "access-control-request-headers": "authorization",
}


@pytest.fixture
def entorno(monkeypatch):

    reloj = {"ahora": 1000.0}

    monkeypatch.setattr(
        limitador,
        "monotonic",
        lambda: reloj["ahora"],
    )

    monkeypatch.setattr(
        servidor,
        "CLAVE_INTERNA",
        "a" * 64,
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

    def bloquear_backend(*args, **kwargs):
        pytest.fail(
            "Una solicitud preflight intento acceder al backend."
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

        yield cliente, reloj


def solicitar(cliente, ip=IP_A):

    return cliente.options(
        "/usuarios/me",
        headers={
            **CABECERAS,
            "cf-connecting-ip": ip,
        },
    )


def saturar(cliente):

    for _ in range(60):

        respuesta = solicitar(cliente)

        assert respuesta.status_code == 204


# ==========================================
# SATURACION DEL LIMITADOR
# ==========================================

def test_primeras_60_solicitudes(entorno):

    cliente, _ = entorno

    saturar(cliente)


def test_solicitud_61_bloqueada(entorno):

    cliente, _ = entorno

    saturar(cliente)

    assert solicitar(cliente).status_code == 429


def test_retry_after_valido(entorno):

    cliente, _ = entorno

    saturar(cliente)

    respuesta = solicitar(cliente)

    assert respuesta.status_code == 429

    assert 1 <= int(
        respuesta.headers["retry-after"]
    ) <= 60


def test_misma_ip_permanece_bloqueada(entorno):

    cliente, _ = entorno

    saturar(cliente)

    assert solicitar(cliente).status_code == 429
    assert solicitar(cliente).status_code == 429


def test_otra_ip_independiente(entorno):

    cliente, _ = entorno

    saturar(cliente)

    assert solicitar(cliente, IP_A).status_code == 429
    assert solicitar(cliente, IP_B).status_code == 204


def test_respuesta_429_sin_cache(entorno):

    cliente, _ = entorno

    saturar(cliente)

    respuesta = solicitar(cliente)

    assert respuesta.status_code == 429

    assert respuesta.headers[
        "cache-control"
    ] == "no-store"


def test_respuesta_429_sin_credenciales(entorno):

    cliente, _ = entorno

    saturar(cliente)

    respuesta = solicitar(cliente)

    assert respuesta.status_code == 429

    assert "access-control-allow-credentials" not in (
        respuesta.headers
    )


# ==========================================
# RECUPERACION DEL ACCESO
# ==========================================

def test_ventana_inicial_completa(entorno):

    cliente, reloj = entorno

    saturar(cliente)

    assert reloj["ahora"] == 1000.0


def test_bloqueo_inicial(entorno):

    cliente, _ = entorno

    saturar(cliente)

    respuesta = solicitar(cliente)

    assert respuesta.status_code == 429
    assert respuesta.headers["retry-after"] == "60"


@pytest.mark.parametrize("segundos", [
    30,
    59,
])
def test_bloqueo_antes_de_expirar(entorno, segundos):

    cliente, reloj = entorno

    saturar(cliente)

    reloj["ahora"] += segundos

    assert solicitar(cliente).status_code == 429


@pytest.mark.parametrize("segundos,espera", [
    (30, "30"),
    (59, "1"),
])
def test_retry_after_actualizado(
    entorno, segundos, espera
):

    cliente, reloj = entorno

    saturar(cliente)

    reloj["ahora"] += segundos

    respuesta = solicitar(cliente)

    assert respuesta.status_code == 429
    assert respuesta.headers["retry-after"] == espera


def test_recuperacion_a_los_60_segundos(entorno):

    cliente, reloj = entorno

    saturar(cliente)

    assert solicitar(cliente).status_code == 429

    reloj["ahora"] += 60

    assert solicitar(cliente).status_code == 204


def test_retry_after_eliminado(entorno):

    cliente, reloj = entorno

    saturar(cliente)

    assert solicitar(cliente).status_code == 429

    reloj["ahora"] += 60

    respuesta = solicitar(cliente)

    assert respuesta.status_code == 204
    assert "retry-after" not in respuesta.headers


def test_nueva_ventana_disponible(entorno):

    cliente, reloj = entorno

    saturar(cliente)

    assert solicitar(cliente).status_code == 429

    reloj["ahora"] += 60

    saturar(cliente)


def test_limite_aplicado_nuevamente(entorno):

    cliente, reloj = entorno

    saturar(cliente)

    assert solicitar(cliente).status_code == 429

    reloj["ahora"] += 60

    saturar(cliente)

    respuesta = solicitar(cliente)

    assert respuesta.status_code == 429
    assert respuesta.headers["retry-after"] == "60"
