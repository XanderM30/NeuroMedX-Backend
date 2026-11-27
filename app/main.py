from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Depends, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import text

from app.database.registro import registrar_paciente_firebase
from app.database.connection import engine
from app.auth.dependencies import obtener_usuario_autenticado

from app.routers import pulsera
from app.ia.iamedicamentos import endpoints as ia_medicamentos
from app.ia.iasintomas import endpoints as ia_sintomas

from app.seguridad.configuracion import DOCUMENTACION_HABILITADA
from app.seguridad.acceso import verificar_acceso_salud_base_datos
from app.seguridad.politicas import limitar_perfil
from app.seguridad.middleware import proteger_solicitudes
from app.seguridad.tamano_solicitudes import LimitarTamanoSolicitudes


bearer_registro = HTTPBearer(auto_error=False)


class RegistroPaciente(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    apellido: str = Field(min_length=1, max_length=100)


# Configuracion principal de FastAPI
app = FastAPI(
    title="NeuroMedX Connect API",
    description="API principal de NeuroMedX Connect",
    version="1.0.0",
    docs_url="/docs" if DOCUMENTACION_HABILITADA else None,
    redoc_url="/redoc" if DOCUMENTACION_HABILITADA else None,
    openapi_url="/openapi.json" if DOCUMENTACION_HABILITADA else None
)


# Restriccion del tamano de solicitudes HTTP
app.add_middleware(LimitarTamanoSolicitudes)

# Middleware general de seguridad
app.middleware("http")(proteger_solicitudes)


# Registro de modulos
app.include_router(pulsera.router)
app.include_router(ia_medicamentos.router)
app.include_router(ia_sintomas.router)


# Endpoint publico principal
@app.get("/")
def inicio():
    return {
        "proyecto": "NeuroMedX Connect",
        "mensaje": "API funcionando correctamente",
        "estado": "activo"
    }


# Estado general de la API
@app.get("/salud")
def comprobar_salud():
    return {
        "api": "NeuroMedX Connect",
        "estado": "operativo"
    }


# Estado interno de PostgreSQL
@app.get(
    "/salud/base-datos",
    dependencies=[Depends(verificar_acceso_salud_base_datos)]
)
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


# Consulta del perfil autenticado
@app.get("/usuarios/me")
def obtener_perfil(
    usuario: dict = Depends(obtener_usuario_autenticado)
):
    limitar_perfil(usuario["firebase_uid"])

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


# Registro de pacientes mediante Firebase
@app.post(
    "/usuarios/registro-paciente",
    status_code=status.HTTP_201_CREATED
)
def registrar_paciente(
    solicitud: RegistroPaciente,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_registro
    )
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