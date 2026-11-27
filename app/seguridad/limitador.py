from collections import deque
from threading import Lock
from time import monotonic
from math import ceil

from fastapi import HTTPException, status


class LimitadorSolicitudes:

    def __init__(self, max_claves: int = 10000):
        self._registros = {}
        self._bloqueo = Lock()
        self._max_claves = max_claves

    def verificar(
        self,
        clave: str,
        limite: int,
        ventana: int = 60
    ) -> None:

        if limite <= 0 or ventana <= 0:
            raise ValueError("Limite o ventana no validos")

        with self._bloqueo:
            ahora = monotonic()

            # Eliminar registros expirados
            expirados = [
                identificador
                for identificador, registro
                in self._registros.items()
                if registro["expiracion"] <= ahora
            ]

            for identificador in expirados:
                del self._registros[identificador]

            if clave not in self._registros:

                if len(self._registros) >= self._max_claves:
                    raise HTTPException(
                        status_code=503,
                        detail="Servicio temporalmente saturado",
                        headers={"Retry-After": "60"}
                    )

                self._registros[clave] = {
                    "solicitudes": deque(),
                    "expiracion": ahora + ventana
                }

            registro = self._registros[clave]
            solicitudes = registro["solicitudes"]

            while solicitudes and solicitudes[0] <= ahora - ventana:
                solicitudes.popleft()

            if len(solicitudes) >= limite:
                espera = max(
                    1,
                    ceil(solicitudes[0] + ventana - ahora)
                )

                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Demasiadas solicitudes. Intenta nuevamente.",
                    headers={"Retry-After": str(espera)}
                )

            solicitudes.append(ahora)
            registro["expiracion"] = ahora + ventana


limitador = LimitadorSolicitudes()