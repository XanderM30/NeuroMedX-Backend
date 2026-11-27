from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.seguridad.politicas import limitar_sintomas
from app.seguridad.concurrencia import controlar_tensorflow
from app.ia.iasintomas.acceso import verificar_acceso_experimental
from app.ia.iasintomas.inferencia import (
    analizar_sintomas,
    cargar_recursos,
)


router = APIRouter(
    prefix="/ia/sintomas",
    tags=["IA - Sintomas"],
)


class SolicitudAnalisis(BaseModel):
    texto: str = Field(min_length=1, max_length=2000)


class EnfermedadSugerida(BaseModel):
    enfermedad: str
    puntuacion_modelo: float = Field(ge=0.0, le=1.0)


class ResultadoAnalisis(BaseModel):
    estado: str
    reconocimiento: dict[str, Any] | None
    alarmas: dict[str, Any]
    resultados: list[EnfermedadSugerida]
    umbral: float | None
    validacion_clinica: bool
    advertencia: str
    aclaracion: dict[str, Any] | None = None


class RespuestaAnalisis(BaseModel):
    estado: str
    usuario_id: str
    resultado: ResultadoAnalisis


@router.get("/health")
def comprobar_salud(
    usuario: dict = Depends(verificar_acceso_experimental),
):
    limitar_sintomas(usuario["firebase_uid"])

    with controlar_tensorflow():
        try:
            recursos = cargar_recursos()

            return {
                "servicio": "IA de sintomas",
                "estado": "operativo",
                "framework": "TensorFlow",
                "arquitectura": "MLP",
                "manifestaciones": len(
                    recursos["catalogo"]["manifestaciones"]
                ),
                "enfermedades": len(
                    recursos["configuracion"]["enfermedades"]
                ),
                "combinaciones": len(
                    recursos["combinaciones_conocidas"]
                ),
                "catalogo_congelado": True,
                "validacion_clinica": False,
            }

        except Exception:
            raise HTTPException(
                status_code=503,
                detail="El servicio de sintomas no esta disponible.",
            )


@router.get("/catalogo")
def obtener_catalogo(
    usuario: dict = Depends(verificar_acceso_experimental),
):
    limitar_sintomas(usuario["firebase_uid"])

    with controlar_tensorflow():
        try:
            recursos = cargar_recursos()

            manifestaciones = [
                {
                    "id": item["id"],
                    "nombre": item["canonico"],
                }
                for item in recursos["catalogo"]["manifestaciones"]
            ]

            return {
                "estado": "correcto",
                "version": recursos["configuracion"][
                    "catalogo_congelado"
                ]["version"],
                "total_manifestaciones": len(manifestaciones),
                "manifestaciones": manifestaciones,
                "validacion_clinica": False,
            }

        except Exception:
            raise HTTPException(
                status_code=503,
                detail="El catalogo no esta disponible.",
            )


@router.post(
    "/analizar",
    response_model=RespuestaAnalisis,
    responses={
        401: {"description": "Autenticacion requerida."},
        403: {"description": "Usuario no autorizado."},
        429: {"description": "Limite de solicitudes superado."},
        503: {"description": "Servicio no disponible."},
    },
)
def analizar(
    solicitud: SolicitudAnalisis,
    usuario: dict = Depends(verificar_acceso_experimental),
):
    limitar_sintomas(usuario["firebase_uid"])

    texto = solicitud.texto.strip()

    if not texto:
        raise HTTPException(
            status_code=422,
            detail="El texto no puede estar vacio.",
        )

    with controlar_tensorflow():
        try:
            resultado = analizar_sintomas(texto)

            return {
                "estado": "correcto",
                "usuario_id": str(usuario["id"]),
                "resultado": resultado,
            }

        except Exception:
            raise HTTPException(
                status_code=503,
                detail="El servicio de analisis no esta disponible.",
            )