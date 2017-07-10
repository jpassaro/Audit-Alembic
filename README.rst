========
Overview
========

.. start-badges

.. list-table::
    :stub-columns: 1

    * - docs
      - |docs|
    * - tests
      - | |travis| | |codecov|
    * - package
      - | |version|

.. |docs| image:: https://readthedocs.org/projects/Audit-Alembic/badge/?style=flat
    :target: https://readthedocs.org/projects/Audit-Alembic
    :alt: Documentation Status

.. |travis| image:: https://travis-ci.org/jpassaro/Audit-Alembic.svg?branch=master
    :alt: Travis-CI Build Status
    :target: https://travis-ci.org/jpassaro/Audit-Alembic

.. |codecov| image:: https://codecov.io/github/jpassaro/Audit-Alembic/coverage.svg?branch=master
    :alt: Coverage Status
    :target: https://codecov.io/github/jpassaro/Audit-Alembic

.. |version| image:: https://img.shields.io/pypi/v/Audit-Alembic.svg
    :alt: PyPI Package latest release
    :target: https://pypi.python.org/pypi/Audit-Alembic

.. |wheel| image:: https://img.shields.io/pypi/wheel/Audit-Alembic.svg
    :alt: PyPI Wheel
    :target: https://pypi.python.org/pypi/Audit-Alembic

.. |supported-versions| image:: https://img.shields.io/pypi/pyversions/Audit-Alembic.svg
    :alt: Supported versions
    :target: https://pypi.python.org/pypi/Audit-Alembic

.. |supported-implementations| image:: https://img.shields.io/pypi/implementation/Audit-Alembic.svg
    :alt: Supported implementations
    :target: https://pypi.python.org/pypi/Audit-Alembic


.. end-badges

An Alembic plugin to keep records of upgrades and downgrades.

* Free software: MIT license

Installation
============

::

    pip install Audit-Alembic

Getting started
===============

Quickstart
----------

Add the following lines to your Alembic ``env.py``::

    from audit_alembic import Auditor
    from myapp import version

    Auditor.create(version).setup()

Slightly more involved::

    # myapp.py
    alembic_auditor = Auditor.create(version, ...)

    # env.py
    from myapp import alembic_auditor

    def run_migrations_offline():
        ...
        context.configure(
            ...
            on_version_apply=alembic_auditor.listen
        )
        ...

    def run_migrations_offline():
        ...
        context.configure(
            ...
            on_version_apply=alembic_auditor.listen
        )
    ...

More involved
-------------

The function :meth:`.Auditor.create` is a factory method: it creates an Alembic
history table and merely asks you to specify your application version (though
it allows much else to be customized as well). If you are already maintaining
a table you wish to add records to whenever an Alembic operation takes place,
and you have a callable that creates a row for that table, you can instantiate
:class:`.Auditor` directly::

    alembic_auditor = Auditor(HistoryTable, HistoryTable.alembic_version_applied)

In this case ``alembic_version_applied`` returns a dictionary that can serve
as parameters for an INSERT statement on ``HistoryTable``. It has the same
signature as documented for Alembic's ``on_version_apply`` hook.

Customizing not just what data to populate a row with but whether the row
should appear at all is not currently supported. Pull requests are welcomed.

Documentation
=============

https://Audit-Alembic.readthedocs.io/ (not available yet)

Development
===========

Status
------

The bulk of the test suite is complete and passing for Postgres, mysql, and
SQLite. Travis does not appear to support MSSQL or Oracle so test status for
those DB backends is not known. If you find that it does not work for your
backend, pull requests to make it so will be happily accepted.

Please feel free to expand from there. See the issues for a list of known
issues to work on.

Testing
-------

To run basic tests::

    $ virtualenv venv && source venv/bin/activate
    (venv) $ python setup.py install
    (venv) $ pip install pytest psycopg2
    (venv) $ pytest

To run all tests (i.e. py2 + py3, across all database drivers), run::

    $ tox

Also see our `Travis setup <https://travis-ci.org/jpassaro/Audit-Alembic>`_.

Note, to combine the coverage data from all the tox environments run:

.. list-table::
    :widths: 10 90
    :stub-columns: 1

    - - Windows
      - ::

            set PYTEST_ADDOPTS=--cov-append
            tox

    - - Other
      - ::

            PYTEST_ADDOPTS=--cov-append tox
