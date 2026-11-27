class RegistroTemporalmenteNoDisponible(Exception):
    """
    Indica que el registro no pudo completarse
    temporalmente por un bloqueo de PostgreSQL.
    """

    pass
