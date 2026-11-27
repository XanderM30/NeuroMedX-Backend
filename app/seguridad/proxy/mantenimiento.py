from pathlib import Path
import stat


def servicio_habilitado(ruta: Path) -> bool:
    try:
        informacion = ruta.stat()

        return stat.S_ISREG(informacion.st_mode)

    except OSError:
        return False
