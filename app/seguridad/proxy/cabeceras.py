from ipaddress import ip_address

CABECERAS_PERMITIDAS = frozenset({
    "authorization",
    "content-type",
    "accept",
})

def validar_ip_cliente(valor: str) -> str:
    if not valor:
        raise ValueError("Direccion IP del cliente ausente.")

    valor = valor.strip()

    if "," in valor or "%" in valor:
        raise ValueError("Direccion IP del cliente invalida.")

    try:
        return str(ip_address(valor))
    except ValueError:
        raise ValueError(
            "Direccion IP del cliente invalida."
        ) from None

def obtener_ip_cloudflare(cabeceras) -> str:
    valores = cabeceras.getlist("cf-connecting-ip")

    if len(valores) != 1:
        raise ValueError(
            "Cabecera de Cloudflare ausente o duplicada."
        )

    return validar_ip_cliente(valores[0])

def preparar_cabeceras(cabeceras) -> dict[str, str]:
    resultado = {}

    for nombre in CABECERAS_PERMITIDAS:
        valores = cabeceras.getlist(nombre)

        if len(valores) > 1:
            raise ValueError(
                f"Cabecera duplicada: {nombre}."
            )

        if valores:
            resultado[nombre] = valores[0]

    return resultado
