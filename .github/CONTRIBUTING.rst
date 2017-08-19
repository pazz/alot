Contributing
============


Getting Involved
----------------

Development is coordinated almost entirely via the projects `github page
<https://github.com/pazz/alot>`_ especially the `issue tracker
<https://github.com/pazz/alot/issues>`_. We also have an irc channel on
freenode: #alot


Bugs and Feature Requests
-------------------------


Filing a Bug
````````````

Use the issue tracker on github to file bugs.

Before filing a bug please be sure that you've checked the following:

* That there is not already a bug filed

  * If there is a bug filed, you can follow that bug

  * Please refrain from adding "me too" comments unless the bug has been quiet
    for a while

* That you are using the most recent version of alot. If you are using an old
  version please update to the latest version before filing a bug

Once you've checked the above, please file a bug using the issue template.


Requesting a Feature
````````````````````

Feature requests are also filed via the issue tracker.

Before filing a feature request be sure to check the following:

* That the feature has not already been added to master or in a newer version

* That the feature has not already been requested. There is a feature tag for
  feature requests in the issue tracker, which is a good place to start.

* That the feature is in scope of the project

  Some examples of features that are not in scope:

  * Contact management, fetching email, sending email, indexing email.
    Alot relies on external services for all of these features. Integration
    with a new external service is okay.

* If the feature is requested already, please use the thumbs up emoji to add
  your support for the feature. Please do not add a "me too" comment.

Once you're sure that the feature isn't implemented or already requested, add a
request. You will be given a template to fill out, but don't, that template is
for bugs. Please be as thorough as possible when describing the feature, please
explain what it does, how it should work, and how you plan to use the feature;
if applicable.


Contributing
------------


Before you Contribute
`````````````````````

Alot is licensed under the `GNU GPLv3+
<https://www.gnu.org/licenses/gpl-3.0.en.html>`_, and all code contributions
will be covered by this license. You will retain your copyright on any code you
write.

By contributing you have agreed that you have the right to contribute the code
you have written, that the code you are contributing is owned by you or
licensed with a compatible license allowing it to be added to alot, and that
your employer or educational institution either does not or cannot claim the
copyright on any code you write, or that they have given you a waiver to
contribute to alot.


What to Contribute
``````````````````

* Bug fixes are always welcome

* Tests for bugs. If you can replicate a bug but don't want to or can't fix it
  we'll still take a unit test. Please decorate the test as an expected
  failure if it is failing.

* New features. Please be aware that we won't take every feature proposed,
  especially those that expand the scope of the project.

* Documentation. Including typos, spelling and grammar, wrong type and
  parameter annotations, or documentation that has gotten out of sync with the
  code.


Sending a Pull Request
``````````````````````

The best way to send new code is with a pull request using the github interface.

* Follow :pep:`8`. This means in particular a maximum linewidth of *79* and no
  trailing white spaces. If in doubt, use an Automatic tool (`[0]
  <http://www.logilab.org/857>`_, `[1] <http://pypi.python.org/pypi/pep8/>`_,
  `[2] <http://pypi.python.org/pypi/pyflakes/>`_) to verify your code.

* Document! Needless to say, we want readable and well documented code. Moreover,

  * use `sphinx directives
    <http://sphinx.pocoo.org/domains.html#info-field-lists>`_ to document the
    parameters and return values of your methods so that we maintain up-to-date
    API docs.
  * If you implemented a new feature, update the user manual in
    `/docs/source/usage` accordingly.
  * If you implement a new feature or fix a major bug, add it to the NEWS file

* If you close an issue, but sure to use a `"fixes" tag
  <https://help.github.com/articles/closing-issues-using-keywords/>`_ to
  automatically close the issue.

* Alot is currently python 2.7 only, but transitioning to python 3.x, please
  do not use constructs that do not map to python 3

* Make sure you don't regress any unit tests. They are implemented with the
  builtin unittest module, and can be run with `python setup.py test`, or with
  your favorite test runner such as pytest or nose.

* If you are fixing a bug or adding a new features, please include unit tests.

* Your patch will be automatically checked in our CI system, which will build
  docs and run unit tests. If any of these fail merging will be blocked until
  they are fixed.
