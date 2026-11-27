import asyncio

import httpx
import pytest

from app.seguridad.proxy import servidor


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("escenario,codigo", [
    ("recepcion_lenta", 408),
    ("cliente_desconectado", 400),
    ("cuerpo_excesivo", 413),
])
async def test_control_recepcion(
    monkeypatch,
    escenario,
    codigo,
):
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
        "TIMEOUT_RECEPCION",
        0.05,
    )

    def bloquear_backend(*args, **kwargs):
        pytest.fail(
            "La solicitud invalida alcanzo el backend."
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        bloquear_backend,
    )

    mensajes = []

    scope = {
        "type": "http",
        "asgi": {
            "version": "3.0",
            "spec_version": "2.4",
        },
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/usuarios/registro-paciente",
        "raw_path": b"/usuarios/registro-paciente",
        "query_string": b"",
        "root_path": "",
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 8002),
        "headers": [
            (b"host", b"api.neuromedx.site"),
            (b"cf-connecting-ip", b"203.0.113.25"),
            (b"content-type", b"application/json"),
        ],
    }

    async def receive():
        if escenario == "recepcion_lenta":
            await asyncio.sleep(1)

        if escenario == "cliente_desconectado":
            return {
                "type": "http.disconnect",
            }

        return {
            "type": "http.request",
            "body": b"x" * 4097,
            "more_body": False,
        }

    async def send(mensaje):
        mensajes.append(mensaje)

    await servidor.app(scope, receive, send)

    inicio = next(
        mensaje
        for mensaje in mensajes
        if mensaje["type"] == "http.response.start"
    )

    assert inicio["status"] == codigo
    assert not semaforo.locked()
