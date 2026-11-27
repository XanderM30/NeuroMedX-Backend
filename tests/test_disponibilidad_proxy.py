import asyncio
import pytest
import httpx

from fastapi.testclient import TestClient
from app.seguridad.proxy import servidor

CLIENTE_HTTPX_ORIGINAL = httpx.AsyncClient


CABECERAS = {
    "host": "api.neuromedx.site",
    "cf-connecting-ip": "203.0.113.25",
}


@pytest.fixture
def entorno(monkeypatch):
    estado = {
        "error": None,
        "llamadas": 0,
    }

    semaforo = asyncio.Semaphore(1)

    monkeypatch.setattr(
        servidor,
        "CLAVE_INTERNA",
        "a" * 64,
    )

    monkeypatch.setattr(
        servidor,
        "conexiones",
        semaforo,
    )

    monkeypatch.setattr(
        servidor,
        "TIMEOUT_POOL",
        0.05,
    )

    cliente_original = CLIENTE_HTTPX_ORIGINAL

    async def backend_simulado(request):
        estado["llamadas"] += 1

        if estado["error"] is not None:
            raise estado["error"](
                "Error interno simulado",
                request=request,
            )

        return httpx.Response(
            200,
            stream=httpx.ByteStream(b'{"estado":"operativo"}'),
            headers={"content-type": "application/json"},
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
        yield cliente, estado, semaforo


@pytest.mark.parametrize("tipo_error", [
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
])
def test_tiempos_de_espera(entorno, tipo_error):
    cliente, estado, semaforo = entorno

    estado["error"] = tipo_error

    respuesta = cliente.get(
        "/salud",
        headers=CABECERAS,
    )

    assert respuesta.status_code == 504
    assert not semaforo.locked()
    assert "Error interno simulado" not in respuesta.text


@pytest.mark.parametrize("tipo_error", [
    httpx.ConnectError,
    httpx.ReadError,
    httpx.WriteError,
    httpx.RemoteProtocolError,
])
def test_backend_no_disponible(entorno, tipo_error):
    cliente, estado, semaforo = entorno

    estado["error"] = tipo_error

    respuesta = cliente.get(
        "/salud",
        headers=CABECERAS,
    )

    assert respuesta.status_code == 502
    assert not semaforo.locked()
    assert "Error interno simulado" not in respuesta.text


def test_proxy_saturado(entorno):
    cliente, estado, semaforo = entorno

    cliente.portal.call(semaforo.acquire)

    try:
        respuesta = cliente.get(
            "/salud",
            headers=CABECERAS,
        )

        assert respuesta.status_code == 503
        assert estado["llamadas"] == 0

    finally:
        cliente.portal.call(semaforo.release)


def test_recuperacion_despues_de_error(entorno):
    cliente, estado, semaforo = entorno

    estado["error"] = httpx.ConnectError

    primera = cliente.get(
        "/salud",
        headers=CABECERAS,
    )

    assert primera.status_code == 502
    assert not semaforo.locked()

    estado["error"] = None

    segunda = cliente.get(
        "/salud",
        headers=CABECERAS,
    )

    assert segunda.status_code == 200
    assert segunda.json()["estado"] == "operativo"
    assert estado["llamadas"] == 2
    assert not semaforo.locked()


def test_liberar_conexion_despues_de_exito(entorno):
    cliente, estado, semaforo = entorno

    for _ in range(5):
        respuesta = cliente.get(
            "/salud",
            headers=CABECERAS,
        )

        assert respuesta.status_code == 200
        assert not semaforo.locked()

    assert estado["llamadas"] == 5


def test_tiempo_maximo_total(entorno, monkeypatch):
    cliente, estado, semaforo = entorno

    monkeypatch.setattr(servidor, "TIMEOUT_CONEXION", 0.05)
    monkeypatch.setattr(servidor, "TIMEOUT_LECTURA", 0.05)
    monkeypatch.setattr(servidor, "TIMEOUT_ESCRITURA", 0.05)
    monkeypatch.setattr(servidor, "TIMEOUT_POOL", 0.05)

    cliente_original = CLIENTE_HTTPX_ORIGINAL

    espera = {
        "segundos": 2,
        "cancelada": False,
    }

    async def backend_lento(request):
        estado["llamadas"] += 1

        try:
            await asyncio.sleep(espera["segundos"])
        except asyncio.CancelledError:
            espera["cancelada"] = True
            raise

        return httpx.Response(
            200,
            stream=httpx.ByteStream(b'{"estado":"operativo"}'),
            headers={"content-type": "application/json"},
        )

    def crear_cliente_lento(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(
            backend_lento
        )

        return cliente_original(*args, **kwargs)

    monkeypatch.setattr(
        servidor.httpx,
        "AsyncClient",
        crear_cliente_lento,
    )

    respuesta = cliente.get(
        "/salud",
        headers=CABECERAS,
    )

    assert respuesta.status_code == 504
    assert espera["cancelada"] is True
    assert not semaforo.locked()
    assert estado["llamadas"] == 1

    espera["segundos"] = 0

    recuperacion = cliente.get(
        "/salud",
        headers=CABECERAS,
    )

    assert recuperacion.status_code == 200
    assert estado["llamadas"] == 2
    assert not semaforo.locked()
