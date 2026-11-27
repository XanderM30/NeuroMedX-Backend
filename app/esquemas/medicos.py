from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


ESPACIOS_NORMALIZACION = (
    "\u0009\u000A\u000B\u000C\u000D"
    "\u0020\u0085\u00A0\u1680"
    "\u2000\u2001\u2002\u2003\u2004"
    "\u2005\u2006\u2007\u2008\u2009"
    "\u200A\u2028\u2029\u202F"
    "\u205F\u3000\uFEFF"
)


class RegistroMedico(BaseModel):
    """
    Datos permitidos para el registro de un medico.
    La identidad y el rol se determinan en el backend.
    """

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    nombre: str = Field(
        min_length=2,
        max_length=100,
    )

    apellido: str = Field(
        min_length=2,
        max_length=100,
    )

    cedula_profesional: str = Field(
        min_length=1,
        max_length=30,
        pattern=r"^[0-9]+$",
    )

    especialidad: str = Field(
        min_length=2,
        max_length=150,
    )

    institucion_formacion: str = Field(
        min_length=2,
        max_length=200,
    )

    @field_validator(
        "nombre",
        "apellido",
        "cedula_profesional",
        mode="before",
    )
    @classmethod
    def normalizar_datos_personales(cls, valor):
        if isinstance(valor, str):
            return valor.strip()

        return valor

    @field_validator(
        "especialidad",
        "institucion_formacion",
        mode="before",
    )
    @classmethod
    def normalizar_datos_profesionales(cls, valor):
        if isinstance(valor, str):
            return valor.strip(
                ESPACIOS_NORMALIZACION
            )

        return valor


class RespuestaRegistroMedico(BaseModel):
    """
    Informacion autorizada para devolver al cliente.
    """

    estado: Literal["correcto"]

    mensaje: str

    usuario_id: UUID

    medico_id: UUID

    rol: Literal["medico"]

    estado_cuenta: bool

    estado_verificacion: Literal[
        "pendiente",
        "verificado",
        "rechazado",
    ]

    existente: bool

class UsuarioPerfilMedico(BaseModel):
    """
    Datos personales del medico autenticado.
    """

    id: UUID
    nombre: str
    apellido: str
    correo: str
    rol: Literal["medico"]
    estado_cuenta: bool


class PerfilProfesionalMedico(BaseModel):
    """
    Informacion profesional del medico autenticado.
    """

    id: UUID
    cedula_profesional: str
    especialidad: str
    institucion_formacion: str

    estado_verificacion: Literal[
        "pendiente",
        "verificado",
        "rechazado",
    ]

    fecha_registro: datetime


class RespuestaPerfilMedico(BaseModel):
    """
    Respuesta autorizada del perfil medico.
    """

    usuario: UsuarioPerfilMedico
    medico: PerfilProfesionalMedico
