import contextlib
import functools
from datetime import datetime
from datetime import timedelta

import pytest
from alembic import command as alcommand
from alembic import util
from alembic.testing.env import _get_staging_directory
from alembic.testing.env import _testing_config
from alembic.testing.env import _write_config_file
from alembic.testing.env import env_file_fixture
from alembic.testing.env import staging_env
from sqlalchemy import Column
from sqlalchemy import MetaData
from sqlalchemy import Table
from sqlalchemy import inspect
from sqlalchemy import types
from sqlalchemy.sql import select
from sqlalchemy.testing import config as sqla_test_config
from sqlalchemy.testing import mock
from sqlalchemy.testing.fixtures import TestBase
from sqlalchemy.testing.util import drop_all_tables

import audit_alembic
from audit_alembic import exc

test_col_name = 'custom_data'

_env_content = """
import audit_alembic
from sqlalchemy import Column, engine_from_config, pool, types

def run_migrations_offline():
    url = config.get_main_option('sqlalchemy.url')
    context.configure(url=url, target_metadata=None, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = audit_alembic.test_version.engine

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()

with audit_alembic.test_auditor.setup():
    (run_migrations_offline if context.is_offline_mode()
     else run_migrations_online)()
"""

_cfg_content = """
[alembic]
script_location = %s/scripts
sqlalchemy.url = %s
"""


def _custom_auditor(make_row=None):
    if make_row is None:
        def make_row(**_):
            return {'changed_at': audit_alembic.CommonColumnValues.change_time}

    custom_table = Table('custom_alembic_history', MetaData(),
                         Column('id',
                                types.BIGINT().with_variant(types.Integer,
                                                            'sqlite'),
                                primary_key=True),
                         Column('changed_at', types.DateTime()))
    return audit_alembic.Auditor(custom_table, make_row)


def _find(list_, f_or_obj, strip=False):
    if callable(f_or_obj):
        i = next((i for i, x in enumerate(list_) if f_or_obj(x)), None)
    elif f_or_obj in list_:
        i = list_.index(f_or_obj)
    else:
        i = None
    if strip and i is not None:
        list_[:] = list_[i + 1:]
    return i


class AuditTypeError(TypeError):
    pass


def _multiequal(*args):
    def setify(x):
        if isinstance(x, (frozenset)):  # pragma: no cover
            return x
        if hasattr(x, 'split'):
            x = x.split('##')
        if isinstance(x, (set, list, tuple)):
            return frozenset(x)
        raise AuditTypeError(repr(x) + ' is not a valid input')

    allthem = set(map(setify, args))
    if len(allthem) == 1:
        return next(iter(allthem))


@pytest.fixture
def env():
    r"""Create an environment in which to run this test.

    Creates the environment directory using alembic.testing utilities, and
    additionally creates a revision map and scripts.

    Expressed visually, the map looks like this::

        A
        |
        B
        |
        C
        | \
        D  D0
        |  |  \
        E  E0  E1
        | /   / |
        F   F1  F2
        | /   / |
        G   G2  G3
        |   |  / |
        |   |  | G4
        |  /  / /
        | / / /
        ||/ /
        H--

    Note that ``H`` alone has a "depends_on", namely ``G4``.

    Uses class scope to create different environments for different backends.
    """
    env = staging_env()
    env_file_fixture(_env_content)
    _write_config_file(_cfg_content % (_get_staging_directory(),
                                       sqla_test_config.db_url))
    revs = env._revs = {}

    def gen(rev, head=None, **kw):
        if head:
            kw['head'] = [env._revs[h].revision for h in head.split()]
        revid = '__'.join((rev, util.rev_id()))
        env._revs[rev] = env.generate_revision(revid, rev, splice=True, **kw)

    gen('A')
    gen('B')
    gen('C')
    gen('D')
    gen('D0', 'C')
    gen('E', 'D')
    gen('E0', 'D0')
    gen('E1', 'D0')
    gen('F', 'E E0')
    gen('F1', 'E1')
    gen('F2', 'E1')
    gen('G', 'F F1')
    gen('G2', 'F2')
    gen('G3', 'F2')
    gen('G4', 'G3')
    gen('H', 'G G2', depends_on='G4')

    revids = env._revids = {k: v.revision for k, v in revs.items()}
    env.R = type('R', (object,), revids)
    yield env
    # we purposefully leave it intact so somebody running it can inspect the
    # contents after a test run. In other words, none of this:
    # clear_staging_env()
    # the user can just clean up after themselves. This seems to happen when
    # running alembic tests quite a bit.


