-- NeuroMedX Connect
-- Privilegios del entorno de pruebas.
-- Ejecutar despues de importar el esquema actualizado.

\set ON_ERROR_STOP on

BEGIN;

SET LOCAL lock_timeout = '5s';

DO $$
BEGIN
    IF current_database() <> 'neuromedx_connect_test'
       OR current_user <> 'postgres'
    THEN
        RAISE EXCEPTION 'Entorno no autorizado';
    END IF;
END;
$$;

REVOKE ALL ON SCHEMA public FROM PUBLIC;

GRANT USAGE ON SCHEMA public TO neuromedx_test;

GRANT SELECT, INSERT
ON public.usuarios, public.medicos
TO neuromedx_test;

CREATE ROLE neuromedx_test_cleanup
    NOLOGIN
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT
    NOREPLICATION
    NOBYPASSRLS;

CREATE SCHEMA pruebas_seguridad
    AUTHORIZATION neuromedx_test_cleanup;

REVOKE ALL ON SCHEMA pruebas_seguridad FROM PUBLIC;

GRANT USAGE ON SCHEMA pruebas_seguridad
TO neuromedx_test;

GRANT USAGE ON SCHEMA public
TO neuromedx_test_cleanup;

GRANT SELECT, DELETE
ON public.usuarios, public.medicos
TO neuromedx_test_cleanup;

GRANT SELECT ON
    public.pacientes,
    public.archivos,
    public.auditoria,
    public.mensajes,
    public.notificaciones,
    public.videollamadas,
    public.relaciones_medico_paciente,
    public.reportes
TO neuromedx_test_cleanup;

COMMIT;
