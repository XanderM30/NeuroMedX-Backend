from app.auth.dependencies import obtener_usuario_autenticado
from fastapi import Depends
from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from app.routers import pulsera
from app.ia.iamedicamentos import endpoints as ia_medicamentos
from app.database.connection import engine

app = FastAPI(
    title="NeuroMedX Connect API",
    description="API principal de NeuroMedX Connect",
    version="1.0.0"
)
app.include_router(pulsera.router)
app.include_router(ia_medicamentos.router)


@app.get("/")
def inicio():
    return {
        "proyecto": "NeuroMedX Connect",
        "mensaje": "API funcionando correctamente",
        "estado": "activo"
    }


@app.get("/salud")
def comprobar_salud():
    return {
        "api": "NeuroMedX Connect",
        "estado": "operativo"
    }


@app.get("/salud/base-datos")
def comprobar_base_datos():
    try:
        with engine.connect() as connection:
            resultado = connection.execute(
                text("SELECT current_database()")
            )
            nombre = resultado.scalar()

        return {
            "base_datos": nombre,
            "estado": "conectada"
        }

    except Exception:
        raise HTTPException(
            status_code=503,
            detail="No fue posible conectar con PostgreSQL"
        )
@app.get("/usuarios/me")
def obtener_perfil(
    usuario: dict = Depends(obtener_usuario_autenticado)
):
    return {
        "mensaje": "Autenticación correcta",
        "usuario": {
            "id": str(usuario["id"]),
            "correo": usuario["correo"],
            "nombre": usuario["nombre"],
            "apellido": usuario["apellido"],
            "rol": usuario["rol"]
        }
    }
