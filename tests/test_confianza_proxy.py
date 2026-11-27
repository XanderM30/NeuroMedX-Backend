import pytest

from fastapi import Request, HTTPException
from app.seguridad import confianza_proxy

IP_SERVIDOR = "10.242.46.163"
IP_CLIENTE = "203.0.113.25"
CLAVE_PRUEBA = "a" * 64

@pytest.fixture(autouse=True)
def configurar_clave(monkeypatch):
    monkeypatch.setattr(
        confianza_proxy,
        "CLAVE_INTERNA",
        CLAVE_PRUEBA,
    )

def crear_solicitud(ip, cabeceras=None):
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/salud",
        "headers": [
            (nombre.lower().encode(), valor.encode())
            for nombre, valor in (cabeceras or [])
        ],
        "client": (ip, 12345),
    })

def cabeceras_proxy(
    clave=CLAVE_PRUEBA,
    ip=IP_CLIENTE,
):
    return [
        ("x-neuromedx-proxy-key", clave),
        ("x-neuromedx-client-ip", ip),
    ]

def test_conexion_directa():
    request = crear_solicitud("10.242.197.59")

    assert confianza_proxy.obtener_ip_cliente(
        request
    ) == "10.242.197.59"

def test_proxy_autorizado():
    request = crear_solicitud(
        IP_SERVIDOR,
        cabeceras_proxy(),
    )

    assert confianza_proxy.obtener_ip_cliente(
        request
    ) == IP_CLIENTE

def test_clave_incorrecta():
    request = crear_solicitud(
        IP_SERVIDOR,
        cabeceras_proxy(clave="b" * 64),
    )

    with pytest.raises(HTTPException) as error:
        confianza_proxy.obtener_ip_cliente(request)

    assert error.value.status_code == 403

def test_origen_no_autorizado():
    request = crear_solicitud(
        "10.242.197.59",
        cabeceras_proxy(),
    )

    with pytest.raises(HTTPException) as error:
        confianza_proxy.obtener_ip_cliente(request)

    assert error.value.status_code == 403

def test_cabecera_incompleta():
    request = crear_solicitud(
        IP_SERVIDOR,
        [("x-neuromedx-client-ip", IP_CLIENTE)],
    )

    with pytest.raises(HTTPException) as error:
        confianza_proxy.obtener_ip_cliente(request)

    assert error.value.status_code == 403

@pytest.mark.parametrize("nombre", [
    "x-neuromedx-proxy-key",
    "x-neuromedx-client-ip",
])
def test_cabeceras_duplicadas(nombre):
    cabeceras = cabeceras_proxy()
    cabeceras.append((nombre, "duplicado"))

    request = crear_solicitud(
        IP_SERVIDOR,
        cabeceras,
    )

    with pytest.raises(HTTPException) as error:
        confianza_proxy.obtener_ip_cliente(request)

    assert error.value.status_code == 403

@pytest.mark.parametrize("ip", [
    "",
    "direccion-invalida",
    "999.999.999.999",
    "203.0.113.25, 203.0.113.26",
    "fe80::1%eth0",
])
def test_ip_invalida(ip):
    request = crear_solicitud(
        IP_SERVIDOR,
        cabeceras_proxy(ip=ip),
    )

    with pytest.raises(HTTPException) as error:
        confianza_proxy.obtener_ip_cliente(request)

    assert error.value.status_code == 400

def test_ipv6_valida():
    request = crear_solicitud(
        IP_SERVIDOR,
        cabeceras_proxy(ip="2001:db8::1"),
    )

    assert confianza_proxy.obtener_ip_cliente(
        request
    ) == "2001:db8::1"

def test_ignorar_cabeceras_externas():
    request = crear_solicitud(
        "10.242.197.59",
        [
            ("x-forwarded-for", IP_CLIENTE),
            ("x-real-ip", IP_CLIENTE),
            ("cf-connecting-ip", IP_CLIENTE),
            ("forwarded", f"for={IP_CLIENTE}"),
        ],
    )

    assert confianza_proxy.obtener_ip_cliente(
        request
    ) == "10.242.197.59"

def test_clave_no_configurada(monkeypatch):
    monkeypatch.setattr(
        confianza_proxy,
        "CLAVE_INTERNA",
        "",
    )

    request = crear_solicitud(
        IP_SERVIDOR,
        cabeceras_proxy(),
    )

    with pytest.raises(HTTPException) as error:
        confianza_proxy.obtener_ip_cliente(request)

    assert error.value.status_code == 403
