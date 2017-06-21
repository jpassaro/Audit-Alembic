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

Track patch history alongside Alembic's database patch tracking.

* Free software: MIT license

Installation
============

::

    pip install Audit-Alembic

Documentation
=============

https://Audit-Alembic.readthedocs.io/

Development
===========

To run all tests, run::

    tox

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
