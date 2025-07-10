Getting Involved
----------------

Development is coordinated almost entirely on our [Github] page.
For quick help or a friendly chat you are welcome to pop into our IRC channel [`#alot` on Libera.chat][Libera].


Bug reports and feature requests
-----------------------------------
Are more than welcome via our [issue tracker][Issues].
Before you do, please be sure that

* you are using up to date versions of alot and notmuch
* your bug/feature is not already being discussed on the [issue tracker][ISSUES]
* your feature request is in scope of the project. Specifically *not in scope are
  features related to contact management, fetching and sending email*.


Licensing
---------
Alot is licensed under the [GNU GPLv3+][GPL3] and all code contributions will be covered by this license.

You will retain your copyright on all code you write.
By contributing you have agreed that you have the right to contribute the code
you have written, that the code you are contributing is owned by you or
licensed with a compatible license allowing it to be added to alot, and that
your employer or educational institution either does not or cannot claim the
copyright on any code you write, or that they have given you a waiver to contribute to alot.


Pull Requests
---------------
You are welcome to submit changes as pull requests on github.
This will trigger consistency checks and unit tests to be run on our CI system.

To ensure timely and painless reviews please keep the following in mind.

* Follow [PEP8]. You can use [automatic tools][pycodestyle] to verify your code.

* Document your code! We want readable and well documented code.
  Please use [sphinx] directives to document the signatures of your methods.
  For new features also update the user manual in `docs/source/usage` accordingly.

* Unit tests: Make sure your changes don't break any existing tests (to check
  locally use `python3 -m unittest`). If you are fixing a bug or adding a new
  features please provide new tests if possible.

* Keep commits simple. Large individual patches are incredibly painful to review properly.
  Please split your contribution into small, focussed and digestible commits
  and include [sensible commit messages][commitiquette].


Type Hints
----------
Alot uses [Python type hints][typing] with [mypy] for static type checking.
Type hints are gradually being added to the codebase, starting with core isolated modules.

When contributing:
* Add type hints to new modules when possible
* Update the mypy configuration in `pyproject.toml` for newly typed modules  
* Run `mypy --ignore-missing-imports your_module.py` to check for type errors locally
* Type checking runs automatically in CI

Currently typed modules: `alot.errors`, `alot.__init__`, `alot.utils.cached_property`


[Github]: https://github.com/pazz/alot
[Issues]: https://github.com/pazz/alot/issues
[Libera]: https://web.libera.chat/#alot
[GPL3]: https://www.gnu.org/licenses/gpl-3.0.en.html
[PEP8]: https://www.python.org/dev/peps/pep-0008/
[pycodestyle]:https://github.com/PyCQA/pycodestyle
[sphinx]: https://www.sphinx-doc.org/en/master/usage/restructuredtext/field-lists.html
[commitiquette]: https://chris.beams.io/posts/git-commit/
[typing]: https://typing.python.org/en/latest/
[mypy]: https://www.mypy-lang.org/
