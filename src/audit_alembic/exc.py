
class AuditError(Exception):
    pass


class AuditConstructError(AuditError):
    pass


class AuditCreateError(AuditError):
    pass


class AuditRuntimeError(AuditError):
    pass


class AuditSetupError(AuditError):
    pass


class UserVersionWarning(UserWarning):
    '''Audit-Alembic recommends against providing a null user version'''
