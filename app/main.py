from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Depends, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import text

from app.database.registro import (
    registrar_paciente_firebase,
    registrar_medico_firebase,
)

from app.esquemas.medicos import (
    RegistroMedico,
    RespuestaRegistroMedico,
)
from app.database.connection import engine
from app.auth.dependencies import obtener_usuario_autenticado
from app.auth.medicos import obtener_medico_autenticado
from app.esquemas.medicos import RespuestaPerfilMedico

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

# Registro de medicos mediante Firebase
@app.post(
    "/usuarios/registro-medico",
    status_code=status.HTTP_201_CREATED,
    response_model=RespuestaRegistroMedico,
    responses={
        200: {
            "model": RespuestaRegistroMedico,
            "description": "Medico registrado previamente",
        },
        401: {"description": "Autenticacion requerida"},
        403: {"description": "Acceso no autorizado"},
        409: {"description": "Conflicto de registro"},
        429: {"description": "Limite de solicitudes alcanzado"},
        503: {"description": "Servicio temporalmente no disponible"},
    },
)
def registrar_medico(
    solicitud: RegistroMedico,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_registro
    ),
):
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere autenticacion de Firebase",
            headers={"WWW-Authenticate": "Bearer"},
        )

    resultado = registrar_medico_firebase(
        token=credentials.credentials,
        nombre=solicitud.nombre,
        apellido=solicitud.apellido,
        cedula_profesional=solicitud.cedula_profesional,
        especialidad=solicitud.especialidad,
        institucion_formacion=solicitud.institucion_formacion,
    )

    if resultado["existente"]:
        response.status_code = status.HTTP_200_OK

    response.headers["Cache-Control"] = "no-store"

    return resultado

# Consulta del perfil medico autenticado
@app.get(
    "/medicos/me",
    response_model=RespuestaPerfilMedico,
    responses={
        401: {"description": "Autenticacion requerida"},
        403: {"description": "Acceso no autorizado"},
        429: {"description": "Limite de solicitudes alcanzado"},
        503: {"description": "Servicio temporalmente no disponible"},
    },
)
def obtener_perfil_medico(
    response: Response,
    perfil: dict = Depends(obtener_medico_autenticado),
):
    usuario = perfil["usuario"]
    medico = perfil["medico"]

    response.headers["Cache-Control"] = "no-store"

    return {
        "usuario": {
            "id": usuario["id"],
            "nombre": usuario["nombre"],
            "apellido": usuario["apellido"],
            "correo": usuario["correo"],
            "rol": usuario["rol"],
            "estado_cuenta": usuario["estado"],
        },
        "medico": {
            "id": medico["id"],
            "cedula_profesional": medico["cedula_profesional"],
            "especialidad": medico["especialidad"],
            "institucion_formacion": medico["institucion_formacion"],
            "estado_verificacion": medico["estado_verificacion"],
            "fecha_registro": medico["fecha_registro"],
        },
    }
