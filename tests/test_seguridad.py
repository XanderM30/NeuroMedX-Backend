import pytest
import anyio

from concurrent.futures import ThreadPoolExecutor
from collections import Counter

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.seguridad import politicas, middleware
from app.seguridad import tamano_solicitudes
from app.seguridad.limitador import LimitadorSolicitudes
from app.seguridad.concurrencia import (
    controlar_beto,
    controlar_tensorflow,
)


@pytest.fixture(autouse=True)
def aislar_limitadores(monkeypatch):

    limitador = LimitadorSolicitudes()

    monkeypatch.setattr(
        politicas,
        "limitador",
        limitador
    )

    monkeypatch.setattr(
        middleware,
        "limitador",
        limitador
    )

    yield


@pytest.fixture
def cliente():

    with TestClient(app) as cliente_prueba:
        yield cliente_prueba


# ==========================================
# RESTRICCIONES DE ACCESO
# ==========================================

@pytest.mark.parametrize(
    "ruta",
    [
        "/",
        "/salud",
        "/pulsera/",
        "/pulsera/health",
    ]
)
def test_endpoints_publicos(cliente, ruta):

    respuesta = cliente.get(ruta)

    assert respuesta.status_code == 200


@pytest.mark.parametrize(
    "ruta",
    [
        "/docs",
        "/redoc",
        "/openapi.json",
        "/salud/base-datos",
    ]
)
def test_endpoints_restringidos(cliente, ruta):

    respuesta = cliente.get(ruta)

    assert respuesta.status_code == 404


@pytest.mark.parametrize(
    "metodo,ruta,cuerpo",
    [
        ("GET", "/usuarios/me", None),
        ("GET", "/ia/sintomas/health", None),
        ("GET", "/ia/sintomas/catalogo", None),
        (
            "POST",
            "/ia/medicamentos/detectar",
            {"texto": "Paracetamol"},
        ),
        (
            "POST",
            "/ia/sintomas/analizar",
            {"texto": "Fiebre y tos"},
        ),
        (
            "POST",
            "/usuarios/registro-paciente",
            {"nombre": "Usuario", "apellido": "Prueba"},
        ),
    ]
)
def test_autenticacion_obligatoria(
    cliente, metodo, ruta, cuerpo
):

    respuesta = cliente.request(
        metodo,
        ruta,
        json=cuerpo
    )

    assert respuesta.status_code == 401


# ==========================================
# LIMITADOR GENERAL
# ==========================================

def test_limite_general(cliente):

    for _ in range(120):

        respuesta = cliente.get("/salud")

        assert respuesta.status_code == 200

    respuesta = cliente.get("/salud")

    assert respuesta.status_code == 429
    assert "Retry-After" in respuesta.headers


# ==========================================
# LIMITADORES POR UID
# ==========================================

@pytest.mark.parametrize(
    "funcion,limite",
    [
        (politicas.limitar_medicamentos, 20),
        (politicas.limitar_sintomas, 10),
        (politicas.limitar_registro, 5),
        (politicas.limitar_perfil, 60),
    ]
)
def test_cuotas_por_uid(funcion, limite):

    for _ in range(limite):
        funcion("uid-prueba-a")

    with pytest.raises(HTTPException) as error:
        funcion("uid-prueba-a")

    assert error.value.status_code == 429
    assert "Retry-After" in error.value.headers

    for _ in range(limite):
        funcion("uid-prueba-b")

    with pytest.raises(HTTPException) as error:
        funcion("uid-prueba-b")

    assert error.value.status_code == 429


def test_independencia_entre_servicios():

    uid = "uid-prueba-servicios"

    for _ in range(20):
        politicas.limitar_medicamentos(uid)

    with pytest.raises(HTTPException) as error:
        politicas.limitar_medicamentos(uid)

    assert error.value.status_code == 429

    politicas.limitar_sintomas(uid)
    politicas.limitar_registro(uid)
    politicas.limitar_perfil(uid)


# ==========================================
# CONCURRENCIA DEL LIMITADOR
# ==========================================

@pytest.mark.parametrize(
    "funcion,limite",
    [
        (politicas.limitar_medicamentos, 20),
        (politicas.limitar_sintomas, 10),
        (politicas.limitar_registro, 5),
        (politicas.limitar_perfil, 60),
    ]
)
def test_concurrencia_limitador(funcion, limite):

    def ejecutar(indice):

        try:
            funcion("uid-prueba-concurrencia")
            return 200

        except HTTPException as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=20) as executor:

        resultados = list(
            executor.map(ejecutar, range(100))
        )

    conteo = Counter(resultados)

    assert conteo[200] == limite
    assert conteo[429] == 100 - limite


