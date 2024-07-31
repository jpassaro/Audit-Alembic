import functools
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict

import audit_alembic
import pytest
from alembic import command as alcommand
from alembic import util
from alembic.script.base import ScriptDirectory
from alembic.testing.env import (
    _get_staging_directory,
    _testing_config,
    _write_config_file,
    env_file_fixture,
    staging_env,
)
from audit_alembic import exc
from sqlalchemy import Column, MetaData, Table, inspect, types
from sqlalchemy.sql import select
from sqlalchemy.testing import config as sqla_test_config
from sqlalchemy.testing import mock
from sqlalchemy.testing.fixtures import TestBase
from sqlalchemy.testing.util import drop_all_tables

test_col_name = "custom_data"

_env_content = """
import audit_alembic
import audit_alembic.exc
from sqlalchemy import Column, engine_from_config, pool, types

listen = audit_alembic.test_auditor.listen

def run_migrations_offline():
    url = config.get_main_option('sqlalchemy.url')
    context.configure(url=url, target_metadata=None,
                      literal_binds=True, on_version_apply=listen)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = audit_alembic.test_version.engine

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=None,
                          on_version_apply=listen)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
"""

_cfg_content = """
[alembic]
script_location = %s/scripts
sqlalchemy.url = %s
"""


def _custom_auditor(make_row: None | Dict[str, Any] | Callable[..., Dict[str, Any]] = None):
    def _make_row(**_):
        return {"changed_at": audit_alembic.CommonColumnValues.change_time}

    make_row = make_row or _make_row

    custom_table = Table(
        "custom_alembic_history",
        MetaData(),
        Column("id", types.BIGINT().with_variant(types.Integer, "sqlite"), primary_key=True),
        Column("changed_at", types.DateTime()),
    )
    return audit_alembic.Auditor(custom_table, make_row)


def _find(list_, f_or_obj, strip=False):
    if callable(f_or_obj):
        i = next((i for i, x in enumerate(list_) if f_or_obj(x)), None)
    elif f_or_obj in list_:
        i = list_.index(f_or_obj)
    else:
        i = None
    if strip and i is not None:
        list_[:] = list_[i + 1 :]
    return i


class AuditTypeError(TypeError):
    pass


def _multiequal(*args):
    def setify(x):
        if isinstance(x, (frozenset)):  # pragma: no cover
            return x
        if hasattr(x, "split"):
            x = x.split("##")
        if isinstance(x, (set, list, tuple)):
            return frozenset(x)
        raise AuditTypeError(repr(x) + " is not a valid input")

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
    staging_dir = Path(__file__).parent.parent / "scratch"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)

    env = staging_env()
    env_file_fixture(_env_content)
    _write_config_file(_cfg_content % (_get_staging_directory(), sqla_test_config.db_url))

    def gen(rev, head=None, **kw):
        if head:
            kw["head"] = list(head.split())
        revid = "__".join((rev, util.rev_id()))
        env.generate_revision(revid, rev, splice=True, **kw)

    gen("A")
    gen("B")
    gen("C")
    gen("D")
    gen("D0", "C")
    gen("E", "D__")
    gen("E0", "D0")
    gen("E1", "D0")
    gen("F", "E__ E0")
    gen("F1", "E1")
    gen("F2", "E1")
    gen("G", "F__ F1")
    gen("G2", "F2")
    gen("G3", "F2")
    gen("G4", "G3")
    gen("H", "G__ G2", depends_on="G4")

    return env


class _Versioner(object):
    """user version tracker"""

    def __init__(self, name, fmt="{name}:step-{n}"):
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
    audit_alembic.test_auditor = audit_alembic.test_version = audit_alembic.test_custom_data = None

    vers = _Versioner(":".join((request.module.__name__, request.cls.__name__, request.function.__name__)))
    vers.engine = db = sqla_test_config.db
    vers.conn = db.connect()

    @request.addfinalizer
    def teardown():
        vers.conn.close()
        drop_all_tables(db, inspect(db))

    with mock.patch(
        "audit_alembic.test_auditor",
        audit_alembic.Auditor.create(
            vers.version,
            extra_columns=[(Column(test_col_name, types.String(32)), lambda **kw: audit_alembic.test_custom_data)],
        ),
    ), mock.patch("audit_alembic.test_version", vers):
        yield vers


