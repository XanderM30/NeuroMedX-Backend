-- NeuroMedX Connect
-- Migracion: 001
-- Descripcion: Fortalecer restricciones de perfiles medicos
-- Fecha: 2026-11-27

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';

ALTER TABLE public.medicos

    ALTER COLUMN cedula_profesional SET NOT NULL,

    ALTER COLUMN especialidad SET NOT NULL,

    ALTER COLUMN institucion_formacion SET NOT NULL,

    ADD CONSTRAINT medicos_cedula_profesional_key
        UNIQUE (cedula_profesional),

    ADD CONSTRAINT medicos_cedula_formato_check
        CHECK (
            cedula_profesional ~ '^[0-9]{1,30}$'
        ),

    ADD CONSTRAINT medicos_especialidad_valida_check
        CHECK (
            CHAR_LENGTH(BTRIM(especialidad)) >= 2
        ),

    ADD CONSTRAINT medicos_institucion_valida_check
        CHECK (
            CHAR_LENGTH(BTRIM(institucion_formacion)) >= 2
        );

COMMIT;
