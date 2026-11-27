-- NeuroMedX Connect
-- Migracion: 002
-- Descripcion: Validacion robusta de espacios Unicode
-- Fecha: 2026-11-27

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';

ALTER TABLE public.medicos

    DROP CONSTRAINT medicos_especialidad_valida_check,

    DROP CONSTRAINT medicos_institucion_valida_check,

    ADD CONSTRAINT medicos_especialidad_valida_check
        CHECK (
            CHAR_LENGTH(
                BTRIM(
                    especialidad,
                    U&'\0009\000A\000B\000C\000D\0020\0085\00A0\1680\2000\2001\2002\2003\2004\2005\2006\2007\2008\2009\200A\2028\2029\202F\205F\3000\FEFF'
                )
            ) >= 2
        ),

    ADD CONSTRAINT medicos_institucion_valida_check
        CHECK (
            CHAR_LENGTH(
                BTRIM(
                    institucion_formacion,
                    U&'\0009\000A\000B\000C\000D\0020\0085\00A0\1680\2000\2001\2002\2003\2004\2005\2006\2007\2008\2009\200A\2028\2029\202F\205F\3000\FEFF'
                )
            ) >= 2
        );

COMMIT;