@pytest.fixture
def cmd():
    """Executes alembic commands but auto-substitutes current staging
    config"""

    class MyCmd(object):
        def __getattr__(self, attr):
            fn: Any = getattr(alcommand, attr)
            if callable(fn):
                old_fn = fn

                @functools.wraps(old_fn)
                def _fn(rev, *args, **kwargs):
                    old_fn(_testing_config(), rev, *args, **kwargs)
                    return rev

                return _fn
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
    q = select(
        *[
            table.c.alembic_version,
            table.c.prev_alembic_version,
            table.c.operation_direction,
            table.c.operation_type,
            table.c.user_version,
            getattr(table.c, test_col_name),
        ]
    ).order_by(table.c.changed_at)
    with sqla_test_config.db.begin() as conn:
        return conn.execute(q).fetchall()


class TestAuditTable(TestBase):
    __backend__ = True
    history = staticmethod(_history)

    def test_linear_updown_migrations(self, env, version, cmd):
        now = str(datetime.now())
        with mock.patch("audit_alembic.test_custom_data", now):

            @version.iterate
            def v():
                cmd.upgrade(env.get_revision("D_").revision)
                yield
                cmd.upgrade(env.get_revision("E_").revision)
                yield
                cmd.downgrade("base")

        assert len(v) == 3
        history = self.history()
        assert set(h[-1] for h in history) == set((now,))
        history = [h[:-1] for h in history]
        assert history == [
            (env.get_revision("A_").revision, "", "up", "migration", v[0]),
            (env.get_revision("B_").revision, env.get_revision("A_").revision, "up", "migration", v[0]),
            (env.get_revision("C_").revision, env.get_revision("B_").revision, "up", "migration", v[0]),
            (env.get_revision("D_").revision, env.get_revision("C_").revision, "up", "migration", v[0]),
            (env.get_revision("E_").revision, env.get_revision("D_").revision, "up", "migration", v[1]),
            (env.get_revision("D_").revision, env.get_revision("E_").revision, "down", "migration", v[2]),
            (env.get_revision("C_").revision, env.get_revision("D_").revision, "down", "migration", v[2]),
            (env.get_revision("B_").revision, env.get_revision("C_").revision, "down", "migration", v[2]),
            (env.get_revision("A_").revision, env.get_revision("B_").revision, "down", "migration", v[2]),
            ("", env.get_revision("A_").revision, "down", "migration", v[2]),
        ]

    def test_merge_unmerge(self, env, version, cmd):
        @version.iterate
        def v():
            cmd.upgrade(env.get_revision("F_").revision)
            yield
            cmd.downgrade(env.get_revision("E_").revision)

        penult, last = self.history()[-2:]
        assert penult[0] == last[1] == env.get_revision("F_").revision
        assert penult[3] == last[3] == "migration"
        assert penult[2] == "up"
        assert penult[4] == v[0]
        assert last[2] == "down"
        assert last[4] == v[1]
        assert (
            _multiequal((env.get_revision("E_").revision, env.get_revision("E0_").revision), penult[1], last[0])
            is not None
        )

    def test_stamp_no_dupe(self, env, version, cmd):
        @version.iterate
        def v():
            cmd.stamp(env.get_revision("B_").revision)
            yield
            cmd.upgrade(env.get_revision("C_").revision)

        assert self.history() == [
            (env.get_revision("B_").revision, "", "up", "stamp", v[0], None),
            (env.get_revision("C_").revision, env.get_revision("B_").revision, "up", "migration", v[1], None),
        ]

    def test_depends_on(self, env, version, cmd):
        @version.iterate
        def v():
            cmd.upgrade(env.get_revision("H_").revision)
            yield
            cmd.stamp(env.get_revision("G_").revision)
            yield
            cmd.stamp(env.get_revision("H_").revision)

        upgr, stdown, stup = self.history()[-3:]
        assert upgr[0] == env.get_revision("H_").revision
        assert (
            _multiequal(
                (env.get_revision("G_").revision, env.get_revision("G2_").revision, env.get_revision("G4_").revision),
                upgr[1],
            )
            is not None
        )
        assert upgr[2:] == ("up", "migration", v[0], None)
        assert stdown == (env.get_revision("G_").revision, env.get_revision("H_").revision, "down", "stamp", v[1], None)
        assert stup == (env.get_revision("H_").revision, env.get_revision("G_").revision, "up", "stamp", v[2], None)

    def test_stamp_down_from_two_heads_to_ancestor(self, env, version, cmd):
        @version.iterate
        def v():
            cmd.upgrade(env.get_revision("E_").revision)
            yield
            cmd.upgrade(env.get_revision("D0_").revision)
            yield
            cmd.stamp(env.get_revision("C_").revision)

        upE, upD, downC = self.history()[-3:]
        assert upE == (env.get_revision("E_").revision, env.get_revision("D_").revision, "up", "migration", v[0], None)
        assert upD == (env.get_revision("D0_").revision, env.get_revision("C_").revision, "up", "migration", v[1], None)
        assert downC[0] == env.get_revision("C_").revision
        assert downC[2:] == ("down", "stamp", v[2], None)
        assert _multiequal((env.get_revision("D0_").revision, env.get_revision("E_").revision), downC[1]) is not None

    def test_two_heads_stamp_down_from_one(self, env, version, cmd):
        @version.iterate
        def v():
            cmd.upgrade(env.get_revision("E_").revision)
            yield
            cmd.upgrade(env.get_revision("E0_").revision)
            yield
            cmd.stamp(env.get_revision("D_").revision)

        assert self.history()[-1] == (
            env.get_revision("D_").revision,
            env.get_revision("E_").revision,
            "down",
            "stamp",
            v[2],
            None,
        )

    def test_branches(self, env: ScriptDirectory, version, cmd):
        @version.iterate
        def v():
            cmd.upgrade(env.get_revision("D_").revision)
            yield
            cmd.downgrade(env.get_revision("C_").revision)
            yield
            cmd.stamp(env.get_revision("E1_").revision)
            yield
            cmd.upgrade(env.get_revision("H_").revision)

        history = [x[:-1] for x in self.history()]

        assert (
            _find(
                history,
                (env.get_revision("D_").revision, env.get_revision("C_").revision, "up", "migration", v[0]),
                True,
            )
            is not None
        )

        assert (
            _find(
                history,
                (env.get_revision("C_").revision, env.get_revision("D_").revision, "down", "migration", v[1]),
                True,
            )
            == 0
        )
        assert all(x[2] == "up" for x in history)
        # no more checking direction or custom data
        history = [x[:2] + x[3:] for x in history]

        assert (
            _find(history, (env.get_revision("E1_").revision, env.get_revision("C_").revision, "stamp", v[2]), True)
            == 0
        )
        assert all(x[2] == "migration" for x in history)
        assert all(x[-1] == v[3] for x in history)
        # no more checking type or revision
        history = [x[:2] + x[3:-1] for x in history]

        assert _find(history, (env.get_revision("D_").revision, env.get_revision("C_").revision)) is not None
        # but we won't find D0, it was skipped by the stamp to E1
        assert _find(history, (env.get_revision("D0_").revision, env.get_revision("C_").revision)) is None
        assert _find(history, (env.get_revision("E0_").revision, env.get_revision("D0_").revision)) is not None