class _Versioner(object):
    """user version tracker"""
    def __init__(self, name, fmt='{name}:step-{n}'):
        self.name = name
        self.n = 0
        self.fmt = fmt

    def inc(self, ct=1):
        self.n += ct

    def version(self, **kw):
        return self.fmt.format(name=self.name, n=self.n)

    def iterate(self, fn):
        """Go through a generator, incrementing version numbers, return all
        known version numbers"""
        def inner():
            yield self.version()
            for ct in fn():
                self.inc(ct or 1)
                yield self.version()
        return list(inner())


@pytest.fixture(autouse=True)
def version(request):
    """Creates a user version provider and an Auditor instance using it.

    The version shows the current module/class/instance/function names,
    along with an incrementing count that tests may increment to track
    progress.

    The Auditor can be accessed via ``audit_alembic.test_auditor``
    """
    audit_alembic.test_auditor = audit_alembic.test_version \
        = audit_alembic.test_custom_data = None

    vers = _Versioner(':'.join((request.module.__name__, request.cls.__name__,
                                request.function.__name__)))
    vers.engine = db = sqla_test_config.db
    vers.conn = db.connect()

    @request.addfinalizer
    def teardown():
        vers.conn.close()
        drop_all_tables(db, inspect(db))

    with mock.patch(
        'audit_alembic.test_auditor',
        audit_alembic.Auditor.create(
            vers.version,
            extra_columns=[(Column(test_col_name, types.String(32)),
                            lambda **kw: audit_alembic.test_custom_data)]
        )
    ), mock.patch('audit_alembic.test_version', vers):
        yield vers


@pytest.fixture
def cmd():
    """Executes alembic commands but auto-substitutes current staging
    config"""
    class MyCmd(object):
        def __getattr__(self, attr):
            fn = getattr(alcommand, attr)
            if callable(fn):
                old_fn = fn

                @functools.wraps(old_fn)
                def fn(rev, *args, **kwargs):
                    old_fn(_testing_config(), rev, *args, **kwargs)
                    return rev
                return fn
            else:  # pragma: no cover
                return fn
    return MyCmd()


# 0. (setup/setup_class) create staging env, create env file that listens
#    using str(time.time()) as user_version
# 1. create A->B->C->D
# 2. full upgrade, check table: verify A/B/C/D upgrades appear
# 4. splice C->D0
# 5. full upgrade, check table: verify D0 upgrade appears
# 6. downgrade D, check table: verify D downgrade appears
# 6. create E, E0, E1, F1
# 7. stamp E1, check table for E1 stamp upgrade from D0
# 8. upgrade, verify upgrades appear for E, E0, F1, no dupe E1, old row for D
#     unchanged and new D upgrade also appears


def _history():
    table = audit_alembic.test_auditor.table
    q = select([
        table.c.alembic_version,
        table.c.prev_alembic_version,
        table.c.operation_direction,
        table.c.operation_type,
        table.c.user_version,
        getattr(table.c, test_col_name),
    ]).order_by(table.c.changed_at)
    return sqla_test_config.db.execute(q).fetchall()


