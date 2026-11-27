from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import text

import app.database.usuarios as modulo_usuarios


pytestmark = [
    pytest.mark.integracion,
    pytest.mark.postgresql,
]


def generar_datos():
    identificador = uuid4().hex
    uid = f"prueba_{identificador}"

    return {
        "firebase_uid": uid,
        "correo": f"{uid}@example.invalid",
        "nombre": "Prueba",
        "apellido": "Concurrente",
        "cedula_profesional": str(uuid4().int)[:30],
        "especialidad": "Medicina general",
        "institucion_formacion": "Universidad de prueba",
    }


@pytest.fixture
def entorno_concurrente(
    engine_postgresql_pruebas,
    monkeypatch,
):
    engine = engine_postgresql_pruebas

    monkeypatch.setattr(
        modulo_usuarios,
        "engine",
        engine,
    )

    registros = {}

    def registrar_datos(datos):
        registros[datos["firebase_uid"]] = datos.copy()
        return datos

    try:
        yield engine, registrar_datos

    finally:
        with engine.begin() as conn:

            conn.execute(
                text("SET LOCAL lock_timeout = '5s'")
            )

            for datos in registros.values():

                uid = datos["firebase_uid"]
                correo = datos["correo"]

                conn.execute(
                    text("""
                        SELECT
                            pruebas_seguridad.limpiar_medico_prueba(
                                :uid,
                                :correo
                            )
                    """),
                    {
                        "uid": uid,
                        "correo": correo,
                    },
                )

            for uid in registros:

                restantes = conn.execute(
                    text("""
                        SELECT COUNT(*)
                        FROM public.usuarios
                        WHERE firebase_uid = :uid
                    """),
                    {"uid": uid},
                ).scalar_one()

                assert restantes == 0


def ejecutar_concurrentemente(datos_a, datos_b):

    barrera = Barrier(2, timeout=10)

    def ejecutar(datos):

        barrera.wait()

        try:
            resultado = (
                modulo_usuarios.crear_usuario_medico(
                    **datos
                )
            )

            return {
                "exito": True,
                "resultado": resultado,
            }

        except ValueError as error:

            return {
                "exito": False,
                "error": str(error),
            }

    with ThreadPoolExecutor(max_workers=2) as executor:

        futuro_a = executor.submit(ejecutar, datos_a)
        futuro_b = executor.submit(ejecutar, datos_b)

        return [
            futuro_a.result(timeout=30),
            futuro_b.result(timeout=30),
        ]


def contar_registros(engine, uids):

    with engine.connect() as conn:

        usuarios = conn.execute(
            text("""
                SELECT COUNT(*)
                FROM public.usuarios
                WHERE firebase_uid = ANY(:uids)
            """),
            {"uids": list(uids)},
        ).scalar_one()

        medicos = conn.execute(
            text("""
                SELECT COUNT(*)
                FROM public.medicos m
                JOIN public.usuarios u
                    ON u.id = m.usuario_id
                WHERE u.firebase_uid = ANY(:uids)
            """),
            {"uids": list(uids)},
        ).scalar_one()

    return usuarios, medicos


def test_mismo_uid_concurrente(entorno_concurrente):

    engine, registrar = entorno_concurrente

    datos = registrar(generar_datos())

    resultados = ejecutar_concurrentemente(
        datos.copy(),
        datos.copy(),
    )

    assert all(r["exito"] for r in resultados)

    primero = resultados[0]["resultado"]
    segundo = resultados[1]["resultado"]

    assert primero["usuario_id"] == segundo["usuario_id"]
    assert primero["medico_id"] == segundo["medico_id"]

    assert sorted([
        primero["existente"],
        segundo["existente"],
    ]) == [False, True]

    assert contar_registros(
        engine,
        [datos["firebase_uid"]],
    ) == (1, 1)


def test_mismo_correo_concurrente(entorno_concurrente):

    engine, registrar = entorno_concurrente

    datos_a = generar_datos()
    datos_b = generar_datos()

    datos_b["correo"] = datos_a["correo"]

    registrar(datos_a)
    registrar(datos_b)

    resultados = ejecutar_concurrentemente(
        datos_a,
        datos_b,
    )

    exitos = [r for r in resultados if r["exito"]]
    errores = [r for r in resultados if not r["exito"]]

    assert len(exitos) == 1
    assert len(errores) == 1
    assert "correo" in errores[0]["error"].lower()

    assert contar_registros(
        engine,
        [
            datos_a["firebase_uid"],
            datos_b["firebase_uid"],
        ],
    ) == (1, 1)


def test_misma_cedula_concurrente(entorno_concurrente):

    engine, registrar = entorno_concurrente

    datos_a = generar_datos()
    datos_b = generar_datos()

    datos_b["cedula_profesional"] = (
        datos_a["cedula_profesional"]
    )

    registrar(datos_a)
    registrar(datos_b)

    resultados = ejecutar_concurrentemente(
        datos_a,
        datos_b,
    )

    exitos = [r for r in resultados if r["exito"]]
    errores = [r for r in resultados if not r["exito"]]

    assert len(exitos) == 1
    assert len(errores) == 1
    assert "cedula" in errores[0]["error"].lower()

    assert contar_registros(
        engine,
        [
            datos_a["firebase_uid"],
            datos_b["firebase_uid"],
        ],
    ) == (1, 1)


def test_medicos_diferentes_concurrentes(
    entorno_concurrente,
):

    engine, registrar = entorno_concurrente

    datos_a = registrar(generar_datos())
    datos_b = registrar(generar_datos())

    resultados = ejecutar_concurrentemente(
        datos_a,
        datos_b,
    )

    assert all(r["exito"] for r in resultados)

    for resultado in resultados:
        assert resultado["resultado"]["existente"] is False

    assert contar_registros(
        engine,
        [
            datos_a["firebase_uid"],
            datos_b["firebase_uid"],
        ],
    ) == (2, 2)
