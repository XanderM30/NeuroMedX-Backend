# Entorno de pruebas PostgreSQL - NeuroMedX Connect

## Objetivo

Proporcionar un entorno aislado para ejecutar pruebas
automatizadas de integracion con PostgreSQL sin modificar
la base de datos de desarrollo o produccion.

## Configuracion del entorno

- PostgreSQL: 18
- Host: 127.0.0.1
- Puerto: 5432
- Base de datos: neuromedx_connect_test
- Usuario: neuromedx_test
- Limite de conexiones del usuario: 5
- Limite de conexiones de la base: 10
- Nivel de aislamiento verificado: READ COMMITTED
- Autenticacion: SCRAM-SHA-256

## Preparacion

1. Crear el usuario y la base de datos de pruebas.
2. Importar exclusivamente el esquema actualizado de NeuroMedX.
3. Verificar que las migraciones correspondientes esten aplicadas.
4. Configurar los permisos minimos.
5. Configurar el aislamiento mediante pg_hba.conf.
6. Crear el rol y la funcion de limpieza restringida.
7. Verificar que no existan registros reales.

## Seguridad

El usuario neuromedx_test solamente dispone de SELECT
e INSERT sobre las tablas usuarios y medicos.

No dispone de permisos UPDATE, DELETE ni TRUNCATE.

El rol neuromedx_test_cleanup no permite iniciar sesion
y no tiene privilegios de superusuario.

La funcion de limpieza utiliza SECURITY DEFINER,
un search_path restringido y validaciones de identidad,
identificadores ficticios y dependencias.

La funcion solo debe instalarse en la base de pruebas.

No deben importarse datos reales ni informacion clinica.

## Credenciales

No almacenar contrasenas en Git, scripts SQL ni archivos
de documentacion.

Las pruebas requieren las variables temporales:

- NEUROMEDX_PRUEBAS_POSTGRESQL=1
- NEUROMEDX_TEST_DB_PASSWORD

Eliminar ambas variables al finalizar la ejecucion.

## Ejecucion habitual

Desde el entorno virtual del backend:

python -m pytest tests -q

Las pruebas de PostgreSQL se omiten automaticamente
cuando no se habilita expresamente su ejecucion.

## Ejecucion de integracion

Despues de configurar las variables temporales:

python -m pytest tests/integracion -v --tb=short

Para ejecutar todas las pruebas:

python -m pytest tests -q --tb=short

## Estrategia de aislamiento

Las pruebas de restricciones y operaciones individuales
utilizan transacciones con ROLLBACK.

Las pruebas del registro medico utilizan SAVEPOINT
para comprobar la atomicidad.

Las pruebas de concurrencia utilizan conexiones
independientes y transacciones con COMMIT real.

Los registros confirmados durante estas pruebas se
eliminan mediante la funcion restringida de limpieza.

## Resultados de referencia

Fecha: 2026-11-27

- Backend y seguridad: 255 pruebas.
- Restricciones PostgreSQL: 39 pruebas.
- Modulo de medicos: 8 pruebas.
- Validacion del registro medico: 38 pruebas.
- Integracion del registro medico: 11 pruebas.
- Bloqueo transaccional: 1 prueba.
- Concurrencia: 4 pruebas.

Total: 356 pruebas superadas conjuntamente.
Tiempo observado: 75.15 segundos.
Pruebas fallidas: 0.
Pruebas omitidas: 0.

Tiempo de espera de bloqueo observado: 5.05 segundos.

## Limitaciones

Los resultados corresponden al entorno local evaluado.

No representan pruebas de carga masiva ni una
certificacion integral de seguridad.

La configuracion de pruebas no debe instalarse
en produccion.

Las pruebas de concurrencia deben ejecutarse sin otras
aplicaciones utilizando la base de datos de pruebas.