class TestAuditTable(TestBase):
    __backend__ = True
    history = staticmethod(_history)

    def test_linear_updown_migrations(self, env, version, cmd):
        now = str(datetime.utcnow())
        with mock.patch('audit_alembic.test_custom_data', now):
            @version.iterate
            def v():
                cmd.upgrade(env.R.D)
                yield
                cmd.upgrade(env.R.E)
                yield
                cmd.downgrade('base')

        assert len(v) == 3
        history = self.history()
        assert set(h[-1] for h in history) == set((now,))
        history = [h[:-1] for h in history]
        assert history == [
            (env.R.A, '', 'up', 'migration', v[0],),
            (env.R.B, env.R.A, 'up', 'migration', v[0],),
            (env.R.C, env.R.B, 'up', 'migration', v[0],),
            (env.R.D, env.R.C, 'up', 'migration', v[0],),
            (env.R.E, env.R.D, 'up', 'migration', v[1],),
            (env.R.D, env.R.E, 'down', 'migration', v[2],),
            (env.R.C, env.R.D, 'down', 'migration', v[2],),
            (env.R.B, env.R.C, 'down', 'migration', v[2],),
            (env.R.A, env.R.B, 'down', 'migration', v[2],),
            ('', env.R.A, 'down', 'migration', v[2],),
        ]

    def test_merge_unmerge(self, env, version, cmd):
        @version.iterate
        def v():
            cmd.upgrade(env.R.F)
            yield
            cmd.downgrade(env.R.E)

        penult, last = self.history()[-2:]
        assert penult[0] == last[1] == env.R.F
        assert penult[3] == last[3] == 'migration'
        assert penult[2] == 'up'
        assert penult[4] == v[0]
        assert last[2] == 'down'
        assert last[4] == v[1]
        assert _multiequal((env.R.E, env.R.E0), penult[1], last[0]) is not None

    def test_stamp_no_dupe(self, env, version, cmd):
        @version.iterate
        def v():
            cmd.stamp(env.R.B)
            yield
            cmd.upgrade(env.R.C)
        assert self.history() == [
            (env.R.B, '', 'up', 'stamp', v[0], None),
            (env.R.C, env.R.B, 'up', 'migration', v[1], None),
        ]

    def test_depends_on(self, env, version, cmd):
        @version.iterate
        def v():
            cmd.upgrade(env.R.H)
            yield
            cmd.stamp(env.R.G)
            yield
            cmd.stamp(env.R.H)

        upgr, stdown, stup = self.history()[-3:]
        assert upgr[0] == env.R.H
        assert _multiequal((env.R.G, env.R.G2, env.R.G4), upgr[1]) is not None
        assert upgr[2:] == ('up', 'migration', v[0], None)
        assert stdown == (env.R.G, env.R.H, 'down', 'stamp', v[1], None)
        assert stup == (env.R.H, env.R.G, 'up', 'stamp', v[2], None)

    def test_stamp_down_from_two_heads_to_ancestor(self, env, version, cmd):
        @version.iterate
        def v():
            cmd.upgrade(env.R.E)
            yield
            cmd.upgrade(env.R.D0)
            yield
            cmd.stamp(env.R.C)

        upE, upD, downC = self.history()[-3:]
        assert upE == (env.R.E, env.R.D, 'up', 'migration', v[0], None)
        assert upD == (env.R.D0, env.R.C, 'up', 'migration', v[1], None)
        assert downC[0] == env.R.C
        assert downC[2:] == ('down', 'stamp', v[2], None)
        assert _multiequal((env.R.D0, env.R.E), downC[1]) is not None

    def test_two_heads_stamp_down_from_one(self, env, version, cmd):
        @version.iterate
        def v():
            cmd.upgrade(env.R.E)
            yield
            cmd.upgrade(env.R.E0)
            yield
            cmd.stamp(env.R.D)

        assert self.history()[-1] == (env.R.D, env.R.E, 'down', 'stamp', v[2],
                                      None)

    def test_branches(self, env, version, cmd):
        @version.iterate
        def v():
            cmd.upgrade(env.R.D)
            yield
            cmd.downgrade(env.R.C)
            yield
            cmd.stamp(env.R.E1)
            yield
            cmd.upgrade(env.R.H)

        history = [x[:-1] for x in self.history()]

        assert _find(history, (env.R.D, env.R.C, 'up', 'migration', v[0]),
                     True) is not None

        assert _find(history, (env.R.C, env.R.D, 'down', 'migration', v[1]),
                     True) == 0
        assert all(x[2] == 'up' for x in history)
        # no more checking direction or custom data
        history = [x[:2] + x[3:] for x in history]

        assert _find(history, (env.R.E1, env.R.C, 'stamp', v[2]), True) == 0
        assert all(x[2] == 'migration' for x in history)
        assert all(x[-1] == v[3] for x in history)
        # no more checking type or revision
        history = [x[:2] + x[3:-1] for x in history]

        assert _find(history, (env.R.D, env.R.C)) is not None
        # but we won't find D0, it was skipped by the stamp to E1
        assert _find(history, (env.R.D0, env.R.C)) is None
        assert _find(history, (env.R.E0, env.R.D0)) is not None


class TestSqlMode(TestBase):
    def test_sql_mode(self, env, cmd, capsys):
        _, _ = capsys.readouterr()
        now = str(datetime.utcnow())
        with mock.patch('audit_alembic.test_custom_data', now):
            cmd.upgrade(env.R.B, sql=True)
        out, _ = capsys.readouterr()
        print('duplicate out? ', out)
        out = list(filter(None, out.split('\n')))

        def has_create(l):
            return l.lower().startswith('create table alembic_version_history')

        assert _find(out, has_create, True) is not None, \
            'create table statement not found'
        assert _find(out, has_create) is None, \
            'duplicate create table statement found'
        assert _find(out, lambda l: (env.R.A in l and l.lower().startswith(
            'insert into alembic_version_history '
        ))) is not None, 'insert statement not found'


