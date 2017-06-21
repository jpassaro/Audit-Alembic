============
Contributing
============

Contributions are welcome, and they are greatly appreciated! Every
little bit helps, and credit will always be given.

Bug reports
===========

When `reporting a bug <https://github.com/jpassaro/Audit-Alembic/issues>`_
please include:

    * Your operating system name and version.
    * Any details about your local setup that might be helpful in troubleshooting.
    * Detailed steps to reproduce the bug.

Documentation improvements
==========================

Audit-Alembic could always use more documentation, whether as part of the
official Audit-Alembic docs, in docstrings, or even on the web in blog posts,
articles, and such.

Feature requests and feedback
=============================

The best way to send feedback is to file an issue at
https://github.com/jpassaro/Audit-Alembic/issues.

If you are proposing a feature:

* Explain in detail how it would work.
* Keep the scope as narrow as possible, to make it easier to implement.
* Remember that I am just this guy, you know? If at all possible, please try
  implementing yourself; if it doesn't work, submit as a pull request and we'll
  see what we can make out of it.

Development
===========

To set up `Audit-Alembic` for local development:

1. Fork `Audit-Alembic <https://github.com/jpassaro/Audit-Alembic>`_
   (look for the "Fork" button).
2. Clone your fork locally::

    git clone git@github.com:your_name_here/Audit-Alembic.git

3. Create a branch for local development::

    git checkout -b name-of-your-bugfix-or-feature

   Now you can make your changes locally.

4. When you're done making changes, run all the checks, doc builder and spell checker with `tox <http://tox.readthedocs.io/en/latest/install.html>`_ one command::

    tox

5. Commit your changes and push your branch to GitHub::

    git add .
    git commit -m "Your detailed description of your changes."
    git push origin name-of-your-bugfix-or-feature

6. Submit a pull request through the GitHub website.

Pull Request Guidelines
-----------------------

If you need some code review or feedback while you're developing the code, just
submit the pull request.

For merging, you should:

1. Include passing tests (run ``tox``) [1]_. If you can write one that fails
   without your patch, even better! If your patch includes new code and does
   not include a test, it is unlikely to be accepted.
2. Update documentation when there's new API, functionality etc.
3. Add a note to ``CHANGELOG.rst`` about the changes.
4. Add yourself to ``AUTHORS.rst``.

.. [1] If you don't have all the necessary python versions available locally you can rely on Travis - it will
       `run the tests <https://travis-ci.org/jpassaro/Audit-Alembic/pull_requests>`_ for each change you add in the pull request.

       It will be slower though ...

Tips
----

To run a subset of tests::

    tox -e envname -- py.test -k test_myfeature

Simple ``pytest -k test_myfeature`` will not work; the package must be
installed first. ``tox`` does that for you.

To run all the test environments in *parallel* (you need to ``pip install detox``)::

    detox
