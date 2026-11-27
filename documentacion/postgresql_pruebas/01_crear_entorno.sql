-- NeuroMedX Connect
-- Instalacion inicial del entorno PostgreSQL de pruebas.
-- Ejecutar exclusivamente en una instancia de desarrollo.
-- Requiere una sesion administrativa mediante psql.

\set ON_ERROR_STOP on

DO $$
BEGIN
    IF current_database() <> 'postgres'
       OR current_user <> 'postgres'
    THEN
        RAISE EXCEPTION 'Conexion administrativa incorrecta';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_roles
        WHERE rolname = 'neuromedx_test'
    ) THEN
        RAISE EXCEPTION 'El usuario de pruebas ya existe';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_database
        WHERE datname = 'neuromedx_connect_test'
    ) THEN
        RAISE EXCEPTION 'La base de pruebas ya existe';
    END IF;
END;
$$;

SET password_encryption = 'scram-sha-256';

CREATE ROLE neuromedx_test
    LOGIN
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT
    NOREPLICATION
    NOBYPASSRLS
    CONNECTION LIMIT 5;

\password neuromedx_test

CREATE DATABASE neuromedx_connect_test
    OWNER postgres
    CONNECTION LIMIT 10
    TEMPLATE template0;

REVOKE ALL
    ON DATABASE neuromedx_connect_test
    FROM PUBLIC;

GRANT CONNECT
    ON DATABASE neuromedx_connect_test
    TO neuromedx_test;

\connect neuromedx_connect_test postgres

REVOKE ALL ON SCHEMA public FROM PUBLIC;

GRANT USAGE ON SCHEMA public TO neuromedx_test;

-- Importar posteriormente el esquema actualizado
-- utilizando pg_dump --schema-only y --no-privileges.
-- No importar registros reales.
-- Configurar los permisos sobre las tablas despues
-- de restaurar el esquema.
-- Aplicar las reglas de aislamiento de pg_hba.conf
-- antes de habilitar conexiones del usuario de pruebas.

SELECT
    current_database() AS base_datos,
    current_user AS usuario_administrador;
