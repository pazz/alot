Contributing
============

Development is coordinated entirely via the projects `github page <https://github.com/pazz/alot>`_
especially the `issue tracker <https://github.com/pazz/alot/issues>`_.

You can send patches to notmuch's mailing list but pull requests on github are preferred.
Here are a few more things you should know and check before you send pull requests:

* Follow :pep:`8`. This means in particular a maximum linewidth of *79* and no trailing
  white spaces. If in doubt, use an Automatic tool
  (`[0] <http://www.logilab.org/857>`_, `[1] <http://pypi.python.org/pypi/pep8/>`_, `[2]
  <http://pypi.python.org/pypi/pyflakes/>`_)
  to verify your code.

* Document! Needless to say, we want readable and well documented code. Moreover,

  * use `sphinx directives <http://sphinx.pocoo.org/domains.html#info-field-lists>`_ to document
    the parameters and return values of your methods so that we maintain up-to-date API docs.
  * Make sure your patch doesn't break the API docs. The build service at `readthedocs.org <http://alot.rtfd.org>`_
    is fragile when it comes to new import statements in our code.
  * If you implemented a new feature, update the user manual in :file:`/docs/user` accordingly.

