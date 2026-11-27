import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.pool import NullPool


@pytest.fixture(scope="session")
def engine_postgresql_pruebas():

    if os.getenv("NEUROMEDX_PRUEBAS_POSTGRESQL") != "1":
        pytest.skip(
            "Pruebas PostgreSQL no habilitadas"
        )

    password = os.getenv("NEUROMEDX_TEST_DB_PASSWORD")

    if not password:
        pytest.fail(
            "Falta la variable NEUROMEDX_TEST_DB_PASSWORD"
        )

    url = URL.create(
        drivername="postgresql+psycopg",
        username="neuromedx_test",
        password=password,
        host="127.0.0.1",
        port=5432,
        database="neuromedx_connect_test",
    )

    engine = create_engine(
        url,
        poolclass=NullPool,
        connect_args={
            "connect_timeout": 5,
        },
        hide_parameters=True,
    )

    try:
        with engine.connect() as conn:

            identidad = conn.execute(text("""
                SELECT
                    current_database() AS base_datos,
                    current_user AS usuario,
                    host(inet_server_addr()) AS servidor
            """)).mappings().one()

            if (
                identidad["base_datos"]
                != "neuromedx_connect_test"
                or identidad["usuario"]
                != "neuromedx_test"
                or identidad["servidor"]
                != "127.0.0.1"
            ):
                pytest.fail(
                    "Conexion de pruebas no autorizada"
                )

        yield engine

    finally:
        engine.dispose()


@pytest.fixture
def conexion_postgresql_pruebas(
    engine_postgresql_pruebas,
):
    with engine_postgresql_pruebas.connect() as conn:

        transaccion = conn.begin()

        try:
            yield conn

        finally:
            if transaccion.is_active:
                transaccion.rollback()
