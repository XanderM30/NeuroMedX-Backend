-- NeuroMedX Connect
-- Funcion restringida de limpieza.
-- Exclusivamente para la base de datos de pruebas.

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

CREATE FUNCTION pruebas_seguridad.limpiar_medico_prueba(
    p_uid TEXT,
    p_correo TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    v_usuario_id UUID;
    v_medico_id UUID;
BEGIN

    IF current_database() <> 'neuromedx_connect_test' THEN
        RAISE EXCEPTION 'Base de datos no autorizada';
    END IF;

    IF session_user <> 'neuromedx_test' THEN
        RAISE EXCEPTION 'Usuario no autorizado';
    END IF;

    IF p_uid IS NULL
       OR p_correo IS NULL
       OR p_uid !~ '^prueba_[0-9a-f]{32}$'
       OR p_correo !~ '^prueba_[0-9a-f]{32}@example[.]invalid$'
    THEN
        RAISE EXCEPTION 'Identificadores de prueba invalidos';
    END IF;

    LOCK TABLE public.usuarios, public.medicos
        IN SHARE ROW EXCLUSIVE MODE;

    SELECT id
    INTO v_usuario_id
    FROM public.usuarios
    WHERE firebase_uid = p_uid
      AND correo = p_correo
      AND rol = 'medico';

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    SELECT id
    INTO v_medico_id
    FROM public.medicos
    WHERE usuario_id = v_usuario_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Perfil medico incompleto';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.pacientes
        WHERE usuario_id = v_usuario_id
    ) OR EXISTS (
        SELECT 1 FROM public.archivos
        WHERE usuario_id = v_usuario_id
    ) OR EXISTS (
        SELECT 1 FROM public.auditoria
        WHERE usuario_id = v_usuario_id
    ) OR EXISTS (
        SELECT 1 FROM public.mensajes
        WHERE remitente_id = v_usuario_id
    ) OR EXISTS (
        SELECT 1 FROM public.notificaciones
        WHERE usuario_id = v_usuario_id
    ) OR EXISTS (
        SELECT 1 FROM public.videollamadas
        WHERE iniciada_por = v_usuario_id
    ) OR EXISTS (
        SELECT 1 FROM public.relaciones_medico_paciente
        WHERE medico_id = v_medico_id
    ) OR EXISTS (
        SELECT 1 FROM public.reportes
        WHERE medico_id = v_medico_id
    ) THEN
        RAISE EXCEPTION 'El registro tiene datos relacionados';
    END IF;

    DELETE FROM public.medicos
    WHERE id = v_medico_id;

    DELETE FROM public.usuarios
    WHERE id = v_usuario_id;

    RETURN TRUE;

END;
$$;

ALTER FUNCTION
    pruebas_seguridad.limpiar_medico_prueba(TEXT, TEXT)
OWNER TO neuromedx_test_cleanup;

REVOKE ALL ON FUNCTION
    pruebas_seguridad.limpiar_medico_prueba(TEXT, TEXT)
FROM PUBLIC;

GRANT EXECUTE ON FUNCTION
    pruebas_seguridad.limpiar_medico_prueba(TEXT, TEXT)
TO neuromedx_test;

COMMIT;
