from contextlib import contextmanager
from threading import BoundedSemaphore

from fastapi import HTTPException, status


# Maximo de operaciones simultaneas por modelo
_semaforo_beto = BoundedSemaphore(value=1)
_semaforo_tensorflow = BoundedSemaphore(value=1)


@contextmanager
def controlar_beto():

    adquirido = _semaforo_beto.acquire(blocking=False)

    if not adquirido:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de medicamentos esta ocupado.",
            headers={"Retry-After": "5"},
        )

    try:
        yield

    finally:
        _semaforo_beto.release()


@contextmanager
def controlar_tensorflow():

    adquirido = _semaforo_tensorflow.acquire(blocking=False)

    if not adquirido:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de sintomas esta ocupado.",
            headers={"Retry-After": "5"},
        )

    try:
        yield

    finally:
        _semaforo_tensorflow.release()