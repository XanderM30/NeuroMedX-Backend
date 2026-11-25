from fastapi.testclient import TestClient

from app.main import app
from app.auth.dependencies import obtener_usuario_autenticado
from app.ia.iamedicamentos import endpoints


def usuario_prueba():
    return {
        "id": "usuario_prueba",
        "correo": "prueba@neuromedx.test",
        "nombre": "Usuario",
        "apellido": "Prueba",
        "rol": "paciente",
        "estado": True,
    }


def resultado_prueba(texto, umbral_confianza):
    return {
        "texto": texto,
        "menciones": [
            {
                "texto": "paracetamol",
                "inicio": 0,
                "fin": 11,
                "confianza": 0.99,
                "coincide_catalogo": True,
                "medicamento_id": "MED_019",
                "medicamento": "Paracetamol",
                "evidencia": None,
                "tipo_coincidencia": "nombre_canonico",
                "estado_catalogo": None,
            }
        ],
        "total_menciones": 1,
        "umbral_confianza": umbral_confianza,
        "dispositivo": "cpu",
    }


def test_sin_autenticacion_retorna_401():
    cliente = TestClient(app)
    respuesta = cliente.post(
        "/ia/medicamentos/detectar",
        json={"texto": "El paciente toma paracetamol."},
    )
    assert respuesta.status_code == 401


def test_deteccion_exitosa(monkeypatch):
    app.dependency_overrides[obtener_usuario_autenticado] = usuario_prueba
    monkeypatch.setattr(
        endpoints,
        "detectar_medicamentos",
        resultado_prueba,
    )

    try:
        cliente = TestClient(app)
        respuesta = cliente.post(
            "/ia/medicamentos/detectar",
            json={
                "texto": "paracetamol",
                "umbral_confianza": 0.50,
            },
        )

        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert datos["estado"] == "correcto"
        assert datos["usuario_id"] == "usuario_prueba"
        assert datos["resultado"]["total_menciones"] == 1
        assert datos["resultado"]["menciones"][0]["medicamento_id"] == "MED_019"
    finally:
        app.dependency_overrides.clear()


def test_texto_vacio_retorna_422():
    app.dependency_overrides[obtener_usuario_autenticado] = usuario_prueba
    try:
        respuesta = TestClient(app).post(
            "/ia/medicamentos/detectar",
            json={"texto": ""},
        )
        assert respuesta.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_texto_demasiado_largo_retorna_422():
    app.dependency_overrides[obtener_usuario_autenticado] = usuario_prueba
    try:
        respuesta = TestClient(app).post(
            "/ia/medicamentos/detectar",
            json={"texto": "a" * 10001},
        )
        assert respuesta.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_umbral_fuera_de_rango_retorna_422():
    app.dependency_overrides[obtener_usuario_autenticado] = usuario_prueba
    try:
        respuesta = TestClient(app).post(
            "/ia/medicamentos/detectar",
            json={"texto": "paracetamol", "umbral_confianza": 1.5},
        )
        assert respuesta.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_texto_obligatorio():
    app.dependency_overrides[obtener_usuario_autenticado] = usuario_prueba
    try:
        respuesta = TestClient(app).post(
            "/ia/medicamentos/detectar",
            json={"umbral_confianza": 0.5},
        )
        assert respuesta.status_code == 422
    finally:
        app.dependency_overrides.clear()