# ==========================================
# CONCURRENCIA DE MODELOS
# ==========================================

@pytest.mark.parametrize(
    "control",
    [
        controlar_beto,
        controlar_tensorflow,
    ]
)
def test_modelo_ocupado(control):

    with control():

        with pytest.raises(HTTPException) as error:

            with control():
                pass

        assert error.value.status_code == 503
        assert error.value.headers["Retry-After"] == "5"

    # Comprobar liberacion del semaforo
    with control():
        pass


def test_modelos_independientes():

    with controlar_beto():

        with controlar_tensorflow():
            pass


@pytest.mark.parametrize(
    "control",
    [
        controlar_beto,
        controlar_tensorflow,
    ]
)
def test_liberacion_por_excepcion(control):

    with pytest.raises(RuntimeError):

        with control():
            raise RuntimeError("Error simulado")

    with control():
        pass


# ==========================================
# RESTRICCION DE TAMANO HTTP
# ==========================================

@pytest.mark.parametrize(
    "ruta,limite",
    [
        ("/usuarios/registro-paciente", 4096),
        ("/ia/medicamentos/detectar", 131072),
        ("/ia/sintomas/analizar", 32768),
        ("/pulsera/mediciones", 16384),
        ("/otra-ruta", 16384),
    ]
)
def test_cuerpo_excesivo(cliente, ruta, limite):

    respuesta = cliente.post(
        ruta,
        content=b"x" * (limite + 1)
    )

    assert respuesta.status_code == 413


def test_cuerpo_excesivo_sin_content_length(cliente):

    def fragmentos():

        yield b"x" * 3000
        yield b"x" * 2000

    respuesta = cliente.post(
        "/usuarios/registro-paciente",
        content=fragmentos()
    )

    assert "content-length" not in respuesta.request.headers
    assert respuesta.status_code == 413


def test_content_length_invalido(cliente):

    respuesta = cliente.post(
        "/usuarios/registro-paciente",
        content=b"prueba",
        headers={"Content-Length": "invalido"}
    )

    assert respuesta.status_code == 400


def test_prioridad_limitador_general(cliente):

    for _ in range(120):

        respuesta = cliente.get("/salud")

        assert respuesta.status_code == 200

    respuesta = cliente.post(
        "/usuarios/registro-paciente",
        content=b"x" * 4097
    )

    assert respuesta.status_code == 429


# ==========================================
# TIEMPO MAXIMO DE RECEPCION HTTP
# ==========================================

@pytest.mark.parametrize(
    "fragmentos,esperado",
    [
        ([(0, b"hola")], 200),
        ([(2, b"hola")], 408),
        ([(0.1, b"hola"), (0.1, b"mundo")], 200),
        ([(0.6, b"hola"), (0.6, b"mundo")], 408),
        ([(0, b"x" * 4097)], 413),
        ([(0, b"")], 200),
    ]
)
def test_tiempo_recepcion(
    monkeypatch, fragmentos, esperado
):

    monkeypatch.setattr(
        tamano_solicitudes,
        "TIEMPO_MAXIMO_RECEPCION_HTTP",
        1
    )

    async def ejecutar():

        mensajes = []
        posicion = 0

        async def aplicacion(scope, receive, send):

            mensaje = await receive()

            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            })

            await send({
                "type": "http.response.body",
                "body": mensaje.get("body", b""),
            })

        async def recibir():

            nonlocal posicion

            retraso, contenido = fragmentos[posicion]
            posicion += 1

            await anyio.sleep(retraso)

            return {
                "type": "http.request",
                "body": contenido,
                "more_body": posicion < len(fragmentos),
            }

        async def enviar(mensaje):

            mensajes.append(mensaje)

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/usuarios/registro-paciente",
            "headers": [],
        }

        proteccion = (
            tamano_solicitudes.LimitarTamanoSolicitudes(
                aplicacion
            )
        )

        await proteccion(scope, recibir, enviar)

        codigo = next(
            mensaje["status"]
            for mensaje in mensajes
            if mensaje["type"] == "http.response.start"
        )

        assert codigo == esperado

    anyio.run(ejecutar)