import pytest

from fastapi.testclient import TestClient

from app.main import app
from app.auth.dependencies import obtener_usuario_autenticado

from app.database import registro
from app.ia.iamedicamentos import endpoints as medicamentos
from app.ia.iasintomas import endpoints as sintomas
from app.ia.iasintomas.acceso import verificar_acceso_experimental

from app.seguridad import politicas, middleware
from app.seguridad.limitador import LimitadorSolicitudes


UID_A = "uid-prueba-a"
UID_B = "uid-prueba-b"


def crear_usuario(uid):

    return {
        "id": f"usuario-{uid}",
        "firebase_uid": uid,
        "correo": f"{uid}@neuromedx.test",
        "nombre": "Usuario",
        "apellido": "Prueba",
        "rol": "paciente",
        "estado": True,
    }


@pytest.fixture
def entorno(monkeypatch):

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

    identidad = {"uid": UID_A}

    def usuario_autenticado():
        return crear_usuario(identidad["uid"])

    anteriores = app.dependency_overrides.copy()

    app.dependency_overrides[
        obtener_usuario_autenticado
    ] = usuario_autenticado

    app.dependency_overrides[
        verificar_acceso_experimental
    ] = usuario_autenticado

    try:

        with TestClient(app) as cliente:
            yield cliente, identidad

    finally:

        app.dependency_overrides.clear()
        app.dependency_overrides.update(anteriores)


def comprobar_cuota(
    solicitud,
    identidad,
    limite,
    codigo_exitoso
):

    identidad["uid"] = UID_A

    for _ in range(limite):

        respuesta = solicitud()

        assert respuesta.status_code == codigo_exitoso, (
            respuesta.text
        )

    # Usuario A supera su cuota
    respuesta = solicitud()

    assert respuesta.status_code == 429
    assert "Retry-After" in respuesta.headers

    assert 1 <= int(
        respuesta.headers["Retry-After"]
    ) <= 60

    # Usuario B conserva su propia cuota
    identidad["uid"] = UID_B

    respuesta = solicitud()

    assert respuesta.status_code == codigo_exitoso

    # Usuario A permanece bloqueado
    identidad["uid"] = UID_A

    respuesta = solicitud()

    assert respuesta.status_code == 429


# ==========================================
# CUOTA HTTP DE BETO
# ==========================================

def test_cuota_http_medicamentos(
    entorno, monkeypatch
):

    cliente, identidad = entorno

    llamadas = []

    def detectar_simulado(texto, umbral_confianza):

        llamadas.append(texto)

        return {
            "texto": texto,
            "menciones": [],
            "total_menciones": 0,
            "umbral_confianza": umbral_confianza,
            "dispositivo": "cpu",
        }

    monkeypatch.setattr(
        medicamentos,
        "detectar_medicamentos",
        detectar_simulado
    )

    def solicitud():

        return cliente.post(
            "/ia/medicamentos/detectar",
            json={"texto": "Paracetamol"}
        )

    comprobar_cuota(
        solicitud,
        identidad,
        limite=20,
        codigo_exitoso=200
    )

    # Las solicitudes bloqueadas no ejecutan BETO
    assert len(llamadas) == 21


# ==========================================
# CUOTA HTTP DE TENSORFLOW
# ==========================================

def test_cuota_http_sintomas(
    entorno, monkeypatch
):

    cliente, identidad = entorno

    llamadas = []

    def analizar_simulado(texto):

        llamadas.append(texto)

        return {
            "estado": "correcto",
            "reconocimiento": {},
            "alarmas": {},
            "resultados": [],
            "umbral": 0.20,
            "validacion_clinica": False,
            "advertencia": "Resultado simulado",
            "aclaracion": None,
        }

    monkeypatch.setattr(
        sintomas,
        "analizar_sintomas",
        analizar_simulado
    )

    def solicitud():

        return cliente.post(
            "/ia/sintomas/analizar",
            json={"texto": "Fiebre y tos"}
        )

    comprobar_cuota(
        solicitud,
        identidad,
        limite=10,
        codigo_exitoso=200
    )

    # Las solicitudes bloqueadas no ejecutan TensorFlow
    assert len(llamadas) == 11


# ==========================================
# CUOTA HTTP DE REGISTRO
# ==========================================

def test_cuota_http_registro(
    entorno, monkeypatch
):

    cliente, identidad = entorno

    llamadas = []

    def verificar_token_simulado(token):

        uid = identidad["uid"]

        return {
            "uid": uid,
            "email": f"{uid}@neuromedx.test",
            "email_verified": True,
        }

    def crear_paciente_simulado(
        firebase_uid,
        correo,
        nombre,
        apellido
    ):

        llamadas.append(firebase_uid)

        return {
            "usuario_id": f"usuario-{firebase_uid}",
            "paciente_id": f"paciente-{firebase_uid}",
            "correo": correo,
            "rol": "paciente",
            "estado": True,
            "existente": False,
        }

    monkeypatch.setattr(
        registro,
        "verificar_token_firebase",
        verificar_token_simulado
    )

    monkeypatch.setattr(
        registro,
        "crear_usuario_paciente",
        crear_paciente_simulado
    )

    def solicitud():

        return cliente.post(
            "/usuarios/registro-paciente",
            headers={
                "Authorization": "Bearer token-simulado"
            },
            json={
                "nombre": "Usuario",
                "apellido": "Prueba",
            }
        )

    comprobar_cuota(
        solicitud,
        identidad,
        limite=5,
        codigo_exitoso=201
    )

    # Las solicitudes bloqueadas no crean pacientes
    assert len(llamadas) == 6


# ==========================================
# CUOTA HTTP DE PERFIL
# ==========================================

def test_cuota_http_perfil(entorno):

    cliente, identidad = entorno

    def solicitud():

        return cliente.get("/usuarios/me")

    comprobar_cuota(
        solicitud,
        identidad,
        limite=60,
        codigo_exitoso=200
    )


# ==========================================
# INDEPENDENCIA HTTP ENTRE SERVICIOS
# ==========================================

def test_independencia_http_servicios(
    entorno, monkeypatch
):

    cliente, identidad = entorno

    def detectar_simulado(texto, umbral_confianza):

        return {
            "texto": texto,
            "menciones": [],
            "total_menciones": 0,
            "umbral_confianza": umbral_confianza,
            "dispositivo": "cpu",
        }

    monkeypatch.setattr(
        medicamentos,
        "detectar_medicamentos",
        detectar_simulado
    )

    for _ in range(20):

        respuesta = cliente.post(
            "/ia/medicamentos/detectar",
            json={"texto": "Paracetamol"}
        )

        assert respuesta.status_code == 200

    respuesta = cliente.post(
        "/ia/medicamentos/detectar",
        json={"texto": "Paracetamol"}
    )

    assert respuesta.status_code == 429

    # El mismo usuario puede consultar su perfil
    respuesta = cliente.get("/usuarios/me")

    assert respuesta.status_code == 200

    # BETO permanece bloqueado
    respuesta = cliente.post(
        "/ia/medicamentos/detectar",
        json={"texto": "Paracetamol"}
    )

    assert respuesta.status_code == 429