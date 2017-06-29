import contextlib
import inspect
from datetime import datetime

from alembic import __version__ as alembic_version
from alembic import context as alembic_context
from alembic import util as alembic_util
from alembic.operations import ops
from alembic.runtime.environment import EnvironmentContext
from sqlalchemy import CheckConstraint
from sqlalchemy import Column
from sqlalchemy import MetaData
from sqlalchemy import Table
from sqlalchemy import types

ALEMBIC_SUPPORTS_EVENTS = hasattr(EnvironmentContext, 'on_version_apply')
del EnvironmentContext


def to_tuple(x):
    return alembic_util.to_tuple(x, default=())


class Auditor(object):
    """Watches Alembic operations, creates and populates a history table.

    This class holds the :class:`sqlalchemy.Table` storing version history
    and information about how to generate rows for it.

    The plain constructor needs only a table, at least one method to generate
    update dicts from a given callback step, and a connection. This is
    appropriate if you are storing history information in a table your
    application already maintains. Otherwise, a :meth:`factory method
    <.Auditor.create>` is available that does most of the work for you, namely
    it defines and creates the table as well as its update method.

    :param table: a SQLAlchemy ``Table``.
    :param make_row: a function or dict.

        If ``make_row`` is callable, it must accept the kwargs provided by
        alembic's on_version_apply, and return a valid dict for the given
        table. Otherwise, it must itself be a valid dict.

        A valid dict must provide keys corresponding to columns of
        :paramref:`~.Auditor.table`. Each value must be a valid input for its
        corresponding column; it may also be callable, in which case it takes
        the kwargs provided by alembic's on_version_apply and returns valid
        input for its corresponding column.
    """
    def __init__(self, table, make_row=None):
        self.table = table
        if not (callable(make_row) or hasattr(make_row, 'items')):
            raise ValueError('invalid make_rows argument')
        self._make_row = make_row
        self.created = False

    @classmethod
    def create(
        cls,
        user_version,
        table_name='alembic_version_history',
        metadata=None,
        extra_columns=(),
        user_version_column_name='user_version',
        user_version_type=types.String(255),
        direction_column_name='operation_direction',
        operation_column_name='operation_type',
        alembic_version_separator='##',
        alembic_version_column_name='alembic_version',
        prev_alembic_version_column_name='prev_alembic_version',
        change_time_column_name='changed_at',
    ):
        """Autocreate a history table.

        This table contains columns for:

        * user version
        * alembic version(s) prior to upgrade
        * alembic version(s) after upgrade
        * :paramref:`operation type <.Auditor.create.operation_column_name>`
        * :paramref:`operation direction <.Auditor.create.direction_column_name>`
        * operation direction
        * upgrade time

        The user may add their own columns and, to some extent, customize
        those provided. See the parameter list for details.

        :param user_version: a constant value or callable giving the user
            version to be stored with each migration step. If callable, it
            accepts the kwargs provided by alembic's on_version_apply
            callback. A good value for this might be your application's git
            version or current version tag.

        .. note::

            :paramref:`.Auditor.create.user_version` does not have to be
            provided. It can be null. It is intended to tie an alembic version
            to a specific point in your version control, so that you may
            consult that history and know exactly the content of the patch
            that was executed. Failing to include this information may
            seriously dilute the value of keeping these records at all. For
            that reason, we highly recommend providing *something* here.

        :param table_name: The name of the version history table.
        :param metadata: The SQLAlchemy MetaData object with which the table
            is to be created. If not provided, a new one will be created.
        :param extra_columns: A sequence of extra columns to add to the
            default table. Each element of the column is a 2-tuple
            ``(col, val)`` where ``col`` is a SQLAlchemy ``Column`` and
            ``val`` is a value for it, expressed the same way as
            :paramref:`~.Auditor.create.user_version`: as a constant,
            type-appropriate value, or a function of kwargs returning such a
            value.
        :param user_version_column_name: the name used for the column
            storing the value of :paramref:`~.Auditor.create.user_version`.
        :param user_version_type: the SQL type of
            :paramref:`~.Auditor.create.user_version`. If not specified, this
            is assumed to be VARCHAR(32).
        :param operation_column_name: the name of the column storing operation
            type. Currently supported values are ``migrate`` and ``stamp``,
            which indicate respectively that database changes are made, or
            that the version is changed without effecting any true changes.
            The field is nonnullable but unconstrained in case future Alembic
            versions support other migration types.
        :param direction_column_name: the name of the column storing the
            operation direction. This column is an enum (native on backends that
            support it, or given as a varchar with constraints) of the string
            values ``up`` and ``down``. It is left nullable in case future
            Alembic versions support migration types without an up/down
            direction.
        :param alembic_version_column_name: The name of the column storing
            the "new" (i.e. after the operation is complete) alembic
            version(s) of the database. Note that this is distinct in theory
            from the "up" version of the migration operation, and distinct
            in practice when the operation is a downgrade.
        :param prev_alembic_version_column_name: The name of the column
            storing the "old" (i.e before the operation is complete) alembic
            version(s) of the database. Note that this is distinct in theory
            from the "down" version of the migration operation, and distinct
            in practice when the operation is a downgrade.
        :param alembic_version_separator: if multiple alembic versions are
            given for one of the alembic version columns, they are joined
            together with ``alembic_version_separator`` as the delimiter.
        :param change_time_column_name: the name of the column storing the
            time of this migration

        """
        if metadata is None:
            metadata = MetaData()

        alembic_version_type = types.String(255)

        columns = [
            Column('id', types.BIGINT().with_variant(types.Integer, 'sqlite'),
                   primary_key=True),
            Column(alembic_version_column_name, alembic_version_type),
            Column(prev_alembic_version_column_name, alembic_version_type),
            CheckConstraint(
                'coalesce(%s, %s) IS NOT NULL' % (
                    alembic_version_column_name,
                    prev_alembic_version_column_name),
                name='alembic_versions_nonnull'),
            Column(operation_column_name, types.String(32), nullable=False),
            Column(direction_column_name, types.String(32), nullable=False),
            Column(user_version_column_name, user_version_type),
            Column(change_time_column_name, types.DateTime())
        ]

        def alembic_version_getter(vtype):
            def getter(step=None, **_):
                return alembic_version_separator.join(to_tuple(
                    getattr(step, '%s_revision_ids' % vtype)))
            return getter

        col_vals = {
            alembic_version_column_name: alembic_version_getter('destination'),
            prev_alembic_version_column_name: alembic_version_getter('source'),
            operation_column_name: cls.get_operation_type,
            direction_column_name: cls.get_operation_direction,
            user_version_column_name: user_version,
            change_time_column_name: cls.get_change_time,
        }
        for col, val in extra_columns:
            columns.append(col)
            if col.name in col_vals:
                raise KeyError('value %s used twice' % col.name)
            col_vals[col.name] = val

        return cls(Table(table_name, metadata, *columns), col_vals)

    @staticmethod
    def get_operation_type(step=None, **_):
        if step.is_stamp:
            return 'stamp'
        elif step.is_migration:
            return 'migration'
        else:
            raise ValueError('Unknown migration type %s'
                             % (step.up_revision_id))

    @staticmethod
    def get_operation_direction(step=None, **_):
        if step.is_upgrade:
            return 'up'
        else:
            return 'down'

    @staticmethod
    def get_change_time(**_):
        return datetime.utcnow()

    @contextlib.contextmanager
    def setup(self, context=None):
        """Call from env.py to set up audit listening.

        This function checks whether the current version of alembic supports
        it and if so, monkey-patches ``context.configure`` to inject this
        listener into its arguments.

        It must be used as a context manager, since afterward it undoes the
        monkey patch.

        :param context: the context to monkey-patch. By default we use
            ``alembic.context``.
        :raise ValueError: if context not provided, ``alembic.context``
            must be active. Additionally ValueError will be raised if
            the alembic version present does not support ``on_version_apply``.
        """
        if context is None:
            context = alembic_context
            if not hasattr(context, '_proxy'):
                raise ValueError('No alembic context given and the global '
                                 'one is not yet initialized')

        orig_configure = context.configure
        if orig_configure.__name__ != 'audit_alembic_configure':
            spec = inspect.getargspec(orig_configure)
            if 'on_version_apply' not in spec.args:
                raise ValueError(
                    'Alembic version %s does not support event listening'
                    % alembic_version)

        def audit_alembic_configure(**kw):
            on_version_apply = to_tuple(kw.get('on_version_apply'))
            kw['on_version_apply'] = on_version_apply + (self.listen,)
            return orig_configure(**kw)

        context.configure = audit_alembic_configure
        yield
        context.configure = orig_configure

    def make_row(self, make_row=None, **kw):
        if make_row is None:
            make_row = self._make_row
        if callable(make_row):
            make_row = make_row(**kw)
        if hasattr(make_row, 'items'):
            make_row = {k: v(**kw) if callable(v) else v
                        for k, v in make_row.items()}
        return make_row

    def listen(self, ctx=None, **kw):
        from alembic import op
        if not self.created:
            if ctx.as_sql:
                op.invoke(ops.CreateTableOp.from_table(self.table))
            else:
                self.table.create(ctx.connection, checkfirst=True)
            self.created = True
        op.bulk_insert(self.table, [self.make_row(**kw)])
