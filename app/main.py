from pydantic import BaseModel, Field
from fastapi import Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database.registro import registrar_paciente_firebase
from app.auth.dependencies import obtener_usuario_autenticado
from fastapi import Depends
from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from app.routers import pulsera
from app.ia.iamedicamentos import endpoints as ia_medicamentos
from app.ia.iasintomas import endpoints as ia_sintomas
from app.database.connection import engine

bearer_registro = HTTPBearer(auto_error=False)


class RegistroPaciente(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    apellido: str = Field(min_length=1, max_length=100)

app = FastAPI(
    title="NeuroMedX Connect API",
    description="API principal de NeuroMedX Connect",
    version="1.0.0"
)
app.include_router(pulsera.router)
app.include_router(ia_medicamentos.router)
app.include_router(ia_sintomas.router)


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
@app.post(
    "/usuarios/registro-paciente",
    status_code=status.HTTP_201_CREATED
)
def registrar_paciente(
    solicitud: RegistroPaciente,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_registro)
):
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere autenticación de Firebase"
        )

    nombre = solicitud.nombre.strip()
    apellido = solicitud.apellido.strip()

    if not nombre or not apellido:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El nombre y apellido son obligatorios"
        )

    resultado = registrar_paciente_firebase(
        token=credentials.credentials,
        nombre=nombre,
        apellido=apellido
    )

    if resultado.get("existente"):
        response.status_code = status.HTTP_200_OK

    return resultado
