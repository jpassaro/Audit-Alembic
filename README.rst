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

`Create an Alembic environment
<http://alembic.zzzcomputing.com/en/latest/tutorial.html>`_ if you don't
already have one.  Edit its ``env.py`` to include the following::

    # ... imports ...
    import audit_alembic
    from myapp import version

    if not audit_alembic.alembic_supports_callback():
        raise audit_alembic.exc.AuditSetupError(
            'This Alembic version does not have on_version_apply')
    auditor = audit_alembic.Auditor.create(version)

    def run_migrations_offline():
        ...
        context.configure(
            ...
            on_version_apply=auditor.listen,
        )
        ...

    def run_migrations_offline():
        ...
        context.configure(
            ...
            on_version_apply=auditor.listen
        )
    ...

More involved
-------------

:meth:`.Auditor.create` is a factory method: it creates an Alembic history
table for you and merely asks you to specify your application version (though
it allows much else to be customized as well). If you are already maintaining a
table you wish to add records to whenever an Alembic operation takes place, and
you have a callable that creates a row for that table, you can instantiate
:class:`.Auditor` directly::

    auditor = Auditor(HistoryTable, HistoryTable.alembic_version_applied)

In this case ``alembic_version_applied`` must return a dictionary that can
serve as binds for an INSERT statement on ``HistoryTable``. It has the same
signature as documented for Alembic's ``on_version_apply`` hook.

.. note
    Customizing not just what data to populate a row with but whether the row
    should appear at all is not currently supported but is
    `planned <http://github.com/jpassaro/Audit-Alembic/issues/1>`_ for a
    release in the near future. Pull requests are welcomed.

Full Documentation
==================

Once the 0.2.0 release is complete, the docs will be accessible here:
https://Audit-Alembic.readthedocs.io/

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

See CONTRIBUTING.rst for more detail.
Also see our `Travis setup <https://travis-ci.org/jpassaro/Audit-Alembic>`_.