class TestSqlMode(TestBase):
    def test_sql_mode(self, env, cmd, capsys):
        _, _ = capsys.readouterr()
        now = str(datetime.utcnow())
        with mock.patch("audit_alembic.test_custom_data", now):
            cmd.upgrade(env.get_revision("B_").revision, sql=True)
        out, _ = capsys.readouterr()
        print("duplicate out? ", out)
        out = list(filter(None, out.split("\n")))

        def has_create(expression: str):
            return expression.lower().startswith("create table alembic_version_history")

        def has_insert(expression: str):
            return env.get_revision("A_").revision in expression and expression.lower().startswith(
                "insert into alembic_version_history "
            )

        assert _find(out, has_create, True) is not None, "create table statement not found"
        assert _find(out, has_create) is None, "duplicate create table statement found"
        assert _find(out, has_insert) is not None, "insert statement not found"


class TestEnsureCoverage(TestBase):  # might as well call it what it is...
    def test_create_with_metadata(self):
        audit_alembic.Auditor.create("a", metadata=MetaData())

    def test_null_version_raises_warning(self):
        with pytest.warns(exc.UserVersionWarning):
            audit_alembic.Auditor.create(None)

    def test_null_version_nullable_no_warning(self, recwarn):
        audit_alembic.Auditor.create(None, user_version_nullable=True)
        assert not [w for w in recwarn.list if isinstance(w, exc.UserVersionWarning)]

    def test_null_version_callable_raises_warning(self, env, cmd):
        with mock.patch("audit_alembic.test_auditor", audit_alembic.Auditor.create(lambda **kw: None)), pytest.warns(
            exc.UserVersionWarning
        ):
            cmd.upgrade(env.get_revision("A_").revision)

    def test_null_version_callable_with_nullable_no_warning(self, env, cmd, recwarn):
        with mock.patch(
            "audit_alembic.test_auditor", audit_alembic.Auditor.create(lambda **kw: None, user_version_nullable=True)
        ):
            cmd.upgrade(env.get_revision("A_").revision)
        assert not [w for w in recwarn.list if isinstance(w, exc.UserVersionWarning)]

    def test_custom_table(self, env, cmd, version):
        # note: MYSQL turns timestamps to 1-second granularity... we must do
        # the same to ensure passing tests
        def flatten(dt: datetime, up=False):
            if up:
                dt += timedelta(milliseconds=990)
            return dt.replace(microsecond=0)

        before = flatten(datetime.now(UTC))
        with mock.patch("audit_alembic.test_auditor", _custom_auditor()) as auditor:
            cmd.upgrade(env.get_revision("A_").revision)

        q = select(auditor.table.c.changed_at)
        with sqla_test_config.db.begin() as conn:
            results = conn.execute(q).fetchall()
        assert len(results) == 1 and len(results[0]) == 1
        then = results[0][0].replace(tzinfo=UTC)
        print("Then:", repr(then))
        print("Before:", repr(before))
        assert before <= then
        after = flatten(datetime.now(UTC), True)  # ceiling
        assert then <= after


class TestErrors(TestBase):
    __backend__ = True

    def test_bad_make_row_non_callable(self):
        with pytest.raises(exc.AuditConstructError):
            _custom_auditor(make_row=object())

    def test_duplicate_column_names(self):
        with pytest.raises(exc.AuditCreateError):
            audit_alembic.Auditor.create(
                "a",
                alembic_version_column_name="foo",
                extra_columns=[(Column("foo"), "bar")],
            )

    def test_bad_migration_type(self):
        class BadMigrationInfo(object):
            is_migration = False
            is_stamp = False
            up_revision_id = "spam"

        with pytest.raises(exc.AuditRuntimeError):
            audit_alembic.CommonColumnValues.operation_type(step=BadMigrationInfo)

    def test_not_multiequal(self):
        assert _multiequal("a", "a##b") is None

    def test_bad_multiequal(self):
        with pytest.raises(AuditTypeError):
            _multiequal(object())

    def test_bad_make_row_callable(self, env, cmd):
        with mock.patch("audit_alembic.test_auditor", _custom_auditor(lambda **_: None)), pytest.raises(
            exc.AuditRuntimeError
        ):
            cmd.upgrade(env.get_revision("A_").revision)
