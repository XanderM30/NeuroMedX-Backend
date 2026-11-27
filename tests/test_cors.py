import pytest

from starlette.requests import Request

from app.seguridad.proxy import cors


ORIGEN_AUTORIZADO = "https://medicos.neuromedx.site"


@pytest.fixture(autouse=True)
def configurar_origenes(monkeypatch):
    monkeypatch.setattr(
        cors,
        "ORIGENES_CORS_PERMITIDOS",
        frozenset({ORIGEN_AUTORIZADO}),
    )


def crear_solicitud(
    origen=ORIGEN_AUTORIZADO,
    metodo="GET",
    ruta="/usuarios/me",
    cabeceras="authorization",
    adicionales=None,
):
    headers = [
        (b"origin", origen.encode("ascii")),
        (
            b"access-control-request-method",
            metodo.encode("ascii"),
        ),
        (
            b"access-control-request-headers",
            cabeceras.encode("ascii"),
        ),
    ]

    if adicionales:
        headers.extend(adicionales)

    return Request({
        "type": "http",
        "method": "OPTIONS",
        "path": ruta,
        "raw_path": ruta.encode("ascii"),
        "query_string": b"",
        "headers": headers,
    })


# ==========================================
# ORIGENES CORS
# ==========================================

def test_origen_autorizado():
    solicitud = crear_solicitud()

    respuesta = cors.procesar_preflight(solicitud)

    assert respuesta.status_code == 204

    assert respuesta.headers[
        "access-control-allow-origin"
    ] == ORIGEN_AUTORIZADO

    assert respuesta.headers[
        "access-control-allow-methods"
    ] == "GET"

    assert "access-control-allow-credentials" not in (
        respuesta.headers
    )

    assert respuesta.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("origen", [
    "https://externo.com",
    "http://localhost:3000",
    "null",
])
def test_origen_no_autorizado(origen):
    solicitud = crear_solicitud(origen=origen)

    respuesta = cors.procesar_preflight(solicitud)

    assert respuesta.status_code == 403

    assert "access-control-allow-origin" not in (
        respuesta.headers
    )


# ==========================================
# METODOS Y RUTAS
# ==========================================

def test_metodo_no_autorizado():
    solicitud = crear_solicitud(metodo="DELETE")

    respuesta = cors.procesar_preflight(solicitud)

    assert respuesta.status_code == 403

    assert "access-control-allow-origin" not in (
        respuesta.headers
    )


def test_ruta_no_autorizada():
    solicitud = crear_solicitud(ruta="/docs")

    respuesta = cors.procesar_preflight(solicitud)

    assert respuesta.status_code == 403

    assert "access-control-allow-origin" not in (
        respuesta.headers
    )


# ==========================================
# CABECERAS CORS
# ==========================================

def test_cabecera_interna_no_autorizada():
    solicitud = crear_solicitud(
        cabeceras="x-neuromedx-proxy-key"
    )

    respuesta = cors.procesar_preflight(solicitud)

    assert respuesta.status_code == 403

    assert "access-control-allow-origin" not in (
        respuesta.headers
    )


def test_cabeceras_autorizadas():
    solicitud = crear_solicitud(
        metodo="POST",
        ruta="/usuarios/registro-paciente",
        cabeceras="authorization, content-type",
    )

    respuesta = cors.procesar_preflight(solicitud)

    assert respuesta.status_code == 204

    permitidas = {
        nombre.strip().lower()
        for nombre in respuesta.headers[
            "access-control-allow-headers"
        ].split(",")
    }

    assert "authorization" in permitidas
    assert "content-type" in permitidas
    assert "x-neuromedx-proxy-key" not in permitidas

    assert respuesta.headers[
        "access-control-allow-methods"
    ] == "POST"

    assert respuesta.headers[
        "access-control-max-age"
    ] == "600"


# ==========================================
# CABECERAS DUPLICADAS
# ==========================================

def test_origen_duplicado():
    solicitud = crear_solicitud(
        adicionales=[
            (b"origin", b"https://externo.com"),
        ],
    )

    respuesta = cors.procesar_preflight(solicitud)

    assert respuesta.status_code == 403

    assert "access-control-allow-origin" not in (
        respuesta.headers
    )


def test_metodo_duplicado():
    solicitud = crear_solicitud(
        adicionales=[
            (
                b"access-control-request-method",
                b"POST",
            ),
        ],
    )

    respuesta = cors.procesar_preflight(solicitud)

    assert respuesta.status_code == 403

    assert "access-control-allow-origin" not in (
        respuesta.headers
    )
