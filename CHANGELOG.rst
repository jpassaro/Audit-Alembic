
Changelog
=========

0.2.0 (TBD)
-----------

Alpha release, pending a patch in alembic without which we cannot support
stamps.

* Creates a listener for Alembic's ``on_version_apply`` callback hook which
  records information from that callback to a SQL table of the user's choosing.
* Test setup making use of SQLAlchemy testing plugins and utilities and Alembic
  testing utilities.
* Tests covering stamps, branches, and a couple of other complex use cases.
* Test setup to cover multiple DB backends. Known to work: SQLite, Postgresql,
  mysql.

0.1.0 (2017-06-21)
------------------

* First release on PyPI. (powered by cookiecutter-pylibrary_)

.. _cookiecutter-pylibrary: https://github.com/ionelmc/cookiecutter-pylibrary