class TestEnsureCoverage(TestBase):  # might as well call it what it is...
    def test_create_with_metadata(self):
        audit_alembic.Auditor.create('a', metadata=MetaData())

    def test_null_version_raises_warning(self):
        with pytest.warns(exc.UserVersionWarning):
            audit_alembic.Auditor.create(None)

    def test_null_version_nullable_no_warning(self, recwarn):
        audit_alembic.Auditor.create(None, user_version_nullable=True)
        assert not [w for w in recwarn.list
                    if isinstance(w, exc.UserVersionWarning)]

    def test_null_version_callable_raises_warning(self, env, cmd):
        with mock.patch('audit_alembic.test_auditor',
                        audit_alembic.Auditor.create(lambda **kw: None)), \
                pytest.warns(exc.UserVersionWarning):
            cmd.upgrade(env.R.A)

    def test_null_version_callable_with_nullable_no_warning(self, env, cmd,
                                                            recwarn):
        with mock.patch('audit_alembic.test_auditor',
                        audit_alembic.Auditor.create(
                            lambda **kw: None, user_version_nullable=True)):
            cmd.upgrade(env.R.A)
        assert not [w for w in recwarn.list
                    if isinstance(w, exc.UserVersionWarning)]

    def test_custom_table(self, env, cmd, version):
        # note: MYSQL turns timestamps to 1-second granularity... we must do
        # the same to ensure passing tests
        def flatten(dt, up=False):
            if up:
                dt += timedelta(milliseconds=990)
            return dt.replace(microsecond=0)

        before = flatten(datetime.utcnow())
        with mock.patch('audit_alembic.test_auditor',
                        _custom_auditor()) as auditor:
            cmd.upgrade(env.R.A)

        q = select([auditor.table.c.changed_at])
        results = sqla_test_config.db.execute(q).fetchall()
        assert len(results) == 1 and len(results[0]) == 1
        then = results[0][0]
        assert before <= then
        after = flatten(datetime.utcnow(), True)  # ceiling
        assert then <= after

    def test_no_global_context(self):
        with audit_alembic.test_auditor.setup():
            from alembic import context
            assert context.configure.__name__ == 'audit_alembic_configure'

    def test_supports_callback_test(self):
        from audit_alembic import supports_callback
        assert supports_callback()

        def good(on_version_apply=None):
            pass  # pragma: no cover

        def bad():
            pass  # pragma: no cover

        assert supports_callback(good)
        assert not supports_callback(bad)


class TestErrors(TestBase):
    __backend__ = True

    def test_bad_make_row_non_callable(self):
        with pytest.raises(exc.AuditConstructError):
            _custom_auditor(make_row=object())

    def test_duplicate_column_names(self):
        with pytest.raises(exc.AuditCreateError):
            audit_alembic.Auditor.create(
                'a',
                alembic_version_column_name='foo',
                extra_columns=[(Column('foo'), 'bar')],
            )

    def test_bad_migration_type(self):
        class BadMigrationInfo(object):
            is_migration = False
            is_stamp = False
            up_revision_id = 'spam'

        with pytest.raises(exc.AuditRuntimeError):
            audit_alembic.CommonColumnValues.operation_type(
                step=BadMigrationInfo)

    def test_no_callback_support(self):
        class BadContext(object):
            def configure(self):
                pass  # pragma: no cover

        with pytest.raises(exc.AuditSetupError):
            audit_alembic.test_auditor.setup(context=BadContext()).__enter__()

    def test_not_multiequal(self):
        assert _multiequal('a', 'a##b') is None

    def test_bad_multiequal(self):
        with pytest.raises(AuditTypeError):
            _multiequal(object())

    def test_nested_auditor(self, env, cmd):
        existing_setup = audit_alembic.test_auditor.setup

        @contextlib.contextmanager
        def nested_setup():
            with existing_setup():
                with _custom_auditor().setup():
                    yield  # pragma: no cover

        with pytest.raises(exc.AuditSetupError), \
                mock.patch('audit_alembic.test_auditor.setup', nested_setup):
            cmd.upgrade(env.R.A)

    def test_bad_make_row_callable(self, env, cmd):
        with mock.patch('audit_alembic.test_auditor',
                        _custom_auditor(lambda **_: None)), \
                pytest.raises(exc.AuditRuntimeError):
            cmd.upgrade(env.R.A)
