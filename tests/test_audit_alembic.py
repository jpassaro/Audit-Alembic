import functools

import pytest
from alembic import command as alcommand
from alembic import util
from alembic.testing.env import _get_staging_directory
from alembic.testing.env import _testing_config
from alembic.testing.env import _write_config_file
from alembic.testing.env import clear_staging_env
from alembic.testing.env import env_file_fixture
from alembic.testing.env import staging_env
from sqlalchemy import inspect
from sqlalchemy.sql import select
from sqlalchemy.testing import config as sqla_test_config
from sqlalchemy.testing import mock
from sqlalchemy.testing.fixtures import TestBase
from sqlalchemy.testing.util import drop_all_tables

import audit_alembic
from audit_alembic.cli import main


_env_content = """
import audit_alembic
from sqlalchemy import engine_from_config, pool

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


@pytest.fixture
def env():
    r"""Create an environment in which to run this test class.

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
    env._revs = {}

    def gen(rev, head=None, revid=None, **kw):
        if head:
            kw['head'] = [env._revs[h].revision for h in head.split()]
        if revid is None:
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
    gen('H', 'G G2 G3', depends_on='G4')

    def revids(*names):
        return '##'.join(env._revs[k].revision for k in names)
    env._revids = revids
    yield env


class _Versioner(object):
    """user version tracker"""
    def __init__(self, name, fmt='{name}:step-{n}'):
        self.name = name
        self.n = 0
        self.fmt = fmt

    def inc(self, ct=1):
        self.n += ct

    def version(self, n=None, **kw):
        if n is None:
            n = self.n
        return self.fmt.format(name=self.name, n=n)

    def verify(self, version, exp_n=''):
        expstr = self.version(exp_n or '')
        if exp_n:
            assert expstr == version
        else:
            assert version.startswith(expstr)
            version = version[len(expstr):]
            assert version and version.isdigit()
            return int(version)

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
    audit_alembic.test_auditor = audit_alembic.test_version = None

    vers = _Versioner(':'.join((request.module.__name__, request.cls.__name__,
                                request.function.__name__)))
    vers.engine = db = sqla_test_config.db
    vers.conn = db.connect()

    @request.addfinalizer
    def teardown():
        drop_all_tables(db, inspect(db))

    with mock.patch('audit_alembic.test_auditor',
                    audit_alembic.Auditor.create(vers.version)) as auditor, \
            mock.patch('audit_alembic.test_version', vers):
        yield vers


@pytest.fixture
def cmd():
    """Executes alembic commands but auto-substitutes current staging
    config"""
    class MyCmd(object):
        def __getattr__(self, attr):
            fn = getattr(alcommand, attr)
            if callable(fn):
                @functools.wraps(fn)
                def inner(*args, **kwargs):
                    return fn(_testing_config(), *args, **kwargs)
                return inner
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

class TestAudit(TestBase):
    __backend__ = True

    @classmethod
    def history(cls):
        table = audit_alembic.test_auditor.table
        q = select([
            table.c.alembic_version,
            table.c.prev_alembic_version,
            table.c.operation_direction,
            table.c.operation_type,
            table.c.user_version,
        ]).order_by(table.c.changed_at)
        return sqla_test_config.db.execute(q).fetchall()

    def test_linear_updown_migrations(self, env, version, cmd):
        @version.iterate
        def v():
            cmd.upgrade(env._revids('D'))
            yield
            cmd.upgrade(env._revids('E'))
            yield
            cmd.downgrade('base')

        assert len(v) == 3
        assert self.history() == [
            (env._revids('A'), '', 'up', 'migration', v[0],),
            (env._revids('B'), env._revids('A'), 'up', 'migration', v[0],),
            (env._revids('C'), env._revids('B'), 'up', 'migration', v[0],),
            (env._revids('D'), env._revids('C'), 'up', 'migration', v[0],),
            (env._revids('E'), env._revids('D'), 'up', 'migration', v[1],),
            (env._revids('D'), env._revids('E'), 'down', 'migration', v[2],),
            (env._revids('C'), env._revids('D'), 'down', 'migration', v[2],),
            (env._revids('B'), env._revids('C'), 'down', 'migration', v[2],),
            (env._revids('A'), env._revids('B'), 'down', 'migration', v[2],),
            ('', env._revids('A'), 'down', 'migration', v[2],),
        ]

    def test_merge_unmerge(self, env, version, cmd):
        @version.iterate
        def v():
            cmd.upgrade(env._revids('F'))
            yield
            cmd.downgrade(env._revids('E'))

        F = env._revids('F')
        Es = env._revids('E', 'E0')
        assert self.history()[-2:] == [
            (F, Es, 'up', 'migration', v[0]),
            (Es, F, 'down', 'migration', v[1]),
        ]
