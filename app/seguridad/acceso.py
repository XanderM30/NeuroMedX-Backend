from fastapi import HTTPException, status

from app.seguridad.configuracion import (
    SALUD_BASE_DATOS_HABILITADA,
    PULSERA_MEDICIONES_HABILITADAS,
)


def verificar_acceso_salud_base_datos() -> None:
    if not SALUD_BASE_DATOS_HABILITADA:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurso no encontrado"
        )


def verificar_acceso_mediciones_pulsera() -> None:
    if not PULSERA_MEDICIONES_HABILITADAS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de mediciones temporalmente deshabilitado"
        )
