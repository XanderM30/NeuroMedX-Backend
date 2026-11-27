import json
import os
import subprocess
import sys


ORIGEN_PRODUCCION = "https://medicos.neuromedx.site"

ORIGENES_DESARROLLO = {
    "http://localhost:3000",
    "http://192.168.0.162:3000",
}


def obtener_configuracion(habilitado):

    entorno = os.environ.copy()

    entorno["CORS_DESARROLLO_HABILITADO"] = (
        "true" if habilitado else "false"
    )

    codigo = """
import json

from app.seguridad.proxy.configuracion import (
    CORS_DESARROLLO_HABILITADO,
    ORIGENES_CORS_PERMITIDOS,
)

print(json.dumps({
    "desarrollo": CORS_DESARROLLO_HABILITADO,
    "origenes": sorted(ORIGENES_CORS_PERMITIDOS),
}))
"""

    resultado = subprocess.run(
        [sys.executable, "-c", codigo],
        env=entorno,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )

    return json.loads(resultado.stdout.strip())


# ==========================================
# ENTORNO DE PRODUCCION
# ==========================================

def test_cors_produccion():

    configuracion = obtener_configuracion(False)

    origenes = set(configuracion["origenes"])

    assert configuracion["desarrollo"] is False

    assert origenes == {
        ORIGEN_PRODUCCION,
    }

    assert origenes.isdisjoint(
        ORIGENES_DESARROLLO
    )

    assert "*" not in origenes


# ==========================================
# ENTORNO DE DESARROLLO
# ==========================================

def test_cors_desarrollo():

    configuracion = obtener_configuracion(True)

    origenes = set(configuracion["origenes"])

    assert configuracion["desarrollo"] is True

    assert origenes == (
        {ORIGEN_PRODUCCION}
        | ORIGENES_DESARROLLO
    )

    assert len(origenes) == 3

    assert "*" not in origenes
