import pytest

from starlette.datastructures import Headers

from app.seguridad.proxy.cabeceras import (
    validar_ip_cliente,
    obtener_ip_cloudflare,
    preparar_cabeceras,
)


@pytest.mark.parametrize("ip,esperado", [
    ("203.0.113.25", "203.0.113.25"),
    ("2001:db8::1", "2001:db8::1"),
    (" 203.0.113.25 ", "203.0.113.25"),
    ("2001:0db8:0000::1", "2001:db8::1"),
])
def test_ip_valida(ip, esperado):
    assert validar_ip_cliente(ip) == esperado


@pytest.mark.parametrize("ip", [
    "",
    " ",
    "direccion-invalida",
    "999.999.999.999",
    "203.0.113.25, 203.0.113.26",
    "fe80::1%eth0",
])
def test_ip_invalida(ip):
    with pytest.raises(ValueError):
        validar_ip_cliente(ip)


def test_ip_cloudflare_valida():
    cabeceras = Headers({
        "cf-connecting-ip": "203.0.113.25",
    })

    assert obtener_ip_cloudflare(
        cabeceras
    ) == "203.0.113.25"


def test_ip_cloudflare_ausente():
    with pytest.raises(ValueError):
        obtener_ip_cloudflare(Headers({}))


def test_ip_cloudflare_duplicada():
    cabeceras = Headers(raw=[
        (b"cf-connecting-ip", b"203.0.113.25"),
        (b"cf-connecting-ip", b"203.0.113.26"),
    ])

    with pytest.raises(ValueError):
        obtener_ip_cloudflare(cabeceras)


def test_conservar_cabeceras_autorizadas():
    cabeceras = Headers({
        "authorization": "Bearer token-ficticio",
        "content-type": "application/json",
        "accept": "application/json",
    })

    assert preparar_cabeceras(cabeceras) == {
        "authorization": "Bearer token-ficticio",
        "content-type": "application/json",
        "accept": "application/json",
    }


def test_eliminar_cabeceras_no_autorizadas():
    cabeceras = Headers({
        "authorization": "Bearer token-ficticio",
        "host": "api.neuromedx.site",
        "cf-connecting-ip": "203.0.113.25",
        "x-forwarded-for": "203.0.113.26",
        "x-real-ip": "203.0.113.26",
        "forwarded": "for=203.0.113.26",
        "x-neuromedx-proxy-key": "clave-falsa",
        "x-neuromedx-client-ip": "203.0.113.26",
        "cookie": "sesion=ficticia",
        "connection": "keep-alive",
        "transfer-encoding": "chunked",
        "content-length": "100",
    })

    assert preparar_cabeceras(cabeceras) == {
        "authorization": "Bearer token-ficticio",
    }


@pytest.mark.parametrize("nombre", [
    "authorization",
    "content-type",
    "accept",
])
def test_rechazar_cabeceras_duplicadas(nombre):
    cabeceras = Headers(raw=[
        (nombre.encode(), b"valor-uno"),
        (nombre.encode(), b"valor-dos"),
    ])

    with pytest.raises(ValueError):
        preparar_cabeceras(cabeceras)


def test_cabeceras_vacias():
    assert preparar_cabeceras(Headers({})) == {}
