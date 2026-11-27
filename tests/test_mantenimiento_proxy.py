import pytest
import httpx

from pathlib import Path
from fastapi.testclient import TestClient

from app.seguridad.proxy import servidor
from app.seguridad.proxy.mantenimiento import servicio_habilitado


CABECERAS = {
    "host": "api.neuromedx.site",
    "cf-connecting-ip": "203.0.113.25",
}


def test_indicador_existente(indicador_proxy_pruebas):
    assert servicio_habilitado(indicador_proxy_pruebas)


def test_indicador_inexistente(indicador_proxy_pruebas):
    indicador_proxy_pruebas.unlink()

    assert not servicio_habilitado(indicador_proxy_pruebas)


def test_indicador_es_directorio(tmp_path):
    directorio = tmp_path / "directorio"
    directorio.mkdir()

    assert not servicio_habilitado(directorio)


def test_error_de_permisos(monkeypatch, indicador_proxy_pruebas):
    def acceso_denegado(self, *args, **kwargs):
        raise PermissionError("Acceso denegado")

    with monkeypatch.context() as contexto:
        contexto.setattr(Path, "stat", acceso_denegado)

        assert not servicio_habilitado(indicador_proxy_pruebas)


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setattr(
        servidor,
        "CLAVE_INTERNA",
        "a" * 64,
    )

    def bloquear_backend(*args, **kwargs):
        pytest.fail("Solicitud de mantenimiento llego al backend")

    monkeypatch.setattr(
        servidor.httpx,
        "AsyncClient",
        bloquear_backend,
    )

    with TestClient(
        servidor.app,
        client=("127.0.0.1", 12345),
    ) as cliente:
        yield cliente


@pytest.mark.parametrize("metodo,ruta", [
    ("GET", "/salud"),
    ("GET", "/usuarios/me"),
    ("POST", "/usuarios/registro-paciente"),
    ("POST", "/ia/medicamentos/detectar"),
])
def test_rutas_bloqueadas(
    cliente,
    indicador_proxy_pruebas,
    metodo,
    ruta,
):
    indicador_proxy_pruebas.unlink()

    respuesta = cliente.request(
        metodo,
        ruta,
        headers=CABECERAS,
    )

    assert respuesta.status_code == 503
    assert respuesta.headers["retry-after"] == "60"
    assert respuesta.headers["cache-control"] == "no-store"


def test_no_evasion_por_cabeceras(
    cliente,
    indicador_proxy_pruebas,
):
    indicador_proxy_pruebas.unlink()

    respuesta = cliente.get(
        "/salud",
        headers={
            **CABECERAS,
            "X-NeuroMedX-Proxy-Key": "a" * 64,
            "X-NeuroMedX-Client-IP": "127.0.0.1",
            "X-Maintenance-Bypass": "true",
        },
    )

    assert respuesta.status_code == 503


def test_ruta_privada_durante_mantenimiento(
    cliente,
    indicador_proxy_pruebas,
):
    indicador_proxy_pruebas.unlink()

    respuesta = cliente.get(
        "/docs",
        headers=CABECERAS,
    )

    assert respuesta.status_code == 404


def test_recuperacion_del_servicio(
    monkeypatch,
    indicador_proxy_pruebas,
):
    monkeypatch.setattr(
        servidor,
        "CLAVE_INTERNA",
        "a" * 64,
    )

    llamadas = []

    async def backend_simulado(request):
        llamadas.append(request)

        return httpx.Response(
            200,
            stream=httpx.ByteStream(b'{"estado":"operativo"}'),
            headers={"content-type": "application/json"},
        )

    cliente_original = httpx.AsyncClient

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

        indicador_proxy_pruebas.unlink()

        bloqueada = cliente.get(
            "/salud",
            headers=CABECERAS,
        )

        assert bloqueada.status_code == 503
        assert len(llamadas) == 0

        indicador_proxy_pruebas.write_text(
            "habilitado",
            encoding="utf-8",
        )

        recuperada = cliente.get(
            "/salud",
            headers=CABECERAS,
        )

        assert recuperada.status_code == 200
        assert len(llamadas) == 1
