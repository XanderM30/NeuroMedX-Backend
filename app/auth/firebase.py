
import os
import firebase_admin

from dotenv import load_dotenv
from firebase_admin import credentials

# Cargar variables del archivo .env
load_dotenv()

# Obtener la ruta de las credenciales
FIREBASE_CREDENTIALS_PATH = os.getenv(
    "FIREBASE_CREDENTIALS_PATH"
)

if not FIREBASE_CREDENTIALS_PATH:
    raise RuntimeError(
        "No se configuró FIREBASE_CREDENTIALS_PATH"
    )

if not os.path.isfile(FIREBASE_CREDENTIALS_PATH):
    raise FileNotFoundError(
        "No se encontró el archivo de credenciales de Firebase"
    )

# Inicializar Firebase Admin una sola vez
if not firebase_admin._apps:
    cred = credentials.Certificate(
        FIREBASE_CREDENTIALS_PATH
    )

    firebase_admin.initialize_app(cred)


def obtener_firebase_app():
    return firebase_admin.get_app()


from firebase_admin import auth
from fastapi import HTTPException, status


def verificar_token_firebase(token: str) -> dict:
    try:
        return auth.verify_id_token(
            token,
            check_revoked=True
        )

    except auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de autenticación ha expirado"
        )

    except auth.RevokedIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de autenticación ha sido revocado"
        )

    except auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de autenticación no es válido"
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No fue posible verificar la autenticación"
        )

