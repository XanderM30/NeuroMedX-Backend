from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import obtener_usuario_autenticado
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
        400: {"description": "Solicitud no v?lida para el detector."},
        401: {"description": "Se requiere autenticaci?n v?lida."},
        403: {"description": "El usuario no tiene acceso al servicio."},
        503: {"description": "El servicio de detecci?n o la base de datos no est?n disponibles."}
    }
)
def detectar(
    solicitud: SolicitudDeteccion,
    usuario: dict = Depends(obtener_usuario_autenticado)
):
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
            detail="El servicio de detecci?n de medicamentos no est? disponible."
        )
