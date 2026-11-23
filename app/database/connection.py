
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

# Cargar las variables privadas del archivo .env
load_dotenv()

# Construir la URL de conexión de forma segura
database_url = URL.create(
    drivername="postgresql+psycopg",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME"),
)

# Crear el motor de conexión
engine = create_engine(
    database_url,
    pool_pre_ping=True,
    echo=False
)


def probar_conexion():
    with engine.connect() as connection:
        resultado = connection.execute(
            text("SELECT current_database(), current_user")
        )

        return resultado.fetchone()
