from app.seguridad.limitador import LimitadorSolicitudes

from app.seguridad.proxy.configuracion import (
    LIMITE_PREFLIGHT_IP,
    VENTANA_PREFLIGHT,
)


limitador_proxy = LimitadorSolicitudes(
    max_claves=10000
)


def limitar_preflight(ip_cliente: str) -> None:
    limitador_proxy.verificar(
        clave=f"preflight:{ip_cliente}",
        limite=LIMITE_PREFLIGHT_IP,
        ventana=VENTANA_PREFLIGHT,
    )
