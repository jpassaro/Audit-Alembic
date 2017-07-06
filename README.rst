========
Overview
========

.. start-badges

.. list-table::
    :stub-columns: 1

    * - docs
      - |docs|
    * - tests
      - | |travis| |appveyor| |requires|
        | |codecov|
    * - package
      - | |version| |wheel| |supported-versions| |supported-implementations|
        | |commits-since|

.. |docs| image:: https://readthedocs.org/projects/Audit-Alembic/badge/?style=flat
    :target: https://readthedocs.org/projects/Audit-Alembic
    :alt: Documentation Status

.. |travis| image:: https://travis-ci.org/jpassaro/Audit-Alembic.svg?branch=master
    :alt: Travis-CI Build Status
    :target: https://travis-ci.org/jpassaro/Audit-Alembic

.. |appveyor| image:: https://ci.appveyor.com/api/projects/status/github/jpassaro/Audit-Alembic?branch=master&svg=true
    :alt: AppVeyor Build Status
    :target: https://ci.appveyor.com/project/jpassaro/Audit-Alembic

.. |requires| image:: https://requires.io/github/jpassaro/Audit-Alembic/requirements.svg?branch=master
    :alt: Requirements Status
    :target: https://requires.io/github/jpassaro/Audit-Alembic/requirements/?branch=master

.. |codecov| image:: https://codecov.io/github/jpassaro/Audit-Alembic/coverage.svg?branch=master
    :alt: Coverage Status
    :target: https://codecov.io/github/jpassaro/Audit-Alembic

.. |version| image:: https://img.shields.io/pypi/v/Audit-Alembic.svg
    :alt: PyPI Package latest release
    :target: https://pypi.python.org/pypi/Audit-Alembic

.. |commits-since| image:: https://img.shields.io/github/commits-since/jpassaro/Audit-Alembic/v0.1.0.svg
    :alt: Commits since latest release
    :target: https://github.com/jpassaro/Audit-Alembic/compare/v0.1.0...master

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

These functions create an alembic history table and merely ask
you to specify your application version (though they allow much
else to be customized as well). If you already have a table you
wish to add records to whenever an alembic operation takes place,
and you have a callable that creates a row for that table,
you can instantiate ``Auditor`` directly::

    alembic_auditor = Auditor(HistoryTable, HistoryTable.alembic_version_applied)

In this case ``alembic_version_applied`` specifies how to build the row
based on Alembic's ``on_version_apply`` hook.

Customizing not just what data to populate a row with but whehter the row
should appear at all is not currently supported. If you wish to do so, directly
using Alembic's ``on_version_apply`` hook may be a better fit for you.

Documentation
=============

https://Audit-Alembic.readthedocs.io/ (not available yet)

Development
===========

Status
------

The most basic tests, for using Audit-Alembic "correctly", pass for Postgres,
MYSQL, and SQLite as a file. Travis does not appear to support MSSQL or Oracle
so test status for those DB backends is not known.

The next tests that need to be written should get us to 100% code coverage
as well as covering various error cases.

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
