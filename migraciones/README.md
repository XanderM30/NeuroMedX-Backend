# Migraciones de PostgreSQL - NeuroMedX Connect

Esta carpeta contiene las modificaciones estructurales
de la base de datos neuromedx_connect.

## Reglas

1. Las migraciones deben estar numeradas consecutivamente.
2. Cada migracion debe estar versionada en Git.
3. Las migraciones deben probarse primero en desarrollo.
4. Antes de modificar produccion debe realizarse un respaldo.
5. Las modificaciones deben ejecutarse dentro de transacciones.
6. No deben incluir credenciales ni datos personales.
7. Una migracion aplicada no debe modificarse posteriormente.
8. Las migraciones no deben ejecutarse automaticamente
   durante el arranque del backend.

## Historial

| Version | Archivo | Descripcion |
|---------|---------|-------------|
| 001 | 001_restricciones_medicos.sql | Restricciones de datos profesionales y unicidad de cedula |
| 002 | 002_validacion_espacios_medicos.sql | Validacion robusta de espacios Unicode en datos profesionales |
