from sqlalchemy.testing.fixtures import TestBase

from audit_alembic.cli import main


class TestMigrationContext(TestBase):
    __backend__ = True
    def test_migrations(self):
        assert main([]) == 0
