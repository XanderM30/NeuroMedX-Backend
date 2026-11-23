
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(
    prefix="/pulsera",
    tags=["Pulsera inteligente"]
)


class MedicionPulsera(BaseModel):
    dispositivo: str = "NeuroMedX Connect"

    # MAX30102
    sensor_max30102: bool = False
    pulso_valido: bool = False

    frecuencia_cardiaca: int | None = Field(
        default=None, ge=30, le=220
    )

    spo2: int | None = Field(
        default=None, ge=70, le=100
    )

    ir: int | None = None
    rojo: int | None = None

    # MAX30205
    temperatura: float | None = None

    # MPU6050
    aceleracion_x: float | None = None
    aceleracion_y: float | None = None
    aceleracion_z: float | None = None

    giro_x: float | None = None
    giro_y: float | None = None
    giro_z: float | None = None


# Almacenamiento temporal en memoria
mediciones: list[dict] = []


@router.get("/")
def inicio():
    return {
        "proyecto": "NeuroMedX Connect",
        "estado": "API de pulsera funcionando",
        "version": "1.1.0",
        "documentacion": "/docs",
        "ultima_medicion": "/pulsera/mediciones/ultima",
    }


@router.get("/health")
def salud():
    return {"estado": "activo"}


@router.post("/mediciones")
def recibir_medicion(datos: MedicionPulsera):
    registro = datos.model_dump()

    registro["fecha_recepcion"] = datetime.now(
        timezone.utc
    ).isoformat()

    mediciones.append(registro)

    if len(mediciones) > 1000:
        del mediciones[:-1000]

    print("\n========== NUEVA MEDICION ==========")
    print("Dispositivo:", registro["dispositivo"])
    print("MAX30102 conectado:", registro["sensor_max30102"])
    print("Lectura válida:", registro["pulso_valido"])
    print("Frecuencia cardiaca:", registro["frecuencia_cardiaca"])
    print("SpO2:", registro["spo2"])
    print("IR:", registro["ir"])
    print("Rojo:", registro["rojo"])
    print("Temperatura:", registro["temperatura"])
    print("====================================\n")

    return {
        "mensaje": "Medicion recibida correctamente",
        "medicion": registro,
    }


@router.get("/mediciones")
def consultar_mediciones():
    return {
        "total": len(mediciones),
        "mediciones": mediciones,
    }


@router.get("/mediciones/ultima")
def consultar_ultima_medicion():
    if not mediciones:
        return {
            "mensaje": "Todavia no hay mediciones disponibles",
            "medicion": None,
        }

    return {"medicion": mediciones[-1]}
