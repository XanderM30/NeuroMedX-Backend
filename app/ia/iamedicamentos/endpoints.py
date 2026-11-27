from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import obtener_usuario_autenticado
from app.seguridad.politicas import limitar_medicamentos
from app.seguridad.concurrencia import controlar_beto
from modelos.BETO.detector_medicamentos import detectar_medicamentos


router = APIRouter(
    prefix="/ia/medicamentos",
    tags=["IA - Medicamentos"]
)


class SolicitudDeteccion(BaseModel):
    texto: str = Field(min_length=1, max_length=10000)
    umbral_confianza: float = Field(default=0.50, ge=0.0, le=1.0)


class MencionMedicamento(BaseModel):
    texto: str
    inicio: int
    fin: int
    confianza: float
    coincide_catalogo: bool
    medicamento_id: str | None = None
    medicamento: str | None = None
    evidencia: dict[str, Any] | None = None
    tipo_coincidencia: str | None = None
    estado_catalogo: str | None = None


class ResultadoDeteccion(BaseModel):
    texto: str
    menciones: list[MencionMedicamento]
    total_menciones: int
    umbral_confianza: float
    dispositivo: str


class RespuestaDeteccion(BaseModel):
    estado: str
    usuario_id: str
    resultado: ResultadoDeteccion


@router.post(
    "/detectar",
    response_model=RespuestaDeteccion,
    responses={
        400: {"description": "Solicitud no valida para el detector."},
        401: {"description": "Se requiere autenticacion valida."},
        403: {"description": "El usuario no tiene acceso al servicio."},
        429: {"description": "Limite de solicitudes superado."},
        503: {"description": "El servicio no esta disponible."}
    }
)
def detectar(
    solicitud: SolicitudDeteccion,
    usuario: dict = Depends(obtener_usuario_autenticado)
):
    # Limitar solicitudes por UID verificado
    limitar_medicamentos(usuario["firebase_uid"])

    # Controlar operaciones simultaneas
    with controlar_beto():

        try:
            resultado = detectar_medicamentos(
                texto=solicitud.texto,
                umbral_confianza=solicitud.umbral_confianza
            )

            return {
                "estado": "correcto",
                "usuario_id": str(usuario["id"]),
                "resultado": resultado
            }

        except (TypeError, ValueError) as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )

        except Exception:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="El servicio de deteccion de medicamentos no esta disponible."
            )